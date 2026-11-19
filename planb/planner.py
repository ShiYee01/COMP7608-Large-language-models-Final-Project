"""Greedy deterministic scheduling helpers.

Used for (a) initial itinerary generation (Story A) and (b) filling newly freed
time (e.g. the extra day after a trip extension). The LLM only extracts
preferences; the schedule itself is built here so it is always checkable.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from .data import World
from .events import EventContext
from .models import Activity, Budget, Preferences, Trip, new_id
from .validator import _within_opening

SKIP_CATEGORIES = {"airport", "hotel", "food"}
PACE_VISITS = {"relaxed": 3, "normal": 4, "packed": 5}


def _round_up(dt: datetime, minutes: int = 15) -> datetime:
    extra = (-dt.minute) % minutes
    return (dt + timedelta(minutes=extra)).replace(second=0, microsecond=0)


def interest_score(place_tags: list[str], interests: list[str]) -> int:
    return len(set(place_tags) & set(interests))


def place_fits(world: World, ctx: EventContext, place_id: str, start: datetime, end: datetime) -> bool:
    """Opening hours KNOWN and satisfied, not closed, not blocked by the event."""
    place = world.place(place_id)
    if place is None:
        return False
    probe = Activity(activity_id="probe", place_id=place_id, title="", start_at=start, end_at=end)
    if _within_opening(probe, world) is not True:
        return False
    if ctx.is_closed(place_id, start, end) or ctx.blocking(start, end, place.indoor):
        return False
    return True


def fill_window(
    trip: Trip,
    world: World,
    ctx: EventContext,
    window_start: datetime,
    window_end: datetime,
    prev_place: Optional[str],
    next_place: Optional[str],
    max_items: int,
    used_places: set[str],
) -> list[Activity]:
    """Greedily add visits into [window_start, window_end]."""
    added: list[Activity] = []
    cursor, prev = window_start, prev_place
    interests = trip.preferences.interests
    while len(added) < max_items:
        best = None
        for place in world.places.values():
            if place.category in SKIP_CATEGORIES or place.place_id in used_places:
                continue
            travel = 0 if prev is None else world.travel_minutes(prev, place.place_id)
            if travel is None:
                continue
            start = _round_up(cursor + timedelta(minutes=travel))
            end = start + timedelta(minutes=place.suggested_visit_minutes)
            back = 0 if next_place is None else world.travel_minutes(place.place_id, next_place)
            if back is None or end + timedelta(minutes=back) > window_end:
                continue
            if not place_fits(world, ctx, place.place_id, start, end):
                continue
            score = interest_score(place.tags, interests) * 10 - travel / 5
            if best is None or score > best[0]:
                best = (score, place, start, end)
        if best is None:
            break
        _, place, start, end = best
        act = Activity(activity_id=new_id("act"), place_id=place.place_id, title=place.name_zh or place.name,
                       start_at=start, end_at=end, category="visit",
                       estimated_cost_minor=place.entry_cost_minor, notes="PlanB 推荐")
        added.append(act)
        used_places.add(place.place_id)
        cursor, prev = end, place.place_id
    return added


def generate_itinerary(
    world: World,
    destination: str,
    start_date: date,
    end_date: date,
    preferences: Preferences,
    budget: Budget | None = None,
    party_size: int = 1,
    hotel_place_id: str | None = "hotel_shinjuku",
    arrival_at: datetime | None = None,
    departure_at: datetime | None = None,
    airport_place_id: str = "haneda_airport",
) -> Trip:
    """Story A: build a structured initial itinerary from the static POI catalogue."""
    tz = world.tz
    trip = Trip(trip_id=new_id("trip"), title=f"{destination} {start_date}~{end_date}", destination=destination,
                start_date=start_date, end_date=end_date, party_size=party_size,
                budget=budget or Budget(), preferences=preferences, hotel_place_id=hotel_place_id)
    acts: list[Activity] = []
    if arrival_at:
        acts.append(Activity(activity_id=new_id("act"), place_id=airport_place_id, title="抵达机场",
                             start_at=arrival_at, end_at=arrival_at + timedelta(minutes=30),
                             category="flight_arrival", is_locked=True))
    if departure_at:
        acts.append(Activity(activity_id=new_id("act"), place_id=airport_place_id, title="返程航班值机",
                             start_at=departure_at - timedelta(hours=2), end_at=departure_at,
                             category="flight_departure", is_locked=True))
    ctx = EventContext()
    used: set[str] = set()
    h, m = map(int, preferences.day_start.split(":"))
    eh, em = map(int, preferences.day_end.split(":"))
    d = start_date
    while d <= end_date:
        ws = datetime(d.year, d.month, d.day, max(h, 9), m, tzinfo=tz)
        we = datetime(d.year, d.month, d.day, min(eh, 19), em if eh <= 19 else 0, tzinfo=tz)
        prev, nxt = hotel_place_id, hotel_place_id
        if arrival_at and arrival_at.astimezone(tz).date() == d:
            ws, prev = arrival_at + timedelta(minutes=30), airport_place_id
        if departure_at and departure_at.astimezone(tz).date() == d:
            we, nxt = departure_at - timedelta(hours=2), airport_place_id
        acts += fill_window(trip, world, ctx, ws, we, prev, nxt, PACE_VISITS[preferences.pace], used)
        d += timedelta(days=1)
    trip.activities = sorted(acts, key=lambda a: a.start_at)
    return trip
