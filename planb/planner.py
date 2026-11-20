"""Greedy deterministic scheduling helpers.

Used for (a) initial itinerary generation (Story A) and (b) filling newly freed
time (e.g. the extra day after a trip extension). The LLM only extracts
preferences; the schedule itself is built here so it is always checkable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
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
    unplaceable: list[str] = field(default_factory=list)  # must-visits that could not be scheduled (reported)


DAY_START, DAY_END = time(9, 0), time(19, 30)
FLIGHT_CATEGORIES = ("flight_arrival", "flight_departure")
# (title, earliest start, latest end, minutes, preferred start)
MEALS = [("午餐", time(11, 30), time(13, 30), 60, time(12, 0)),
         ("晚餐", time(17, 30), time(20, 0), 90, time(18, 0))]
MEAL_NOTE = "附近自由用餐"


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
        free = a.category == "free_time"  # a meal slot "nearby": no travel to it, keep the previous place
        if gap_end > cursor:
            gaps.append((cursor, gap_end, prev, None if free else a.place_id))
        cursor = max(cursor, a.end_at)
        if not free:
            prev = a.place_id
    if we > cursor:
        gaps.append((cursor, we, prev, end_place))
    return gaps


def add_meal_slots(world: World, days: list[date], acts: list[Activity], hotel: str) -> list[Activity]:
    """Reserve a free lunch and dinner slot per day, unless a booked meal or the flights leave no room."""
    tz, added = world.tz, []
    for d in days:
        day_acts = [a for a in acts + added if world.local(a.start_at).date() == d]
        lo_bound = max([a.end_at for a in day_acts if a.category == "flight_arrival"],
                       default=datetime.combine(d, time(0), tzinfo=tz))
        hi_bound = min([a.start_at for a in day_acts if a.category == "flight_departure"],
                       default=datetime.combine(d, time(23, 59), tzinfo=tz))
        for title, lo, hi, minutes, pref in MEALS:
            wlo, whi = datetime.combine(d, lo, tzinfo=tz), datetime.combine(d, hi, tzinfo=tz)
            if any(a.category == "meal" and a.start_at < whi and a.end_at > wlo for a in day_acts):
                continue  # the traveller already booked a meal in this window
            p = datetime.combine(d, pref, tzinfo=tz)
            starts = [wlo + timedelta(minutes=15 * i) for i in range(int((whi - wlo).total_seconds() // 900) + 1)]
            for start in sorted(starts, key=lambda x: abs((x - p).total_seconds())):
                end = start + timedelta(minutes=minutes)
                if start < lo_bound or end > hi_bound or end > whi:
                    continue
                if any(a.start_at < end and a.end_at > start for a in day_acts):
                    continue
                meal = Activity(activity_id=new_id("act"), place_id=hotel, title=f"{title}（自由安排）",
                                start_at=start, end_at=end, category="free_time", notes=MEAL_NOTE)
                added.append(meal)
                day_acts.append(meal)
                break
    return added


def settle_meal_slots(world: World, trip: Trip) -> list[str]:
    """A meal slot must not eat the travel time to the next stop (e.g. dinner right before airport check-in).
    Move such a slot earlier inside its window, or drop it and say so."""
    notes: list[str] = []
    windows = {title: (lo, hi) for title, lo, hi, _, _ in MEALS}
    for _ in range(10):
        bad = [v for v in validate(trip, world).hard_violations if v.rule == "TRAVEL_TIME" and len(v.activity_ids) >= 2]
        if not bad:
            break
        a, b = trip.activity(bad[0].activity_ids[0]), trip.activity(bad[0].activity_ids[1])
        meals = [m for m in trip.activities if m.category == "free_time" and m.start_at < b.start_at and m.end_at > a.end_at]
        if not meals:
            break
        m = meals[-1]
        title = next((t for t in windows if t in m.title), None)
        lo = datetime.combine(world.local(m.start_at).date(), windows[title][0], tzinfo=world.tz) if title else m.start_at
        dur, moved = m.end_at - m.start_at, False
        start = m.start_at - timedelta(minutes=15)
        while start >= max(lo, a.end_at):
            m.start_at, m.end_at = start, start + dur
            others = [x for x in trip.activities if x is not m]
            if not any(x.start_at < m.end_at and x.end_at > m.start_at for x in others) and not any(
                    v.rule == "TRAVEL_TIME" and m.activity_id not in v.activity_ids and {a.activity_id, b.activity_id} <= set(v.activity_ids)
                    for v in validate(trip, world).hard_violations):
                moved = True
                break
            start -= timedelta(minutes=15)
        if not moved:
            trip.activities = [x for x in trip.activities if x is not m]
            notes.append(f"{world.local(m.start_at):%m月%d日}{(title or '用餐')}时间不够（要赶去下一站），没有单独留出")
    return notes


def drop_unfit_suggestions(world: World, trip: Trip) -> list[Activity]:
    """Last safety net: a stop PlanB itself suggested must never cause a hard violation (e.g. it was placed
    right before a meal slot and the onward travel to the airport no longer fits once that slot is settled).
    Remove such suggestions; the user's own places and bookings are never removed here."""
    dropped: list[Activity] = []
    for _ in range(20):
        ids = {i for v in validate(trip, world).hard_violations for i in v.activity_ids}
        bad = [a for a in trip.sorted_activities()
               if a.activity_id in ids and a.category == "visit" and not a.is_locked and a.notes == "PlanB 推荐"]
        if not bad:
            break
        trip.activities = [x for x in trip.activities if x is not bad[-1]]
        dropped.append(bad[-1])
    return dropped


