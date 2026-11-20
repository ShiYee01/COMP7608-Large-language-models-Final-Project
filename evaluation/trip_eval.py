"""Evaluation of the new features: trip setup by conversation (T*) and chat edits (E*).

Methods (same model, temperature 0, same facts for the LLM baselines):
  direct      LLM reads the request + full catalogue + travel matrix and returns the plan / edited plan itself
  structured  same, plus explicit rules (closing days, travel time, locked bookings, pace, avoid, no invented
              places, ask when dates are missing / when something does not fit, report unknowns) and a checklist
  planb       LLM only extracts the request; PlanB's planner / edit engine builds and validates everything
  planb_gold  PlanB's planner / edit engine on the hand-written gold request (isolates extraction errors);
              for edits the gold request is the scenario's `gold_edit` (added after the model runs)

Every itinerary is judged by the same validator and the hand-written checks in evaluation/trip_scenarios/.
Scoring rules agreed with the reviewer: associated preferences are not penalised; on a full day the method
must ask with concrete options (a bare "does not fit" is wrong).

  python evaluation/trip_eval.py --mock                     # pipeline test (NOT results)
  python evaluation/trip_eval.py --run-name trip-nemotron   # real run (needs LLM_* environment variables)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from planb.agent import PlanBAgent  # noqa: E402
from planb.data import World, load_world  # noqa: E402
from planb.edits import EditRequest, add_user_restaurant, apply_edit  # noqa: E402
from planb.llm import LLMClient, LLMUsage, extract_json  # noqa: E402
from planb.models import Activity, Booking, Preferences, Trip, new_id  # noqa: E402
from planb.planner import plan_trip  # noqa: E402
from planb.store import TripStore  # noqa: E402
from planb.trip_request import TAG_LABELS, MustVisit, StatedBooking, HotelStay, TripRequest, extract_trip_request  # noqa: E402
from planb.validator import validate  # noqa: E402

SCEN = ROOT / "evaluation" / "trip_scenarios"
TODAY = date(2026, 11, 19)
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PACE_CAP = {"relaxed": 3, "normal": 4, "packed": 5}


# ---------------------------------------------------------------------------
# Facts given to the LLM baselines (the same catalogue PlanB uses)
# ---------------------------------------------------------------------------

def _hours(p) -> str:
    if p.opening_hours is None:
        return "unknown"
    open_days = [d for d in WEEKDAYS if d in p.opening_hours]
    closed = [d for d in WEEKDAYS if d not in p.opening_hours]
    first = p.opening_hours[open_days[0]][0]
    return f"{first[0]}-{first[1]}" + (f" (closed {','.join(closed)})" if closed else "")


def serialize_world(world: World) -> dict:
    places = [{"id": p.place_id, "name_zh": p.name_zh, "name": p.name, "category": p.category,
               "indoor": p.indoor, "area": p.area, "hours": _hours(p), "visit_minutes": p.suggested_visit_minutes,
               "tags": p.tags} for p in world.places.values()]
    seen, lines = set(), []
    for (a, b), tt in world._travel.items():
        if (b, a) in seen:
            continue
        seen.add((a, b))
        lines.append(f"{a} {b} {tt.travel_minutes}")
    return {"weekdays": "2026-12-10 is Thursday", "places": places,
            "travel_minutes (symmetric, 'a b minutes'; a missing pair means unknown)": "\n".join(lines)}


SETUP_SCHEMA = """Return ONE JSON object and nothing else:
{
  "status": "ok" | "needs_information",
  "questions": ["questions for the traveller, if information is missing"],
  "understood": {"start_date": "YYYY-MM-DD" | null, "end_date": "YYYY-MM-DD" | null,
                 "must_visit": [{"place_id": "...", "day": "YYYY-MM-DD" | null}], "avoid": ["place_id"],
                 "interests": [tags from: TAGS], "pace": "relaxed" | "normal" | "packed" | null,
                 "hotel_place_id": "one of the hotel ids" | null,
                 "bookings": [{"kind": "flight_arrival" | "flight_departure" | "attraction" | "restaurant",
                               "place_id": "...", "start": "ISO datetime +09:00",
                               "price_cny": number | null, "change_fee_cny": number | null}],
                 "unknown_places": ["places the traveller named that are not in the catalogue"]},
  "itinerary": [{"place_id": "...", "title": "...", "start_at": "YYYY-MM-DDTHH:MM:SS+09:00",
                 "end_at": "YYYY-MM-DDTHH:MM:SS+09:00",
                 "category": "visit" | "meal" | "flight_arrival" | "flight_departure" | "free_time"}],
  "unplaceable": [{"place_id": "...", "reason": "..."}],
  "explanation": "short"
}
In understood.bookings, "start" of a flight is the landing time (arrival) or the take-off time (departure).
In the itinerary, an arrival flight is an item at the airport from landing time (30 minutes); a departure flight is
an item at the airport from 2 hours before take-off until take-off. Bookings the traveller made go into the
itinerary at exactly the stated time.""".replace("TAGS", ", ".join(TAG_LABELS))

SETUP_RULES = """Follow these rules strictly.
1. Use only place ids from the catalogue. A place the traveller names that is not in the catalogue goes into
   understood.unknown_places; never replace it with another place and never invent places.
