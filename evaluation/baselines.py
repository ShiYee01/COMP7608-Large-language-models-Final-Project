"""Baselines and the PlanB method, all producing the same MethodOutput.

Fairness: all LLM methods receive the SAME facts (trip, bookings with policies and
quotes, place catalogue with opening hours, travel-time matrix, user request) and the
SAME output schema and cost definition. They use the same model and temperature.
- direct:      Baseline A — plain instruction, model edits the itinerary and computes cost itself.
- structured:  Baseline B — same facts + explicit constraint rules, cost rules, step-by-step checklist.
- planb:       LLM parses the request -> deterministic repair/validation/booking/cost engine.
- planb_gold:  PlanB fed the gold structured event (no LLM) — isolates request-parsing errors.
"""
from __future__ import annotations

import json
import time
from typing import Optional

from common import MethodOutput, Scenario, itinerary_to_trip

from planb.llm import LLMClient, LLMUsage, extract_json
from planb.parser import parse_request
from planb.repair import replan

OUTPUT_SCHEMA = """Return ONE JSON object and nothing else:
{
  "status": "ok" | "infeasible" | "needs_information",
  "itinerary": [   // the FULL updated itinerary, including unchanged activities and the flight/airport activities
    {"activity_id": "<existing id, or new_1, new_2 ... for new activities>", "place_id": "<id from places>",
     "title": "...", "start_at": "YYYY-MM-DDTHH:MM:SS+09:00", "end_at": "YYYY-MM-DDTHH:MM:SS+09:00"}
  ],
  "affected_booking_ids": ["<ids of existing bookings that now require the traveller to act: change date, extend, shorten, cancel or claim refund>"],
  "additional_cost_cny": <number or null>,
  "explanation": "<short explanation>"
}
Definition of additional_cost_cny: the net ADDITIONAL out-of-pocket money (CNY) caused by changes to the EXISTING
bookings, relative to the original plan: change fees + fare/price differences + extra nights + new bookings that
replace existing ones, MINUS confirmed refunds. Do not include entry fees of newly added sightseeing activities.
Use null if it cannot be determined from the given data.
If no itinerary can satisfy the traveller's fixed requirements, use status "infeasible" and keep the itinerary unchanged."""

STRUCTURED_RULES = """Follow these rules strictly.
HARD CONSTRAINTS (a valid itinerary must satisfy all of them):
1. No two activities overlap in time.
2. Between consecutive activities on the same day, the gap must be at least the travel time in the matrix.
3. Every visit must lie fully inside the place's opening hours for that weekday (a weekday missing = closed).
4. Activities with "is_locked": true must keep the same place, start and end time — unless the traveller's request
   explicitly changes them (e.g. the return flight when changing the trip dates) or a provider moved the reservation.
5. Do not schedule anything at a place during a stated closure; during bad weather do not schedule OUTDOOR places
   (indoor=false) in the affected time range; during a transport delay nothing can happen in the affected range.
6. All activities must be within the trip dates; nothing after the departure-flight airport block starts on that day.
7. Only use place_ids from the places list.
REPAIR POLICY: change only the activities affected by the event; keep everything else exactly as it was.
COST RULES:
- Use ONLY the fees, refunds and quotes written in the bookings (policy + quotes). Amounts in data are in fen (1/100 CNY).
- Flight date change = change_fee + fare difference from the matching quote. Hotel extension = the extend_stay quote.
- Already-paid amounts are NOT new spending. Refunds count as negative.
- If any needed fee/quote/refund rule is missing (null), additional_cost_cny MUST be null — never guess or use 0.
STEP-BY-STEP: (1) identify the event and its time range; (2) list affected activities and bookings; (3) repair only
those activities; (4) check every hard constraint above; (5) compute the cost from the rules; (6) output JSON."""


def _compact_hours(oh) -> str:
    if oh is None:
        return "UNKNOWN"
    if not oh:
        return "closed"
    groups: dict[str, list[str]] = {}
    for day, windows in oh.items():
        groups.setdefault(",".join(f"{a}-{b}" for a, b in windows), []).append(day)
    return "; ".join(f"{'/'.join(days)} {w}" for w, days in groups.items())


