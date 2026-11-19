"""Turn a DisruptionEvent into explicit, checkable constraints (EventContext)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from .models import Booking, DisruptionEvent, Trip


@dataclass
class BlockedWindow:
    start: datetime
    end: datetime
    scope: Literal["outdoor", "all"]
    reason: str


@dataclass
class Closure:
    place_id: str
    start: Optional[datetime]  # None = open-ended
    end: Optional[datetime]
    reason: str


@dataclass
class EventContext:
    event: Optional[DisruptionEvent] = None
    blocked: list[BlockedWindow] = field(default_factory=list)
    closures: list[Closure] = field(default_factory=list)
    new_end_date: Optional[date] = None
    # activity_id -> (new_start, new_end) imposed by the outside world (e.g. venue moved a reservation)
    forced_moves: dict[str, tuple[datetime, datetime]] = field(default_factory=dict)
    # locked activities the user's own request explicitly allows to change (e.g. return flight on extension)
    released_locks: set[str] = field(default_factory=set)
    missing_information: list[str] = field(default_factory=list)

    def is_closed(self, place_id: str, start: datetime, end: datetime) -> Optional[Closure]:
        for c in self.closures:
            if c.place_id != place_id:
                continue
            if (c.start is None or end > c.start) and (c.end is None or start < c.end):
                return c
        return None

    def blocking(self, start: datetime, end: datetime, indoor: bool) -> Optional[BlockedWindow]:
        for w in self.blocked:
            if w.scope == "outdoor" and indoor:
                continue
            if start < w.end and end > w.start:
                return w
        return None


def _parse_dt(value) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _parse_date(value) -> Optional[date]:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def build_context(event: Optional[DisruptionEvent], trip: Trip, bookings: list[Booking]) -> EventContext:
    ctx = EventContext(event=event)
    if event is None:
        return ctx
    et = event.event_type
    p = event.parameters
    start, end = event.affected_start, event.affected_end

    if et in ("weather_change", "transport_delay"):
        if start is not None and end is None and p.get("delay_minutes"):
            end = start + timedelta(minutes=int(p["delay_minutes"]))
        if start is None or end is None:
            ctx.missing_information.append("受影响的时间范围（开始/结束时间）")
        else:
            scope = "outdoor" if et == "weather_change" else "all"
            ctx.blocked.append(BlockedWindow(start, end, scope, event.description or et))

    elif et == "place_closed":
        if not event.affected_place_ids:
            ctx.missing_information.append("关闭的地点")
        for pid in event.affected_place_ids:
            ctx.closures.append(Closure(pid, start, end, event.description or "place closed"))

    elif et in ("trip_extension", "trip_shortening"):
        new_end = _parse_date(p.get("new_end_date"))
        if new_end is None:
            ctx.missing_information.append("新的返程日期")
        else:
            ctx.new_end_date = new_end
            # The user's own request explicitly allows moving the return flight.
            for a in trip.activities:
                if a.category == "flight_departure":
                    ctx.released_locks.add(a.activity_id)

    elif et == "reservation_change":
        bid = p.get("booking_id")
        new_start, new_end = _parse_dt(p.get("new_start")), _parse_dt(p.get("new_end"))
        booking = next((b for b in bookings if b.booking_id == bid), None)
        if booking is None:
            ctx.missing_information.append("被改期的预约（booking_id）")
        elif new_start is None:
            ctx.missing_information.append("预约的新时间")
        else:
            for aid in booking.linked_activity_ids:
                act = trip.activity(aid)
                if act is None:
                    continue
                duration = act.end_at - act.start_at
                ctx.forced_moves[aid] = (new_start, new_start + duration)
                ctx.released_locks.add(aid)
    return ctx