2. If the travel dates are not given, set status "needs_information", ask for them and return an empty itinerary.
3. Every visit must lie inside the place's opening hours for that weekday; a weekday listed as closed means closed.
4. No overlaps; between consecutive items the gap must be at least the travel time in the matrix.
5. Bookings the traveller made are fixed at the stated time. Nothing before the arrival flight or after
   departure check-in on those days.
6. Must-visit places must be scheduled (on the requested day if one is given). If one cannot be scheduled,
   do not schedule it and list it in "unplaceable" with the reason.
7. Never schedule places the traveller wants to avoid.
8. Pace: at most 3 visits per day for relaxed, 4 for normal, 5 for packed. Prefer places matching the interests.
9. Infer the year from today's date (the trip is in the future).
Before answering, check every item against rules 3-8."""

EDIT_SCHEMA = """Return ONE JSON object and nothing else:
{
  "status": "ok" | "ask" | "refuse",
  "message": "what you tell the traveller",
  "options": [{"summary": "...",
               "itinerary": [the FULL updated itinerary: {"activity_id": "existing id, or new_1, new_2 ...",
                             "place_id": "catalogue id, or 'custom' for a place not in the catalogue",
                             "custom_name": "name if place_id is 'custom'", "title": "...",
                             "start_at": "...+09:00", "end_at": "...+09:00",
                             "category": "visit" | "meal" | "flight_arrival" | "flight_departure" | "free_time"}]}],
  "unverified": ["anything you could not verify, e.g. a restaurant's opening hours"]
}
"ok": you propose one or more options; "ask": you need the traveller to choose or confirm (options may be given);
"refuse": you will not change the itinerary. Every option is only a proposal the traveller approves."""

EDIT_RULES = """Follow these rules strictly.
1. Change as little as possible; keep every other activity exactly as it is (same id, place and times).
2. Never move or remove locked activities (is_locked = true, e.g. booked tickets and flights) on your own:
   if the request needs that, use status "ask" or "refuse" and explain.
3. Respect opening hours (closed weekdays), no overlaps, enough travel time between consecutive items.
4. "free_time" items are meal slots ("eat nearby"); a restaurant the traveller picks replaces that slot.
5. Use only catalogue ids; a restaurant that is not in the catalogue uses place_id "custom" with its name, and its
   opening hours / price are unknown: list them in "unverified" instead of guessing.
6. If what the traveller wants does not fit, do not just say it does not fit: offer concrete options
   (replace a specific activity, or another day / time slot) with status "ask".
