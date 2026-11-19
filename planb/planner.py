"""Greedy deterministic scheduling helpers.

Used for (a) initial itinerary generation (Story A) and (b) filling newly freed
time (e.g. the extra day after a trip extension). The LLM only extracts
preferences; the schedule itself is built here so it is always checkable.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Optional

from .data import World
from .events import EventContext
from .models import Activity, Booking, BookingPolicy, Budget, Preferences, Trip, ValidationResult, new_id
from .validator import _within_opening, validate

if TYPE_CHECKING:
    from .trip_request import TripRequest

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


# ---------------------------------------------------------------------------
# Planning from a natural-language TripRequest (trip setup by conversation)
# ---------------------------------------------------------------------------

@dataclass
class TripPlan:
    trip: Trip
    bookings: list[Booking]
    report: list[str]
    validation: ValidationResult


DAY_START, DAY_END = time(9, 0), time(19, 0)
FLIGHT_CATEGORIES = ("flight_arrival", "flight_departure")


def _minor(cny: Optional[float]) -> Optional[int]:
    return None if cny is None else int(round(cny * 100))


def _day_frame(world: World, d: date, acts: list[Activity], hotel: str):
    """Usable window of a day and where it starts/ends (hotel, or the airport on travel days)."""
    tz = world.tz
    ws, we = datetime.combine(d, DAY_START, tzinfo=tz), datetime.combine(d, DAY_END, tzinfo=tz)
    start_place = end_place = hotel
    for a in acts:
        if world.local(a.start_at).date() != d:
            continue
        if a.category == "flight_arrival":
            ws, start_place = max(ws, a.end_at), a.place_id
        elif a.category == "flight_departure":
            we, end_place = min(we, a.start_at), a.place_id
    return ws, we, start_place, end_place


def _gaps(world: World, d: date, acts: list[Activity], hotel: str):
    """Free intervals of day d between fixed activities: (start, end, prev_place, next_place)."""
    ws, we, prev, end_place = _day_frame(world, d, acts, hotel)
    fixed = sorted((a for a in acts if world.local(a.start_at).date() == d and a.category not in FLIGHT_CATEGORIES),
                   key=lambda a: a.start_at)
    cursor, gaps = ws, []
    for a in fixed:
        gap_end = min(a.start_at, we)
        if gap_end > cursor:
            gaps.append((cursor, gap_end, prev, a.place_id))
        cursor, prev = max(cursor, a.end_at), a.place_id
    if we > cursor:
        gaps.append((cursor, we, prev, end_place))
    return gaps


def _fit(world: World, ctx: EventContext, place_id: str, gap) -> Optional[tuple[datetime, datetime, int]]:
    """Earliest feasible slot for a place inside a gap, and the extra travel it adds."""
    gs, ge, prev, nxt = gap
    place = world.place(place_id)
    t_in = world.travel_minutes(prev, place_id) if prev else 0
    t_out = world.travel_minutes(place_id, nxt) if nxt else 0
    if place is None or t_in is None or t_out is None:
        return None
    direct = world.travel_minutes(prev, nxt) if (prev and nxt) else 0
    start = _round_up(gs + timedelta(minutes=t_in))
    while True:
        end = start + timedelta(minutes=place.suggested_visit_minutes)
        if end + timedelta(minutes=t_out) > ge:
            return None
        if place_fits(world, ctx, place_id, start, end):
            return start, end, t_in + t_out - (direct or 0)
        start += timedelta(minutes=15)


def plan_trip(world: World, req: "TripRequest") -> TripPlan:
    """Build an initial itinerary around what the traveller said they booked and want.

    1. Stated bookings become locked activities (flights, tickets, reservations) and Booking records;
       prices and rules that were not stated stay unknown.
    2. Must-visit places go into the free slot that adds the least travel (opening hours checked).
    3. Remaining time is filled greedily by preference tags (`fill_window`), never with avoided places.
    """
    missing = req.missing_required()
    if missing:
        raise ValueError("还缺少：" + "、".join(missing))
    tz = world.tz
    hotel = req.hotel.place_id if req.hotel and req.hotel.place_id else "hotel_shinjuku"
    prefs = Preferences(interests=list(req.interests), pace=req.pace or "normal")
    trip = Trip(trip_id=new_id("trip"), title=f"东京 {req.start_date:%m/%d}–{req.end_date:%m/%d}", destination="Tokyo",
                start_date=req.start_date, end_date=req.end_date, preferences=prefs, hotel_place_id=hotel,
                budget=Budget(amount_minor=_minor(req.budget_cny)) if req.budget_cny else Budget())
    acts: list[Activity] = []
    bookings: list[Booking] = []
    report: list[str] = []

    def name(pid: str) -> str:
        p = world.place(pid)
        return (p.name_zh or p.name) if p else pid

    for b in sorted(req.bookings, key=lambda x: x.start):
        if not (req.start_date <= world.local(b.start).date() <= req.end_date):
            report.append(f"预订「{b.title}」的日期不在旅行日期内，未排入")
            continue
        policy = BookingPolicy(change_fee_minor=_minor(b.change_fee_cny),
                               refund_on_cancel_minor=(_minor(b.price_cny) if b.refundable and b.price_cny is not None
                                                       else 0 if b.refundable is False else None))
        if b.kind == "flight_arrival":
            a = Activity(activity_id=new_id("act"), place_id=b.place_id, title=f"抵达{name(b.place_id)}",
                         start_at=b.start, end_at=b.start + timedelta(minutes=30), category="flight_arrival", is_locked=True)
            bk = Booking(booking_id=new_id("bk"), booking_type="flight",
                         title=f"去程航班（{world.local(b.start):%m/%d %H:%M} 抵达{name(b.place_id)}）", place_id=b.place_id,
                         service_start=b.start, service_end=b.start)
        elif b.kind == "flight_departure":
            a = Activity(activity_id=new_id("act"), place_id=b.place_id,
                         title=f"{name(b.place_id)}返程（{world.local(b.start):%H:%M} 起飞）",
                         start_at=b.start - timedelta(hours=2), end_at=b.start, category="flight_departure", is_locked=True)
            bk = Booking(booking_id=new_id("bk"), booking_type="flight",
                         title=f"返程航班（{world.local(b.start):%m/%d %H:%M} 从{name(b.place_id)}起飞）", place_id=b.place_id,
                         service_start=b.start, service_end=b.start)
        else:
            place = world.place(b.place_id)
            minutes = 90 if b.kind == "restaurant" else place.suggested_visit_minutes
            end = b.end or b.start + timedelta(minutes=minutes)
            a = Activity(activity_id=new_id("act"), place_id=b.place_id, title=f"{name(b.place_id)}（已预订）",
                         start_at=b.start, end_at=end, category="meal" if b.kind == "restaurant" else "visit",
                         is_locked=True, priority=3, notes="你已预订")
            bk = Booking(booking_id=new_id("bk"), booking_type=b.kind, title=f"{name(b.place_id)} {world.local(b.start):%m/%d %H:%M}",
                         place_id=b.place_id, service_start=b.start, service_end=end)
        bk.paid_minor, bk.policy, bk.linked_activity_ids = _minor(b.price_cny), policy, [a.activity_id]
        acts.append(a)
        bookings.append(bk)

    if req.hotel and req.hotel.place_id:
        ci, co = req.hotel.check_in or req.start_date, req.hotel.check_out or req.end_date
        nights = max((co - ci).days, 0)
        price = req.hotel.price_per_night_cny
        bookings.append(Booking(
            booking_id=new_id("bk"), booking_type="hotel", title=f"{name(hotel)}（{ci:%m/%d} 入住 – {co:%m/%d} 退房）",
            place_id=hotel, service_start=datetime.combine(ci, time(15), tzinfo=tz),
            service_end=datetime.combine(co, time(11), tzinfo=tz),
            paid_minor=_minor(price * nights) if price is not None else None))
    if not any(b.kind == "flight_arrival" for b in req.bookings):
        report.append("没有提到去程航班：第一天从酒店 09:00 开始安排")
    if not any(b.kind == "flight_departure" for b in req.bookings):
        report.append("没有提到返程航班：最后一天安排到 19:00")

    ctx = EventContext()
    days = [req.start_date + timedelta(days=i) for i in range((req.end_date - req.start_date).days + 1)]
    cap = PACE_VISITS[prefs.pace]
    count = {d: sum(1 for a in acts if a.category == "visit" and world.local(a.start_at).date() == d) for d in days}

    placed_must = 0
    for mv in req.must_visit:
        best = None
        for d in ([mv.day] if mv.day in days else days):
            if count[d] >= cap:
                continue
            for gap in _gaps(world, d, acts, hotel):
                r = _fit(world, ctx, mv.place_id, gap)
                if r and (best is None or (r[2], r[0]) < (best[2], best[0])):
                    best = (*r, d)
        if best is None:
            p = world.place(mv.place_id)
            why = "营业时间未知，无法确认" if p.opening_hours is None else "营业时间或剩余时间不够"
            report.append(f"没能排进「{name(mv.place_id)}」：{why}")
            continue
        start, end, _, d = best
        acts.append(Activity(activity_id=new_id("act"), place_id=mv.place_id, title=name(mv.place_id), start_at=start,
                             end_at=end, priority=3, estimated_cost_minor=world.place(mv.place_id).entry_cost_minor,
                             notes="你想去的地点"))
        count[d] += 1
        placed_must += 1

    used = {a.place_id for a in acts} | set(req.avoid)
    recommended = 0
    for d in days:
        for gap in _gaps(world, d, acts, hotel):
            remaining = cap - count[d]
            if remaining <= 0:
                break
            added = fill_window(trip, world, ctx, gap[0], gap[1], gap[2], gap[3], remaining, used)
            acts += added
            count[d] += len(added)
            recommended += len(added)

    trip.activities = sorted(acts, key=lambda a: a.start_at)
    validation = validate(trip, world)
    n_booked = sum(1 for b in bookings if b.linked_activity_ids)
    report.insert(0, f"共安排 {sum(count.values())} 个景点：你想去的 {placed_must} 个，按喜好推荐的 {recommended} 个；"
                     f"已预订的 {n_booked} 项已锁定")
    return TripPlan(trip=trip, bookings=bookings, report=report, validation=validation)
