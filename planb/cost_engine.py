"""Deterministic incremental cost engine (PROJECT_CONTEXT.md §10).

Metric: ADDITIONAL OUT-OF-POCKET cash relative to the original plan, caused by
changes to existing bookings (fees, fare differences, extra nights, minus
confirmed refunds). Entry fees of new, not-yet-booked activities are NOT included
(they are reported separately by the UI as estimates).

Rules:
- integer minor units only; never mix currencies;
- unknown inputs produce unknown components (never 0);
- money already paid is never counted again as new spending.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from .data import World
from .models import AlternativeQuote, Booking, BookingImpact, CostComponent, CostEstimate


def _yuan(minor: Optional[int]) -> str:
    return "未知" if minor is None else f"¥{minor / 100:,.0f}"


def _pick_quote(booking: Booking, action: str, target: Optional[datetime], world: World) -> Optional[AlternativeQuote]:
    if target is None:
        return None
    cands = [q for q in booking.quotes if q.action == action and q.target_start is not None
             and world.local(q.target_start).date() == world.local(target).date()]
    if not cands:
        return None
    return min(cands, key=lambda q: abs((q.target_start - target).total_seconds()))


def _flight_change(b: Booking, imp: BookingImpact, world: World, comps: list[CostComponent], notes: list[str]):
    pol = b.policy
    # For a departure activity the flight leaves at the END of the airport block.
    target = imp.target_end or imp.target_start
    if pol.change_allowed is False:
        q = next((q for q in b.quotes if q.action == "new_booking"), None)
        comps.append(CostComponent(kind="flight_new_ticket", booking_id=b.booking_id,
                                   amount_minor=q.amount_minor if q else None,
                                   basis="原机票不可改签，需要新购机票" + (f"（报价 {_yuan(q.amount_minor)}）" if q else "；缺少新票报价")))
        return
    if pol.change_allowed is None:
        comps.append(CostComponent(kind="flight_change", booking_id=b.booking_id, amount_minor=None,
                                   basis="订单未提供是否允许改签"))
        return
    comps.append(CostComponent(kind="flight_change_fee", booking_id=b.booking_id, amount_minor=pol.change_fee_minor,
                               basis="改签手续费（订单规则）" if pol.change_fee_minor is not None else "订单未提供改签手续费"))
    q = _pick_quote(b, "change_date", target, world)
    if q is None:
        comps.append(CostComponent(kind="flight_fare_difference", booking_id=b.booking_id, amount_minor=None,
                                   basis=f"缺少 {world.local(target):%m-%d} 航班的票价差报价" if target else "缺少目标航班报价"))
        return
    if q.available is False:
        notes.append(f"{b.title}: 报价 {q.quote_id} 显示目标航班不可用")
    diff = q.amount_minor
    if diff is not None and diff < 0:
        if pol.negative_fare_difference_refunded is True:
            pass
        elif pol.negative_fare_difference_refunded is False:
            notes.append(f"{b.title}: 票价差为负（{_yuan(diff)}），按规则不退还，计为 0")
            diff = 0
        else:
            diff = None
            notes.append(f"{b.title}: 票价差为负，规则未说明是否退还")
    comps.append(CostComponent(kind="flight_fare_difference", booking_id=b.booking_id, amount_minor=diff,
                               basis=f"票价差（报价 {q.quote_id}{'，模拟' if q.simulated else ''}）"))


def _hotel(b: Booking, imp: BookingImpact, world: World, new_end, comps: list[CostComponent], notes: list[str]):
    if imp.required_action == "extend_stay":
        q = None
        for cand in b.quotes:
            if cand.action == "extend_stay" and cand.target_end is not None and world.local(cand.target_end).date() == new_end:
                q = cand
        if q is None:
            comps.append(CostComponent(kind="hotel_extension", booking_id=b.booking_id, amount_minor=None,
                                       basis=f"缺少续住到 {new_end} 的报价/可用性"))
            return
        if q.available is False:
            notes.append(f"{b.title}: 续住报价显示无房，需要另订酒店")
            comps.append(CostComponent(kind="hotel_extension", booking_id=b.booking_id, amount_minor=None,
                                       basis="原酒店无法续住，缺少替代酒店报价"))
            return
        if q.available is None:
            notes.append(f"{b.title}: 续住可用性未确认")
        comps.append(CostComponent(kind="hotel_extension", booking_id=b.booking_id, amount_minor=q.amount_minor,
                                   basis=f"续住报价 {q.quote_id}{'（模拟）' if q.simulated else ''}"))
    elif imp.required_action == "shorten_stay":
        refund = b.policy.early_checkout_refund_minor
        comps.append(CostComponent(kind="hotel_early_checkout_refund", booking_id=b.booking_id,
                                   amount_minor=None if refund is None else -refund,
                                   basis="提前退房退款（订单规则）" if refund is not None else "订单未提供提前退房退款规则"))
        if refund is not None and b.paid_minor is not None and b.service_start and b.service_end:
            nights = (world.local(b.service_end).date() - world.local(b.service_start).date()).days
            lost = (world.local(b.service_end).date() - new_end).days
            if nights > 0:
                forfeited = b.paid_minor * lost // nights - refund
                if forfeited > 0:
                    comps.append(CostComponent(kind="hotel_unused_nights_forfeited", booking_id=b.booking_id,
                                               amount_minor=forfeited, cash=False,
                                               basis=f"{lost} 晚未入住且不退款（按均价估算，属经济损失，非新增现金支出）"))


def _cancel(b: Booking, imp: BookingImpact, comps: list[CostComponent]):
    pol = b.policy
    if imp.provider_initiated:
        refund, basis = pol.provider_cancellation_refund_minor, "商家/场馆原因取消的退款规则"
    elif pol.cancel_allowed is False:
        refund, basis = 0, "订单不可取消，无退款"
    else:
        refund, basis = pol.refund_on_cancel_minor, "用户取消的退款规则"
    comps.append(CostComponent(kind="cancellation_refund", booking_id=b.booking_id,
                               amount_minor=None if refund is None else -refund,
                               basis=basis if refund is not None else "订单未提供退款规则"))
    if refund is not None and b.paid_minor is not None and b.paid_minor - refund > 0:
        comps.append(CostComponent(kind="forfeited_payment", booking_id=b.booking_id,
                                   amount_minor=b.paid_minor - refund, cash=False,
                                   basis="已付款中不可退部分（经济损失，非新增现金支出）"))


def _reservation_change(b: Booking, imp: BookingImpact, world: World, comps: list[CostComponent]):
    pol = b.policy
    if pol.change_allowed is True:
        comps.append(CostComponent(kind="reservation_change_fee", booking_id=b.booking_id,
                                   amount_minor=pol.change_fee_minor if pol.change_fee_minor is not None else None,
                                   basis="预约改期手续费" if pol.change_fee_minor is not None else "订单未提供改期手续费"))
        q = _pick_quote(b, "change_date", imp.target_start, world)
        if q is not None:
            comps.append(CostComponent(kind="reservation_price_difference", booking_id=b.booking_id,
                                       amount_minor=q.amount_minor, basis=f"改期报价 {q.quote_id}"))
        return
    # Not changeable: the original ticket is lost and a new one must be bought.
    _cancel(b, imp.model_copy(update={"provider_initiated": False}), comps)
    q = next((q for q in b.quotes if q.action == "new_booking"), None)
    comps.append(CostComponent(kind="new_reservation", booking_id=b.booking_id,
                               amount_minor=q.amount_minor if q else None,
                               basis="原预约不可改期，需要重新预约" + ("" if q else "；缺少新预约报价")))


def estimate_cost(impacts: list[BookingImpact], bookings: list[Booking], world: World, new_end_date) -> CostEstimate:
    by_id = {b.booking_id: b for b in bookings}
    comps: list[CostComponent] = []
    notes: list[str] = []
    for imp in impacts:
        if imp.status != "change_required":
            continue
        b = by_id[imp.booking_id]
        if b.booking_type == "flight" and imp.required_action == "change_date":
            _flight_change(b, imp, world, comps, notes)
        elif b.booking_type == "hotel":
            _hotel(b, imp, world, new_end_date, comps, notes)
        elif imp.required_action == "cancel":
            _cancel(b, imp, comps)
        elif imp.required_action == "change_date":
            _reservation_change(b, imp, world, comps)

    currencies = {by_id[c.booking_id].currency for c in comps if c.booking_id}
    if len(currencies) > 1:
        notes.append("涉及多个币种，未换算，总额按币种分别展示")

    cash = [c for c in comps if c.cash]
    unknown = [c for c in cash if c.amount_minor is None]
    known = sum(c.amount_minor for c in cash if c.amount_minor is not None)
    forfeited = sum(c.amount_minor for c in comps if not c.cash and c.amount_minor is not None)
    notes.append("价格与规则来自用户录入/静态演示数据，非实时报价")
    return CostEstimate(
        currency=next(iter(currencies)) if len(currencies) == 1 else "CNY",
        known_additional_minor=known,
        total_additional_minor=None if unknown else known,
        forfeited_minor=forfeited,
        is_complete=not unknown,
        components=comps,
        unknown_components=unknown,
        assumptions=notes,
    )