def place_meal_slots(world: World, trip: Trip) -> None:
    """Label each free meal slot with the place it follows (shown as 'nearby'; it adds no travel)."""
    by_day: dict = {}
    for a in trip.sorted_activities():
        by_day.setdefault(world.local(a.start_at).date(), []).append(a)
    for d, items in by_day.items():
        last = trip.hotel_place_id
        for a in items:
            if a.category == "free_time":
                a.place_id = last or a.place_id
            else:
                last = a.place_id


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
    acts += add_meal_slots(world, days, acts, hotel)
    cap = PACE_VISITS[prefs.pace]
    count = {d: sum(1 for a in acts if a.category == "visit" and world.local(a.start_at).date() == d) for d in days}

    placed_must, unplaceable = 0, []
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
            unplaceable.append(mv.place_id)
            continue
        start, end, _, d = best
        acts.append(Activity(activity_id=new_id("act"), place_id=mv.place_id, title=name(mv.place_id), start_at=start,
                             end_at=end, priority=3, estimated_cost_minor=world.place(mv.place_id).entry_cost_minor,
                             notes="你想去的地点"))
        count[d] += 1
        placed_must += 1

    used = {a.place_id for a in acts if a.category != "free_time"} | set(req.avoid)
    recommended = 0
    for d in days:
        cursor = None  # fill in time order, recomputing gaps so travel always starts from the real previous stop
        while cap - count[d] > 0:
            gaps = [g for g in _gaps(world, d, acts, hotel) if cursor is None or g[0] >= cursor]
            if not gaps:
                break
            gap = gaps[0]
            added = fill_window(trip, world, ctx, gap[0], gap[1], gap[2], gap[3], cap - count[d], used)
            acts += added
            count[d] += len(added)
            recommended += len(added)
            cursor = gap[1]

    trip.activities = sorted(acts, key=lambda a: a.start_at)
    place_meal_slots(world, trip)
    report += settle_meal_slots(world, trip)
    trip.activities = sorted(trip.activities, key=lambda a: a.start_at)
    dropped = drop_unfit_suggestions(world, trip)
    for a in dropped:
        count[world.local(a.start_at).date()] -= 1
        recommended -= 1
        report.append(f"去掉了推荐的「{a.title}」：{world.local(a.start_at):%m月%d日}之后赶下一站的交通时间不够")
    validation = validate(trip, world)
    n_booked = sum(1 for b in bookings if b.linked_activity_ids)
    n_meals = sum(1 for a in trip.activities if a.category == "free_time")
    report.insert(0, f"共安排 {sum(count.values())} 个景点：你想去的 {placed_must} 个，按喜好推荐的 {recommended} 个；"
                     f"已预订的 {n_booked} 项已锁定；留了 {n_meals} 段用餐时间（自由安排）")
    return TripPlan(trip=trip, bookings=bookings, report=report, validation=validation, unplaceable=unplaceable)
