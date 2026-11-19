"""Deterministic constraint validator (PROJECT_CONTEXT.md §8).

The validator is the neutral judge used both inside PlanB and in the evaluation of
the baselines. It never calls an LLM.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Optional

from .data import World
from .events import EventContext
from .models import Activity, Trip, ValidationResult, Violation

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
FLIGHT_CATEGORIES = {"flight_arrival", "flight_departure"}
PACE_LIMIT = {"relaxed": 4, "normal": 5, "packed": 7}  # visits+meals per day

RULES = [
    "UNKNOWN_PLACE", "TIME_ORDER", "TRIP_WINDOW", "TIME_OVERLAP", "TRAVEL_TIME",
    "OPENING_HOURS", "EVENT_CLOSURE", "EVENT_BLOCKED", "LOCKED", "BUDGET",
]


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _fmt(dt: datetime) -> str:
    return dt.strftime("%m-%d %H:%M")


def _within_opening(act: Activity, world: World) -> Optional[bool]:
    """True/False if known, None if opening hours unknown."""
    place = world.place(act.place_id)
    if place is None or place.opening_hours is None:
        return None
    start, end = world.local(act.start_at), world.local(act.end_at)
    if start.date() in place.closed_dates:
        return False
    windows = place.opening_hours.get(WEEKDAYS[start.weekday()], [])
    for o, c in windows:
        open_dt = start.replace(hour=_hm(o).hour, minute=_hm(o).minute, second=0, microsecond=0)
        close_t = _hm(c)
        close_dt = start.replace(hour=close_t.hour, minute=close_t.minute, second=0, microsecond=0)
        if c == "23:59":
            close_dt = close_dt + timedelta(minutes=1)
        if open_dt <= start and end <= close_dt:
            return True
    return False


def validate(
    trip: Trip,
    world: World,
    ctx: Optional[EventContext] = None,
    original: Optional[Trip] = None,
    extra_cost_minor: Optional[int] = 0,
    booking_paid_minor: Optional[int] = 0,
) -> ValidationResult:
    ctx = ctx or EventContext()
    hard: list[Violation] = []
    soft: list[Violation] = []
    unknown: list[Violation] = []

    acts = [a for a in trip.sorted_activities() if a.status == "planned"]
    end_date = ctx.new_end_date or trip.end_date

    # --- per-activity checks -------------------------------------------------
    for a in acts:
        if a.category == "free_time":
            # Free slots (e.g. "lunch, eat nearby") are not tied to a venue: no opening hours or weather
            # checks; they still count for overlaps, and travel is checked between the real activities.
            if a.end_at <= a.start_at:
                hard.append(Violation(rule="TIME_ORDER", activity_ids=[a.activity_id],
                                      message=f"{a.title}: 结束时间不晚于开始时间"))
            continue
        place = world.place(a.place_id)
        if place is None:
            hard.append(Violation(rule="UNKNOWN_PLACE", activity_ids=[a.activity_id], place_id=a.place_id,
                                  message=f"{a.title}: 地点 {a.place_id} 不在已知地点库中"))
            continue
        if a.end_at <= a.start_at:
            hard.append(Violation(rule="TIME_ORDER", activity_ids=[a.activity_id],
                                  message=f"{a.title}: 结束时间不晚于开始时间"))
        d = world.local(a.start_at).date()
        if d < trip.start_date or d > end_date:
            hard.append(Violation(rule="TRIP_WINDOW", activity_ids=[a.activity_id],
                                  message=f"{a.title}: 日期 {d} 不在旅行日期 {trip.start_date}~{end_date} 内"))
        if a.category in FLIGHT_CATEGORIES:
            continue
        ok = _within_opening(a, world)
        if ok is None:
            unknown.append(Violation(rule="OPENING_HOURS", activity_ids=[a.activity_id], place_id=a.place_id,
                                     message=f"{a.title}: 缺少营业时间数据，无法验证"))
        elif not ok:
            hard.append(Violation(rule="OPENING_HOURS", activity_ids=[a.activity_id], place_id=a.place_id,
                                  message=f"{a.title}: {_fmt(world.local(a.start_at))}-{world.local(a.end_at):%H:%M} 不在营业时间内"))
        closure = ctx.is_closed(a.place_id, a.start_at, a.end_at)
        if closure:
            hard.append(Violation(rule="EVENT_CLOSURE", activity_ids=[a.activity_id], place_id=a.place_id,
                                  message=f"{a.title}: 该地点在此时段关闭（{closure.reason}）"))
        block = ctx.blocking(a.start_at, a.end_at, place.indoor)
        if block:
            hard.append(Violation(rule="EVENT_BLOCKED", activity_ids=[a.activity_id],
                                  message=f"{a.title}: 与事件时段冲突（{block.reason}）"))
        day_start = _hm(trip.preferences.day_start)
        day_end = _hm(trip.preferences.day_end)
        ls, le = world.local(a.start_at), world.local(a.end_at)
        if ls.time() < day_start or (le.date() > ls.date()) or le.time() > day_end:
            soft.append(Violation(rule="DAY_WINDOW", activity_ids=[a.activity_id],
                                  message=f"{a.title}: 超出偏好的每日活动时间 {trip.preferences.day_start}-{trip.preferences.day_end}"))

    # --- arrival / departure anchors ------------------------------------------
    arrivals = [a for a in acts if a.category == "flight_arrival"]
    departures = [a for a in acts if a.category == "flight_departure"]
    for a in acts:
        if a.category in FLIGHT_CATEGORIES:
            continue
        for arr in arrivals:
            if world.local(arr.start_at).date() == world.local(a.start_at).date() and a.start_at < arr.end_at:
                hard.append(Violation(rule="TRIP_WINDOW", activity_ids=[a.activity_id, arr.activity_id],
                                      message=f"{a.title}: 安排在航班抵达之前"))
        for dep in departures:
            if world.local(dep.start_at).date() == world.local(a.start_at).date() and a.end_at > dep.start_at:
                hard.append(Violation(rule="TRIP_WINDOW", activity_ids=[a.activity_id, dep.activity_id],
                                      message=f"{a.title}: 结束时间晚于返程值机时间"))

    # --- pairwise overlap ------------------------------------------------------
    for i, a in enumerate(acts):
        for b in acts[i + 1:]:
            if b.start_at >= a.end_at:
                break
            hard.append(Violation(rule="TIME_OVERLAP", activity_ids=[a.activity_id, b.activity_id],
                                  message=f"{a.title} 与 {b.title} 时间重叠"))

    # --- travel time between consecutive activities on the same day -------------
    # Free slots ("eat nearby") take time but no travel: the time they occupy is subtracted from the gap.
    real = [a for a in acts if a.category != "free_time"]
    for a, b in zip(real, real[1:]):
        if world.local(a.start_at).date() != world.local(b.start_at).date():
            continue
        if world.place(a.place_id) is None or world.place(b.place_id) is None:
            continue
        minutes = world.travel_minutes(a.place_id, b.place_id)
        busy = sum((min(f.end_at, b.start_at) - max(f.start_at, a.end_at)).total_seconds() / 60
                   for f in acts if f.category == "free_time" and f.start_at < b.start_at and f.end_at > a.end_at)
        gap = (b.start_at - a.end_at).total_seconds() / 60 - busy
        if minutes is None:
            unknown.append(Violation(rule="TRAVEL_TIME", activity_ids=[a.activity_id, b.activity_id],
                                     message=f"{a.title} → {b.title}: 缺少交通时间数据"))
        elif gap >= 0 and gap < minutes:
            hard.append(Violation(rule="TRAVEL_TIME", activity_ids=[a.activity_id, b.activity_id],
                                  message=f"{a.title} → {b.title}: 需要 {minutes} 分钟交通，仅有 {int(gap)} 分钟"))

    # --- locked activities -----------------------------------------------------
    if original is not None:
        by_id = {a.activity_id: a for a in acts}
        for o in original.activities:
            if not o.is_locked or o.status != "planned":
                continue
            new = by_id.get(o.activity_id)
            if o.activity_id in ctx.forced_moves:
                fs, fe = ctx.forced_moves[o.activity_id]
                if new is None or new.start_at != fs or new.end_at != fe:
                    hard.append(Violation(rule="LOCKED", activity_ids=[o.activity_id],
                                          message=f"{o.title}: 预约已被改到 {_fmt(world.local(fs))}，方案未遵守"))
                continue
            if o.activity_id in ctx.released_locks:
                if new is None:
                    hard.append(Violation(rule="LOCKED", activity_ids=[o.activity_id],
                                          message=f"{o.title}: 锁定活动被删除"))
                continue
            if new is None or new.key() != o.key():
                hard.append(Violation(rule="LOCKED", activity_ids=[o.activity_id],
                                      message=f"{o.title}: 锁定活动被删除或改动（需用户解锁）"))

    # --- pace (soft) -------------------------------------------------------------
    per_day: dict = {}
    for a in acts:
        if a.category in ("visit", "meal"):
            per_day.setdefault(world.local(a.start_at).date(), []).append(a)
    limit = PACE_LIMIT[trip.preferences.pace]
    for d, items in per_day.items():
        if len(items) > limit:
            soft.append(Violation(rule="PACE", activity_ids=[a.activity_id for a in items],
                                  message=f"{d}: {len(items)} 项活动，超过 {trip.preferences.pace} 节奏建议的 {limit} 项"))

    # --- budget ------------------------------------------------------------------
    if trip.budget.amount_minor is not None:
        costs = [a.estimated_cost_minor for a in acts if a.category in ("visit", "meal")]
        parts = costs + [extra_cost_minor, booking_paid_minor]
        known_total = sum(c for c in parts if c is not None)
        if known_total > trip.budget.amount_minor:
            # Even the KNOWN part already exceeds the budget.
            v = Violation(rule="BUDGET", message=f"已知花费 ¥{known_total/100:.0f} 超出预算 ¥{trip.budget.amount_minor/100:.0f}")
            (hard if trip.budget.is_hard_limit else soft).append(v)
        elif any(c is None for c in parts) and trip.budget.is_hard_limit:
            unknown.append(Violation(rule="BUDGET", message="部分费用未知，无法确认是否超出硬预算"))

    status = "invalid" if hard else ("unknown" if unknown else "valid")
    return ValidationResult(feasibility_status=status, hard_violations=hard, soft_warnings=soft,
                            unknown_constraints=unknown, checked_rules=RULES)
