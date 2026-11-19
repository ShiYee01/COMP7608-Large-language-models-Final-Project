"""Booking dependency analysis (PROJECT_CONTEXT.md §10.1).

Compares the original trip with a candidate trip (plus event context) and decides,
for every booking, one of: unaffected / change_required / potentially_affected / unknown.
"""
from __future__ import annotations

from .data import World
from .events import EventContext
from .models import Booking, BookingImpact, Trip


def analyze_booking_impact(
    original: Trip, candidate: Trip, bookings: list[Booking], world: World, ctx: EventContext | None = None
) -> list[BookingImpact]:
    ctx = ctx or EventContext()
    old_end = original.end_date
    new_end = candidate.end_date
    cand = {a.activity_id: a for a in candidate.activities if a.status == "planned"}
    impacts: list[BookingImpact] = []

    for b in bookings:
        if b.service_start is None or b.service_end is None:
            impacts.append(BookingImpact(booking_id=b.booking_id, status="unknown",
                                         reason="订单缺少服务时间，无法判断是否受影响"))
            continue

        if b.booking_type == "hotel":
            checkout = world.local(b.service_end).date()
            if new_end > checkout:
                impacts.append(BookingImpact(
                    booking_id=b.booking_id, status="change_required", required_action="extend_stay",
                    reason=f"新返程日 {new_end} 晚于退房日 {checkout}，需要续住 {(new_end - checkout).days} 晚",
                    target_start=b.service_end, target_end=None))
            elif new_end < checkout:
                impacts.append(BookingImpact(
                    booking_id=b.booking_id, status="change_required", required_action="shorten_stay",
                    reason=f"新返程日 {new_end} 早于退房日 {checkout}，需要提前退房 {(checkout - new_end).days} 晚"))
            else:
                impacts.append(BookingImpact(booking_id=b.booking_id, status="unaffected", reason="入住/退房日期不变"))
            continue

        # Bookings tied to activities (flights, attractions, restaurants)
        linked = [original.activity(aid) for aid in b.linked_activity_ids]
        linked = [a for a in linked if a is not None]
        if not linked:
            impacts.append(BookingImpact(booking_id=b.booking_id, status="unknown",
                                         reason="订单没有关联任何活动，无法判断"))
            continue

        provider_initiated = False
        if ctx.event is not None and ctx.event.event_type == "place_closed" and b.place_id in ctx.event.affected_place_ids:
            provider_initiated = True

        changed = []
        removed = []
        for a in linked:
            new = cand.get(a.activity_id)
            if new is None or new.place_id != a.place_id:
                removed.append(a)  # dropped or replaced by another place -> booking no longer used
            elif new.start_at != a.start_at:
                # Attraction / restaurant slots: still fine if the new start is inside the booked entry window.
                in_slot = (b.booking_type in ("attraction", "restaurant")
                           and b.service_start <= new.start_at <= b.service_end)
                if not in_slot:
                    changed.append((a, new))

        forced = any(a.activity_id in ctx.forced_moves for a in linked)
        if forced and not removed:
            # The provider itself moved the reservation: no action is needed from the traveller.
            impacts.append(BookingImpact(booking_id=b.booking_id, status="unaffected",
                                         reason="预约时间已由商家调整，行程已同步，无需额外操作", provider_initiated=True))
        elif removed:
            impacts.append(BookingImpact(
                booking_id=b.booking_id, status="change_required", required_action="cancel",
                reason=("场馆关闭，" if provider_initiated else "") + f"关联活动「{removed[0].title}」被取消",
                provider_initiated=provider_initiated))
        elif changed:
            old, new = changed[0]
            impacts.append(BookingImpact(
                booking_id=b.booking_id, status="change_required", required_action="change_date",
                reason=f"关联活动「{old.title}」由 {world.local(old.start_at):%m-%d %H:%M} 改为 {world.local(new.start_at):%m-%d %H:%M}",
                target_start=new.start_at, target_end=new.end_at))
        else:
            # Activity kept; is it still exposed to the event (e.g. outdoor + rain)?
            exposed = False
            for a in linked:
                place = world.place(a.place_id)
                if place and (ctx.blocking(a.start_at, a.end_at, place.indoor)
                              or ctx.is_closed(a.place_id, a.start_at, a.end_at)):
                    exposed = True
            if exposed:
                impacts.append(BookingImpact(booking_id=b.booking_id, status="potentially_affected",
                                             reason="关联活动保留，但仍处于事件影响时段", provider_initiated=provider_initiated))
            else:
                impacts.append(BookingImpact(booking_id=b.booking_id, status="unaffected", reason="关联活动未改变"))
    return impacts