def serialize_facts(s: Scenario) -> str:
    w = s.world
    trip = {
        "start_date": str(s.trip.start_date), "end_date": str(s.trip.end_date), "timezone": s.trip.timezone,
        "weekdays": "2026-12-10 is Thursday", "preferences": s.trip.preferences.model_dump(),
        "activities": [{"activity_id": a.activity_id, "title": a.title, "place_id": a.place_id,
                        "start_at": w.local(a.start_at).isoformat(), "end_at": w.local(a.end_at).isoformat(),
                        "category": a.category, "is_locked": a.is_locked} for a in s.trip.sorted_activities()],
    }
    bookings = [b.model_dump(mode="json", exclude_none=True) for b in s.bookings]
    places = [{"place_id": p.place_id, "name": p.name_zh or p.name, "category": p.category, "indoor": p.indoor,
               "opening_hours": _compact_hours(p.opening_hours), "tags": p.tags}
              for p in w.places.values()]
    seen, pairs = set(), []
    for (a, b), tt in w._travel.items():
        if (b, a) in seen:
            continue
        seen.add((a, b))
        pairs.append(f"{a}~{b}:{tt.travel_minutes}")
    return (f"TRIP:\n{json.dumps(trip, ensure_ascii=False)}\n\nBOOKINGS (money in fen):\n"
            f"{json.dumps(bookings, ensure_ascii=False)}\n\nPLACES:\n{json.dumps(places, ensure_ascii=False)}\n\n"
            f"TRAVEL MINUTES (symmetric, missing pair = unknown):\n{' '.join(pairs)}")


def _mock_reply(s: Scenario) -> str:
    """Pipeline-test stand-in: returns the original itinerary unchanged. NOT a real baseline result."""
    w = s.world
    return json.dumps({"status": "ok", "itinerary": [
        {"activity_id": a.activity_id, "place_id": a.place_id, "title": a.title,
         "start_at": w.local(a.start_at).isoformat(), "end_at": w.local(a.end_at).isoformat()}
        for a in s.trip.activities], "affected_booking_ids": [], "additional_cost_cny": None,
        "explanation": "mock"})


def run_llm_baseline(s: Scenario, llm: LLMClient, structured: bool) -> MethodOutput:
    name = "structured" if structured else "direct"
    system = "You are a careful travel planning assistant." + (f"\n\n{STRUCTURED_RULES}" if structured else "")
    user = (f"{serialize_facts(s)}\n\nTRAVELLER REQUEST:\n{s.raw['user_request']}\n\n"
            f"Update the itinerary for this request.\n{OUTPUT_SCHEMA}")
    if structured:
        user += '\nYou may add a "reasoning" field (string) before "status" for your step-by-step check.'
    out = MethodOutput(method=name)
    t0 = time.perf_counter()
    try:
        r = llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}],
                     max_tokens=3000, mock=lambda _m: _mock_reply(s))
    except Exception as e:
        out.json_ok, out.error = False, str(e)[:300]
        return out
    out.latency_s = r.latency_s if r.cached else time.perf_counter() - t0
    out.llm_calls, out.prompt_tokens, out.completion_tokens = 1, r.prompt_tokens, r.completion_tokens
    out.raw_text = r.text
    data = extract_json(r.text)
    if not isinstance(data, dict):
        out.json_ok, out.error = False, "no JSON"
        return out
    out.status = data.get("status")
    out.affected_booking_ids = [str(x) for x in (data.get("affected_booking_ids") or [])]
    cost = data.get("additional_cost_cny")
    try:
        out.cost_minor = None if cost is None else int(round(float(cost) * 100))
    except (TypeError, ValueError):
        out.cost_minor = None
    out.trip, out.format_errors = itinerary_to_trip(data.get("itinerary") or [], s.trip, s.world)
    return out


def run_planb(s: Scenario, llm: Optional[LLMClient], use_gold_event: bool = False) -> MethodOutput:
    out = MethodOutput(method="planb_gold" if use_gold_event else "planb")
    usage = LLMUsage()
    t0 = time.perf_counter()
    if use_gold_event:
        event, out.parse_method = s.gold_event, "gold"
    else:
        try:
            event, out.parse_method = parse_request(s.raw["user_request"], s.trip, s.bookings, s.world, llm, usage)
        except Exception as e:
            out.json_ok, out.error = False, str(e)[:300]
            return out
    out.parsed_event = event.model_dump(mode="json") if event else None
    if event is None:
        out.status = "needs_information"
        out.trip = s.trip
    else:
        res = replan(s.trip, event, s.world, s.bookings)
        out.status = res.status
        if res.status == "ok":
            p = res.proposals[0]
            out.trip = p.proposed_trip
            out.affected_booking_ids = [i.booking_id for i in p.booking_impacts if i.status == "change_required"]
            out.cost_minor = p.cost_estimate.total_additional_minor
        else:
            out.trip = s.trip
    elapsed = time.perf_counter() - t0
    # When LLM responses come from the cache, count the original API latency instead of ~0.
    out.latency_s = max(elapsed, usage.latency_s)
    out.llm_calls, out.prompt_tokens, out.completion_tokens = usage.calls, usage.prompt_tokens, usage.completion_tokens
    return out
