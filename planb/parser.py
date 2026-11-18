"""Natural-language request -> structured DisruptionEvent.

The LLM does the understanding; the result is validated with Pydantic and checked
against the known places/bookings. A transparent rule-based parser is used in mock
mode (no API key) and as a fallback when the model output is unusable.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Optional

from pydantic import ValidationError

from .data import World
from .llm import LLMClient, LLMUsage, extract_json
from .models import Booking, DisruptionEvent, Trip

EVENT_TYPES = ["weather_change", "place_closed", "transport_delay", "trip_extension", "trip_shortening",
               "reservation_change"]

SYSTEM_PROMPT = """You are the request-understanding module of PlanB, a travel copilot.
Convert the traveller's message into ONE JSON object describing the change event. Do NOT plan the trip,
do NOT compute any cost. Use only ids that appear in the context. Use ISO 8601 datetimes with the trip
timezone offset (+09:00 for Tokyo). If a required value is not stated and cannot be inferred from the
context, use null — never guess.

JSON schema:
{
  "event_type": one of ["weather_change","place_closed","transport_delay","trip_extension","trip_shortening","reservation_change"],
  "description": short description in the user's language,
  "affected_start": ISO datetime or null,   // weather/delay/closure time range start
  "affected_end": ISO datetime or null,
  "affected_place_ids": [place ids],         // for place_closed
  "parameters": {
     "new_end_date": "YYYY-MM-DD",           // trip_extension / trip_shortening: the new return date
     "booking_id": "...", "new_start": ISO datetime   // reservation_change
  }
}
Conventions: morning = 08:00-12:00, afternoon = 12:00-18:00, evening = 18:00-22:00, whole day = 00:00 to next day 00:00.
For transport_delay, affected_end is the time from which the traveller can continue.
Reply with the JSON object only."""


def _context(trip: Trip, bookings: list[Booking], world: World) -> str:
    acts = [{"id": a.activity_id, "title": a.title, "place_id": a.place_id,
             "start": world.local(a.start_at).isoformat(), "locked": a.is_locked} for a in trip.sorted_activities()]
    places = [{"id": p.place_id, "name": p.name, "name_zh": p.name_zh} for p in world.places.values()]
    bks = [{"id": b.booking_id, "title": b.title} for b in bookings]
    return json.dumps({"trip": {"destination": trip.destination, "start_date": str(trip.start_date),
                                "end_date": str(trip.end_date), "timezone": trip.timezone},
                       "activities": acts, "bookings": bks, "places": places}, ensure_ascii=False)


def _sanitize(data: dict, trip: Trip, bookings: list[Booking], world: World) -> DisruptionEvent:
    data = dict(data)
    data["affected_place_ids"] = [p for p in (data.get("affected_place_ids") or []) if p in world.places]
    params = data.get("parameters") or {}
    if params.get("booking_id") and not any(b.booking_id == params["booking_id"] for b in bookings):
        params["booking_id"] = None
    data["parameters"] = {k: v for k, v in params.items() if v is not None}
    data["source"] = "llm"
    ev = DisruptionEvent.model_validate({k: v for k, v in data.items() if k in DisruptionEvent.model_fields})
    tz = world.tz
    for f in ("affected_start", "affected_end"):
        v = getattr(ev, f)
        if v is not None and v.tzinfo is None:
            setattr(ev, f, v.replace(tzinfo=tz))
    return ev


def parse_request(text: str, trip: Trip, bookings: list[Booking], world: World, llm: LLMClient,
                  usage: LLMUsage | None = None, max_attempts: int = 2) -> tuple[Optional[DisruptionEvent], str]:
    """Return (event, method) where method is 'llm', 'rule_fallback' or 'rule'."""
    if llm.is_mock:
        return parse_rule_based(text, trip, bookings, world), "rule"
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{_context(trip, bookings, world)}\n\nTraveller message:\n{text}"}]
    for _ in range(max_attempts):
        r = llm.chat(messages, max_tokens=600)
        if usage:
            usage.add(r)
        data = extract_json(r.text)
        if data is None:
            err = "Your reply was not valid JSON."
        else:
            try:
                return _sanitize(data, trip, bookings, world), "llm"
            except (ValidationError, ValueError, TypeError) as e:
                err = f"Schema validation failed: {str(e)[:500]}"
        messages += [{"role": "assistant", "content": r.text}, {"role": "user", "content": err + " Reply with corrected JSON only."}]
    return parse_rule_based(text, trip, bookings, world), "rule_fallback"


# ---------------------------------------------------------------------------
# Rule-based parser (mock mode + fallback)
# ---------------------------------------------------------------------------

_PERIODS = {"上午": ("08:00", "12:00"), "早上": ("08:00", "10:30"), "morning": ("08:00", "12:00"),
            "下午": ("12:00", "18:00"), "afternoon": ("12:00", "18:00"),
            "晚上": ("18:00", "22:00"), "evening": ("18:00", "22:00")}


def _find_date(text: str, trip: Trip) -> Optional[date]:
    year = trip.start_date.year
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", text) or re.search(r"\b(\d{1,2})/(\d{1,2})\b", text)
    if m:
        return date(year, int(m.group(1)), int(m.group(2)))
    m = re.search(r"Dec(?:ember)?\.?\s*(\d{1,2})", text, re.I)
    if m:
        return date(year, 12, int(m.group(1)))
    m = re.search(r"第\s*(\d)\s*天|day\s*(\d)", text, re.I)
    if m:
        return trip.start_date + timedelta(days=int(m.group(1) or m.group(2)) - 1)
    return None


def _find_times(text: str, day: date, tz) -> tuple[Optional[datetime], Optional[datetime]]:
    def mk(hm: str) -> datetime:
        h, mi = map(int, hm.split(":"))
        return datetime(day.year, day.month, day.day, h, mi, tzinfo=tz)

    m = re.search(r"(上午|早上|下午|晚上)?\s*(\d{1,2})[:：点](\d{2})?\s*(?:分)?\s*(?:到|至|-|~|to)\s*"
                  r"(上午|早上|下午|晚上)?\s*(\d{1,2})[:：点]?(\d{2})?", text)
    if m:
        q1, h1, m1, q2, h2, m2 = m.group(1), int(m.group(2)), int(m.group(3) or 0), m.group(4), int(m.group(5)), int(m.group(6) or 0)
        pm = ("下午", "晚上")
        if q1 in pm and h1 < 12:
            h1 += 12
        if (q2 in pm or (q2 is None and q1 in pm)) and h2 < 12:
            h2 += 12
        if h2 < h1 and h2 < 12:
            h2 += 12
        return mk(f"{h1}:{m1:02d}"), mk(f"{h2 % 24}:{m2:02d}")
    if re.search(r"全天|整天|all day|whole day", text, re.I):
        return mk("00:00"), mk("00:00") + timedelta(days=1)
    for k, (a, b) in _PERIODS.items():
        if k in text.lower():
            return mk(a), mk(b)
    return None, None


def _find_places(text: str, world: World) -> list[str]:
    found = []
    low = text.lower()
    for p in world.places.values():
        names = [p.name_zh, p.name, p.name.split(" (")[0], p.name_zh.split("（")[0]]
        if any(n and n.lower() in low for n in names):
            found.append(p.place_id)
    return found


def parse_rule_based(text: str, trip: Trip, bookings: list[Booking], world: World) -> Optional[DisruptionEvent]:
    tz = world.tz
    low = text.lower()
    day = _find_date(text, trip)
    desc = text.strip()[:80]

    if re.search(r"多待|多玩|延长|延后|推迟|延期|晚一天|extend|stay .*longer|postpone", low):
        new_end = day or trip.end_date + timedelta(days=1)
        return DisruptionEvent(event_type="trip_extension", description=desc, source="rule",
                               parameters={"new_end_date": str(new_end)})
    if re.search(r"提前.*回|早一天|缩短|shorten|leave earlier|go home earlier", low):
        new_end = day or trip.end_date - timedelta(days=1)
        return DisruptionEvent(event_type="trip_shortening", description=desc, source="rule",
                               parameters={"new_end_date": str(new_end)})
    if re.search(r"改到|改期|moved to|rescheduled", low):
        target = None
        for b in bookings:
            names = [b.title.split(" ")[0].lower(), (b.provider_name or "").split(" ")[0].lower()]
            if b.place_id:
                p = world.place(b.place_id)
                names += [p.name_zh.split("（")[0].lower(), p.name.split(" ")[0].lower()]
            if any(n and n in low for n in names):
                target = b
                break
        m = re.search(r"改到了?\s*(?:晚上|下午)?\s*(\d{1,2})[:：点](\d{2})?", text)
        if target and m and day:
            h = int(m.group(1))
            if ("下午" in text or "晚上" in text) and h < 12:
                h += 12
            new_start = datetime(day.year, day.month, day.day, h, int(m.group(2) or 0), tzinfo=tz)
            return DisruptionEvent(event_type="reservation_change", description=desc, source="rule",
                                   parameters={"booking_id": target.booking_id, "new_start": new_start.isoformat()})
        return DisruptionEvent(event_type="reservation_change", description=desc, source="rule",
                               parameters={"booking_id": target.booking_id} if target else {})
    if re.search(r"关闭|闭馆|不开放|不对外开放|closed|closure", low):
        places = _find_places(text, world)
        s, e = (None, None)
        if day:
            s, e = _find_times(text, day, tz)
            if s is None:
                s = datetime(day.year, day.month, day.day, tzinfo=tz)
                e = s + timedelta(days=1)
        return DisruptionEvent(event_type="place_closed", description=desc, source="rule",
                               affected_place_ids=places, affected_start=s, affected_end=e)
    if re.search(r"延误|晚点|堵车|delay|到不了", low):
        s, e = _find_times(text, day, tz) if day else (None, None)
        m = re.search(r"(\d{1,2})[点:：](\d{2}|半)?\s*之前", text)
        if day and m:
            minute = 30 if m.group(2) == "半" else int(m.group(2) or 0)
            e = datetime(day.year, day.month, day.day, int(m.group(1)), minute, tzinfo=tz)
            s = s if (s and s < e) else datetime(day.year, day.month, day.day, 8, 0, tzinfo=tz)
        return DisruptionEvent(event_type="transport_delay", description=desc, source="rule",
                               affected_start=s, affected_end=e)
    if re.search(r"雨|雪|台风|天气|rain|storm|snow|typhoon", low):
        s, e = _find_times(text, day, tz) if day else (None, None)
        return DisruptionEvent(event_type="weather_change", description=desc, source="rule",
                               affected_start=s, affected_end=e)
    return None