7. Recommendations should match the traveller's preferences or the requested kind of place.
Before answering, check every option against rules 1-6."""


def _setup_prompt(s: dict, world: World, structured: bool) -> list[dict]:
    system = "You are a travel planning assistant for Tokyo. Plan the trip the traveller describes."
    if structured:
        system += "\n" + SETUP_RULES
    user = (f"Today is {s['today']}.\nCatalogue and travel times:\n"
            f"{json.dumps(serialize_world(world), ensure_ascii=False)}\n\nTraveller:\n{s['request']}\n\n{SETUP_SCHEMA}")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _edit_prompt(e: dict, base: dict, world: World, structured: bool) -> list[dict]:
    system = "You are a travel planning assistant for Tokyo. Update the traveller's itinerary as they ask."
    if structured:
        system += "\n" + EDIT_RULES
    current = {"trip": {k: base["trip"][k] for k in ("start_date", "end_date", "preferences", "hotel_place_id")},
               "itinerary": base["trip"]["activities"], "bookings": base["bookings"]}
    user = (f"Catalogue and travel times:\n{json.dumps(serialize_world(world), ensure_ascii=False)}\n\n"
            f"Current itinerary:\n{json.dumps(current, ensure_ascii=False)}\n\nTraveller:\n{e['request']}\n\n{EDIT_SCHEMA}")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


# ---------------------------------------------------------------------------
# Running the methods
# ---------------------------------------------------------------------------

def _dt(v) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None


def _items_to_acts(items: list, world: World, keep_ids: bool = False) -> tuple[list[Activity], int, list[str]]:
    """LLM itinerary items -> Activities. Custom places are registered with unknown location (never invented)."""
    acts, malformed, invented = [], 0, []
    for i, it in enumerate(items or []):
        try:
            pid = str(it.get("place_id") or "")
            cat = it.get("category") if it.get("category") in ("visit", "meal", "flight_arrival", "flight_departure",
                                                                "free_time") else "visit"
            if cat == "free_time":
                # meal slots are location-free ("eat nearby"): their place id is irrelevant, never "invented"
                pid = pid if world.place(pid) else (acts[-1].place_id if acts else "hotel_shinjuku")
            elif pid == "custom" or pid.startswith("custom"):
                pid, _ = add_user_restaurant(world, str(it.get("custom_name") or it.get("title") or "custom"))
            elif world.place(pid) is None:
                invented.append(pid)
            start, end = _dt(it["start_at"]), _dt(it["end_at"])
            acts.append(Activity(activity_id=str(it.get("activity_id")) if keep_ids and it.get("activity_id") else f"x{i}",
                                 place_id=pid, title=str(it.get("title") or pid), start_at=start, end_at=end,
                                 category=cat, is_locked=bool(it.get("is_locked", False))))
        except Exception:
            malformed += 1
    return acts, malformed, invented


def run_setup(s: dict, method: str, llm: Optional[LLMClient]) -> dict:
    world = load_world(extended=True)
    out = {"scenario": s["id"], "type": "setup", "method": method, "llm_calls": 0, "tokens": 0, "latency_s": 0.0}
    t0 = time.perf_counter()
    if method in ("planb", "planb_gold"):
        usage = LLMUsage()
        if method == "planb":
            req, how = extract_trip_request(s["request"], world, llm, today=TODAY, usage=usage)
        else:
            req, how = gold_request(s), "gold"
        out["parse_method"] = how
        out["understood"] = understood_from_request(req)
        if req.missing_required():
            out.update(status="needs_information", acts=[], unplaceable=[])
        else:
            plan = plan_trip(world, req)
            out.update(status="ok", acts=plan.trip.activities, unplaceable=plan.unplaceable)
        out["llm_calls"], out["tokens"] = usage.calls, usage.prompt_tokens + usage.completion_tokens
        out["latency_s"] = usage.latency_s if usage.calls else time.perf_counter() - t0
        out["world"] = world
        return out
    r = llm.chat(_setup_prompt(s, world, method == "structured"), max_tokens=6000, mock=lambda _m: _mock_setup())
    out["llm_calls"], out["tokens"] = 1, r.prompt_tokens + r.completion_tokens
    out["latency_s"] = r.latency_s if r.cached else time.perf_counter() - t0
    out["raw_text"] = r.text
    data = extract_json(r.text) or {}
    out["json_ok"] = bool(data)
    out["status"] = "needs_information" if data.get("status") == "needs_information" else ("ok" if data else "error")
    out["understood"] = data.get("understood") or {}
    acts, malformed, invented = _items_to_acts(data.get("itinerary") or [], world)
    out.update(acts=acts, malformed=malformed, invented=invented,
               unplaceable=[str(u.get("place_id")) for u in (data.get("unplaceable") or []) if isinstance(u, dict)])
    out["world"] = world
    return out


def _mock_setup() -> str:
    return json.dumps({"status": "ok", "understood": {}, "itinerary": [], "unplaceable": []})


def gold_request(s: dict) -> TripRequest:
    g = s["gold_request"]
    hotel = HotelStay(place_id=g["hotel_place_id"]) if g["hotel_place_id"] else None
    return TripRequest(
        start_date=g["start_date"], end_date=g["end_date"],
        must_visit=[MustVisit(place_id=p, day=g["must_visit_days"].get(p)) for p in g["must_visit"]],
        avoid=g["avoid"], interests=g["interests_required"], pace=g["pace"], hotel=hotel,
        bookings=[StatedBooking(kind=b["kind"], place_id=b["place_id"], start=b["start"], title=b["place_id"],
                                price_cny=b.get("price_cny"), change_fee_cny=b.get("change_fee_cny"))
                  for b in g["bookings"]],
        unknown_places=g["unknown_places"])


def understood_from_request(req: TripRequest) -> dict:
    return {"start_date": str(req.start_date) if req.start_date else None,
            "end_date": str(req.end_date) if req.end_date else None,
            "must_visit": [{"place_id": m.place_id, "day": str(m.day) if m.day else None} for m in req.must_visit],
            "avoid": req.avoid, "interests": req.interests, "pace": req.pace,
            "hotel_place_id": req.hotel.place_id if req.hotel else None,
            "bookings": [{"kind": b.kind, "place_id": b.place_id, "start": b.start.isoformat() if b.start else None,
                          "price_cny": b.price_cny, "change_fee_cny": b.change_fee_cny} for b in req.bookings],
            "unknown_places": req.unknown_places}


def load_edit_base() -> tuple[Trip, list[Booking], dict]:
    raw = json.loads((SCEN / "edit_base.json").read_text())
    return Trip.model_validate(raw["trip"]), [Booking.model_validate(b) for b in raw["bookings"]], raw


def run_edit(e: dict, method: str, llm: Optional[LLMClient]) -> dict:
    world = load_world(extended=True)
    base, bookings, raw = load_edit_base()
    out = {"scenario": e["id"], "type": "edit", "method": method, "llm_calls": 0, "tokens": 0, "latency_s": 0.0,
           "world": world, "base": base}
    t0 = time.perf_counter()
    if method == "planb":
        agent = PlanBAgent(TripStore(base.model_copy(deep=True), bookings, world), llm)
        turn = agent.handle(e["request"], explain=False)
        status = {"WAITING_FOR_APPROVAL": "ok", "PREFERENCES_UPDATED": "ok"}.get(turn.state, "refuse")
        props = agent.store.pending()
        out.update(status=status, message=turn.message, parse_method=turn.parse_method,
                   options=[p.proposed_trip.activities for p in props],
                   unverified_flag=bool(any(p.validation.unknown_constraints for p in props))
                   or bool(re.search(r"未知|无法验证|无法确认", turn.message)),
                   llm_calls=turn.usage.calls, tokens=turn.usage.prompt_tokens + turn.usage.completion_tokens)
        out["latency_s"] = turn.usage.latency_s if turn.usage.calls else time.perf_counter() - t0
        return out
    if method == "planb_gold":
        store = TripStore(base.model_copy(deep=True), bookings, world)
        outcome = apply_edit(EditRequest.model_validate(e["gold_edit"]), store.trip, store.bookings, world, set())
        for p in outcome.proposals:
            store.add_proposal(p)
        props = store.pending()
        out.update(status={"WAITING_FOR_APPROVAL": "ok", "PREFERENCES_UPDATED": "ok"}.get(outcome.state, "refuse"),
                   message=outcome.message, parse_method="gold",
                   options=[p.proposed_trip.activities for p in props],
                   unverified_flag=bool(any(p.validation.unknown_constraints for p in props))
                   or bool(re.search(r"未知|无法验证|无法确认", outcome.message)))
        out["latency_s"] = time.perf_counter() - t0
        return out
    r = llm.chat(_edit_prompt(e, raw, world, method == "structured"), max_tokens=6000,
                 mock=lambda _m: json.dumps({"status": "refuse", "message": "mock", "options": []}))
    out["llm_calls"], out["tokens"] = 1, r.prompt_tokens + r.completion_tokens
    out["latency_s"] = r.latency_s if r.cached else time.perf_counter() - t0
    out["raw_text"] = r.text
    data = extract_json(r.text) or {}
    out["json_ok"] = bool(data)
    out["status"] = data.get("status") if data.get("status") in ("ok", "ask", "refuse") else "error"
    out["message"] = str(data.get("message") or "")
    options, invented = [], []
    for o in data.get("options") or []:
        if isinstance(o, dict):
            acts, _, inv = _items_to_acts(o.get("itinerary") or [], world, keep_ids=True)
            options.append(acts)
            invented += inv
    out["options"], out["invented"] = options, invented
    out["unverified_flag"] = bool(data.get("unverified")) or bool(re.search(r"未知|无法确认|unknown|not sure|verify",
                                                                             out["message"], re.I))
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _names_match(gold: str, got: list[str]) -> bool:
    g = re.sub(r"\s", "", gold).lower()
    for x in got:
        x = re.sub(r"\s", "", str(x)).lower()
        if x and (x in g or g in x):
            return True
        if len(set(re.findall(r"[一-鿿]{2}", g)) & set(re.findall(r"[一-鿿]{2}", x))) >= 2:
            return True
    return False


def score_extraction(s: dict, u: dict) -> dict:
    g = s["gold_request"]
    u = u or {}
    mv = u.get("must_visit") or []
    mv_ids = {m.get("place_id") if isinstance(m, dict) else m for m in mv}
    mv_days = {m.get("place_id"): m.get("day") for m in mv if isinstance(m, dict)}
    fields = {
        "dates": u.get("start_date") == g["start_date"] and u.get("end_date") == g["end_date"],
        "must_visit": mv_ids == set(g["must_visit"]),
        "avoid": set(u.get("avoid") or []) == set(g["avoid"]),
        "interests": set(g["interests_required"]) <= set(u.get("interests") or []),
        "pace": (u.get("pace") in (None, "normal")) if g["pace"] is None else u.get("pace") == g["pace"],
        "hotel": u.get("hotel_place_id") == g["hotel_place_id"],
        "unknown_places": all(_names_match(n, u.get("unknown_places") or []) for n in g["unknown_places"]),
    }
    if g["must_visit_days"]:
        fields["must_visit_days"] = all(str(mv_days.get(p)) == d for p, d in g["must_visit_days"].items())
    got_b = u.get("bookings") or []

    def same(gb, xb):
        if xb.get("kind") != gb["kind"] or xb.get("place_id") != gb["place_id"]:
            return False
        if _dt(xb.get("start")) != _dt(gb["start"]):
            return False
        return all(xb.get(k) is not None and float(xb.get(k)) == float(gb[k])
                   for k in ("price_cny", "change_fee_cny") if k in gb)

    fields["bookings"] = (len(got_b) == len(g["bookings"]) and
                          all(any(isinstance(x, dict) and same(gb, x) for x in got_b) for gb in g["bookings"]))
    return {f"x_{k}": v for k, v in fields.items()} | {"extraction_acc": round(sum(fields.values()) / len(fields), 3)}


def score_setup(s: dict, out: dict) -> dict:
    row = {"scenario": s["id"], "type": "setup", "method": out["method"], "status": out.get("status"),
           "llm_calls": out["llm_calls"], "tokens": out["tokens"], "latency_s": round(out["latency_s"], 2),
           "parse_method": out.get("parse_method", "")}
    row |= score_extraction(s, out.get("understood"))
    expected = s.get("expected_status", "ok")
    row["status_correct"] = out.get("status") == expected
    if expected != "ok":
        row["success"] = row["status_correct"] and not out.get("acts")
        return row
    c, g, world = s["plan_checks"], s["gold_request"], out["world"]
    acts = [a for a in out.get("acts", []) if a.start_at and a.end_at]
    if out.get("status") != "ok" or not acts:
        row.update(hard_violations=None, checks_passed=0.0, success=False)
        return row
    # free_time items are ignored when judging feasibility, for EVERY method: PlanB uses them as "eat nearby"
    # slots, the baselines also used them for "travel to X" / "transfer"; the schema never defined them precisely.
    trip = Trip(trip_id="eval", destination="Tokyo", start_date=g["start_date"], end_date=g["end_date"],
                preferences=Preferences(pace=g["pace"] or "normal"), hotel_place_id=g["hotel_place_id"],
                activities=[a for a in acts if a.category != "free_time"])
    res = validate(trip, world)
    row["hard_violations"] = len(res.hard_violations)
    row["violation_rules"] = ";".join(sorted({v.rule for v in res.hard_violations}))
    places = [a.place_id for a in acts]
    day_of = {}
    for a in acts:
        day_of.setdefault(a.place_id, set()).add(str(world.local(a.start_at).date()))
    visits_per_day = {}
    for a in acts:
        if a.category == "visit" and world.place(a.place_id) and world.place(a.place_id).category not in ("airport", "hotel"):
            d = str(world.local(a.start_at).date())
            visits_per_day[d] = visits_per_day.get(d, 0) + 1
    checks = {
        "c_feasible": not res.hard_violations,
        "c_no_invented": not out.get("invented") and all(world.place(p) for p in places),
        "c_must_include": all(p in places for p in c["must_include"]),
        "c_must_exclude": not any(p in places for p in c["must_exclude"]),
        "c_on_day": all(d in day_of.get(p, set()) for p, d in c["on_day"].items()),
        "c_not_on_day": not any(set(ds) & day_of.get(p, set()) for p, ds in c["not_on_day"].items()),
        "c_no_visits_on": not any(visits_per_day.get(d, 0) for d in c["no_visits_on"]),
        "c_unplaceable_reported": all(p not in places and p in out.get("unplaceable", [])
                                      for p in c["expected_unplaceable"]),
        "c_bookings_locked": all(any(a.place_id == b["place_id"] and a.category == b["kind"] and a.end_at == _dt(b["start"])
                                     if b["kind"] == "flight_departure" else
                                     a.place_id == b["place_id"] and a.start_at == _dt(b["start"]) for a in acts)
                                 for b in c["locked_at"]),
        "c_pace": max(visits_per_day.values(), default=0) <= c["max_visits_per_day"],
    }
    row |= checks
    row["checks_passed"] = round(sum(checks.values()) / len(checks), 3)
    extra = [a for a in acts if a.category == "visit" and a.place_id not in c["must_include"]
             and world.place(a.place_id) and world.place(a.place_id).category not in ("airport", "hotel")]
    tags = set(c["preference_tags"])
    row["pref_match"] = (round(sum(bool(tags & set(world.place(a.place_id).tags)) for a in extra) / len(extra), 3)
                         if extra and tags else None)
    row["success"] = row["status_correct"] and all(checks.values())
    return row


def score_edit(e: dict, out: dict) -> dict:
    x, world, base = e["expected"], out["world"], out["base"]
    row = {"scenario": e["id"], "type": "edit", "method": out["method"], "status": out.get("status"),
           "llm_calls": out["llm_calls"], "tokens": out["tokens"], "latency_s": round(out["latency_s"], 2),
           "parse_method": out.get("parse_method", ""), "n_options": len(out.get("options") or [])}
    options = out.get("options") or []
    base_by_id = {a.activity_id: a for a in base.activities}
    new_place_ids = lambda acts: [a.place_id for a in acts if a.activity_id not in base_by_id  # noqa: E731
                                  or a.place_id != base_by_id[a.activity_id].place_id]

    def option_ok(acts) -> dict:
        # free_time items ignored for feasibility, for every method (see score_setup)
        trip = base.model_copy(update={"activities": [a for a in acts if a.category != "free_time"]})
        res = validate(trip, world, None, base.model_copy(update={"activities": [a for a in base.activities
                                                                                  if a.category != "free_time"]}))
        ids = {a.activity_id: a for a in acts}
        added = [p for p in new_place_ids(acts) if world.place(p)]
        added_visits = [p for p in added if world.place(p).category not in ("food", "airport", "hotel")]
        chk = {
            "feasible": not res.hard_violations,
            "kept": all(k in ids and ids[k].key() == base_by_id[k].key() for k in x["must_keep"]),
            "removed": all(r not in ids or ids[r].place_id != base_by_id[r].place_id for r in x["removed"]),
            "tags": (not x["added_tags_any"] or not added_visits or
                     any(set(x["added_tags_any"]) & set(world.place(p).tags) for p in added_visits)),
            "added_place": True, "not_substituted": not (set(added) & set(x["must_not_use"])),
        }
        if x["added_place"]:
            ap = x["added_place"]
            lo, hi = ap["window"]
            chk["added_place"] = any(a.place_id == ap["place_id"] and str(world.local(a.start_at).date()) == ap["day"]
                                     and lo <= f"{world.local(a.start_at):%H:%M}" and f"{world.local(a.end_at):%H:%M}" <= hi
                                     for a in acts)
        if x["added_tags_any"] and x["status"] == "ask_with_options":
            chk["tags"] = bool(added_visits) and all(set(x["added_tags_any"]) & set(world.place(p).tags) for p in added_visits)
        return chk

    checked = [option_ok(o) for o in options]
    row["options_feasible"] = all(c["feasible"] for c in checked) if checked else None
    row["options_keep_locked"] = all(c["kept"] for c in checked) if checked else None
    row["invented_places"] = len(out.get("invented") or [])
    status = out.get("status")
    if x["status"] == "refused":
        row["status_correct"] = status in ("refuse", "ask") and not any(
            "e4" not in {a.activity_id for a in o} for o in options if status == "ok")
        row["success"] = row["status_correct"]
        return row
    if x["status"] == "ask_with_options":
        row["status_correct"] = status in ("ok", "ask") and bool(options)
        row["success"] = row["status_correct"] and all(all(c.values()) for c in checked) and not row["invented_places"]
        return row
    row["status_correct"] = status in ("ok", "ask") and bool(options)
    satisfying = [c for c in checked if all(c.values())]
    row["unknown_flagged"] = out.get("unverified_flag") if x["unknown_expected"] else None
    row["success"] = (row["status_correct"] and bool(satisfying) and all(c["feasible"] and c["kept"] for c in checked)
                      and not row["invented_places"] and (out.get("unverified_flag") or not x["unknown_expected"]))
    return row


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (typ, m), g in df.groupby(["type", "method"], sort=False):
        r = {"type": typ, "method": m, "cases": len(g), "success": round(g.success.mean(), 3),
             "status_correct": round(g.status_correct.mean(), 3)}
        if typ == "setup":
            ok = g[g.get("hard_violations").notna()] if "hard_violations" in g else g.iloc[0:0]
            r |= {"extraction_acc": round(g.extraction_acc.mean(), 3),
                  "feasible": round(ok.c_feasible.mean(), 3) if len(ok) else None,
                  "checks_passed": round(g.checks_passed.dropna().mean(), 3) if "checks_passed" in g else None,
                  "pref_match": round(g.pref_match.dropna().mean(), 3) if g.pref_match.notna().any() else None}
        else:
            r |= {"options_feasible": round(g.options_feasible.dropna().astype(float).mean(), 3)
                  if g.options_feasible.notna().any() else None}
        r |= {"avg_tokens": round(g.tokens.mean()), "avg_latency_s": round(g.latency_s.mean(), 1),
              "avg_llm_calls": round(g.llm_calls.mean(), 2)}
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", default="direct,structured,planb,planb_gold")
    ap.add_argument("--scenarios", default="")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--run-name", default=None)
    args = ap.parse_args()
    llm = LLMClient(provider="mock") if args.mock else LLMClient()
    methods = [m for m in args.methods.split(",") if m]
    only = {x for x in args.scenarios.split(",") if x}
    files = sorted(SCEN.glob("t*.json")) + sorted(SCEN.glob("e0*.json"))
    scen = [json.loads(f.read_text()) for f in files]
    scen = [s for s in scen if not only or s["id"] in only]
    run = args.run_name or ("mock-trip" if llm.is_mock else datetime.now().strftime("trip-%Y%m%d-%H%M%S"))
    out_dir = ROOT / "evaluation" / "results" / run
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"LLM: {llm.describe()} | methods {methods} | {len(scen)} scenarios -> {out_dir}")
    rows, raw = [], []
    for s in scen:
        for m in methods:
            try:
                out = run_setup(s, m, llm) if s["type"] == "trip_setup" else run_edit(s, m, llm)
            except Exception as ex:  # quota exhausted or provider error: stop cleanly, cached calls are kept
                print(f"  {s['id']} {m}: ERROR {str(ex)[:200]}")
                if "quota" in str(ex).lower():
                    break
                continue
            row = score_setup(s, out) if s["type"] == "trip_setup" else score_edit(s, out)
            rows.append(row)
            raw.append({"scenario": s["id"], "method": m, "status": out.get("status"), "understood": out.get("understood"),
                        "raw_text": out.get("raw_text"), "message": out.get("message"),
                        "itinerary": [a.model_dump(mode="json") for a in out.get("acts", [])],
                        "options": [[a.model_dump(mode="json") for a in o] for o in out.get("options", [])],
                        "unplaceable": out.get("unplaceable")})
            print(f"  {s['id']:38s} {m:11s} status={str(row['status']):18s} success={row['success']}")
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "per_case.csv", index=False)
    summ = summarize(df)
    summ.to_csv(out_dir / "summary.csv", index=False)
    with open(out_dir / "raw_outputs.jsonl", "w") as f:
        for r in raw:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    head = f"# Trip-setup and edit evaluation `{run}`\n\n- LLM: {llm.describe()}\n- Scenarios: {len(scen)}\n"
    if llm.is_mock:
        head += "\n> **MOCK RUN — pipeline test only.** Baselines return empty answers; NOT experimental results.\n"
    (out_dir / "summary.md").write_text(head + "\n" + summ.to_markdown(index=False) + "\n")
    print("\n" + summ.to_string(index=False))


if __name__ == "__main__":
    main()
