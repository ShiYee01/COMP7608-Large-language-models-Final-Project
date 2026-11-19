"""Shared evaluation utilities: scenario loading and the common output format."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from planb.data import DATA, World, load_world  # noqa: E402
from planb.models import Activity, Booking, DisruptionEvent, Trip  # noqa: E402

SCENARIO_DIR = ROOT / "evaluation" / "scenarios"


@dataclass
class Scenario:
    raw: dict
    trip: Trip
    bookings: list[Booking]
    world: World
    gold_event: DisruptionEvent

    @property
    def id(self) -> str:
        return self.raw["scenario_id"]

    @property
    def gt(self) -> dict:
        return self.raw["ground_truth"]


def _set_path(obj: dict, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    for p in parts[:-1]:
        obj = obj.setdefault(p, {})
    obj[parts[-1]] = value


def load_scenario(path: Path, world: World | None = None) -> Scenario:
    raw = json.loads(Path(path).read_text())
    trip_d = json.loads((DATA / "sample_trips/tokyo_3day.json").read_text())
    bookings_d = json.loads((DATA / "sample_bookings/tokyo_bookings.json").read_text())
    ov = raw.get("overrides", {})
    for aid, changes in ov.get("activities", {}).items():
        act = next(a for a in trip_d["activities"] if a["activity_id"] == aid)
        for k, v in changes.items():
            _set_path(act, k, v)
    for bid, changes in ov.get("bookings", {}).items():
        b = next(x for x in bookings_d if x["booking_id"] == bid)
        for k, v in changes.items():
            _set_path(b, k, v)
    return Scenario(raw=raw, trip=Trip.model_validate(trip_d),
                    bookings=[Booking.model_validate(b) for b in bookings_d],
                    world=world or load_world(),
                    gold_event=DisruptionEvent.model_validate({**raw["gold_event"], "source": "gold"}))


def load_scenarios(split: str | None = None, ids: list[str] | None = None) -> list[Scenario]:
    world = load_world()
    out = []
    for p in sorted(SCENARIO_DIR.glob("*.json")):
        s = load_scenario(p, world)
        if split and s.raw.get("split") != split:
            continue
        if ids and s.id not in ids:
            continue
        out.append(s)
    return out


@dataclass
class MethodOutput:
    method: str
    status: Optional[str] = None  # ok / infeasible / needs_information
    trip: Optional[Trip] = None
    affected_booking_ids: list[str] = field(default_factory=list)
    cost_minor: Optional[int] = None
    json_ok: bool = True
    format_errors: int = 0
    latency_s: float = 0.0
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    parse_method: str = ""
    parsed_event: Optional[dict] = None
    raw_text: str = ""
    error: str = ""


def _parse_dt(s: str, world: World) -> datetime:
    dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=world.tz)


def _normalize_ids(items: list[dict], original: Trip) -> list[str | None]:
    """Neutral ID normalisation for baseline output.

    Small models often re-emit an existing activity under a new id (e.g. ``a12_new``). Scoring that as
    "original deleted + new item added" would unfairly flag locked items as removed. An item whose id is
    unknown (or already used) is matched to an original activity at the same place_id that the output
    does not otherwise contain (one-to-one, in output order).
    """
    orig_ids = [a.activity_id for a in original.activities]
    raw = [str(it.get("activity_id")) if isinstance(it, dict) and it.get("activity_id") else None for it in items]
    used, out = set(), []
    for r in raw:
        if r in orig_ids and r not in used:
            used.add(r)
            out.append(r)
        else:
            out.append(None)
    for i, it in enumerate(items):
        if out[i] is not None or not isinstance(it, dict):
            continue
        pid = str(it.get("place_id", ""))
        match = next((a.activity_id for a in original.activities
                      if a.place_id == pid and a.activity_id not in used), None)
        if match:
            used.add(match)
            out[i] = match
        else:
            out[i] = raw[i] if raw[i] and raw[i] not in used and raw[i] not in orig_ids else None
            if out[i]:
                used.add(out[i])
    return out


def itinerary_to_trip(items: list[dict], original: Trip, world: World) -> tuple[Trip, int]:
    """Convert an LLM itinerary list to a Trip. Returns (trip, number of malformed items)."""
    trip = original.model_copy(deep=True)
    orig = {a.activity_id: a for a in original.activities}
    ids = _normalize_ids(items or [], original)
    acts, errors = [], 0
    for i, it in enumerate(items or []):
        try:
            start, end = _parse_dt(it["start_at"], world), _parse_dt(it["end_at"], world)
            pid = str(it.get("place_id", ""))
            aid = ids[i] or f"new_{i}"
            if aid in orig:
                base = orig[aid]
                acts.append(base.model_copy(update={"place_id": pid, "start_at": start, "end_at": end,
                                                    "title": it.get("title") or base.title}))
            else:
                place = world.place(pid)
                cat = "visit"
                if place and place.category == "food":
                    cat = "meal"
                elif place and place.category == "airport":
                    cat = "flight_departure"
                acts.append(Activity(activity_id=aid, place_id=pid, title=it.get("title") or pid,
                                     start_at=start, end_at=end, category=cat))
        except Exception:
            errors += 1
    trip.activities = acts
    return trip, errors
