"""Local plan repair engine (PROJECT_CONTEXT.md §9).

Bounded beam search over local edits (Keep / Shift / Move-day / Replace / Remove)
applied ONLY to activities affected by the event. Hard constraints are checked by
the deterministic validator before any candidate is ranked.

Ranking order (lexicographic):
  1. disruption to still-feasible original plan (weighted change count)
  2. known booking-related extra cost (unknown cost never counts as cheapest)
  3. total travel minutes
  4. preference match (higher is better)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from .booking_impact import analyze_booking_impact
from .cost_engine import estimate_cost
from .data import World
from .events import EventContext, build_context
from .models import (Activity, ActivityChange, Booking, DisruptionEvent, PlanProposal, ReplanResult, Trip)
from .planner import fill_window, interest_score, place_fits
from .validator import FLIGHT_CATEGORIES, validate

BEAM_WIDTH = 6
MAX_PROPOSALS = 3
STEP_MIN = 15
CHANGE_WEIGHT = {"shift": 1.0, "move_day": 1.5, "replace": 2.0, "remove": 3.0, "add": 0.25}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _clone(trip: Trip) -> Trip:
    return trip.model_copy(deep=True)


def _day_bounds(trip: Trip, world: World, day) -> tuple[datetime, datetime]:
    h, m = map(int, trip.preferences.day_start.split(":"))
    eh, em = map(int, trip.preferences.day_end.split(":"))
    return (datetime(day.year, day.month, day.day, h, m, tzinfo=world.tz),
            datetime(day.year, day.month, day.day, eh, em, tzinfo=world.tz))


def _trip_days(trip: Trip):
    d = trip.start_date
    while d <= trip.end_date:
        yield d
        d += timedelta(days=1)


def _hard_count(trip: Trip, world: World, ctx: EventContext, original: Trip) -> int:
    return len(validate(trip, world, ctx, original).hard_violations)


def _neighbors_ok(trip: Trip, world: World, act: Activity) -> bool:
    """Quick local feasibility of one activity against same-day neighbours."""
    day = world.local(act.start_at).date()
    same = sorted([a for a in trip.activities if a.status == "planned" and a.activity_id != act.activity_id
                   and world.local(a.start_at).date() == day], key=lambda a: a.start_at)
    prev = next((a for a in reversed(same) if a.start_at <= act.start_at), None)
    nxt = next((a for a in same if a.start_at > act.start_at), None)
    if prev:
        t = world.travel_minutes(prev.place_id, act.place_id)
        if prev.end_at > act.start_at or (t is not None and prev.end_at + timedelta(minutes=t) > act.start_at):
            return False
    if nxt:
        t = world.travel_minutes(act.place_id, nxt.place_id)
        if act.end_at > nxt.start_at or (t is not None and act.end_at + timedelta(minutes=t) > nxt.start_at):
            return False
    for a in same:  # anchors
        if a.category == "flight_departure" and act.end_at > a.start_at:
            return False
        if a.category == "flight_arrival" and act.start_at < a.end_at:
            return False
    return True


def _replace_activity(trip: Trip, act_id: str, **update) -> Trip:
    t = _clone(trip)
    t.activities = [a.model_copy(update=update) if a.activity_id == act_id else a for a in t.activities]
    return t


# ---------------------------------------------------------------------------
# candidate local edits for one affected activity
# ---------------------------------------------------------------------------

def _actions(state: Trip, act_id: str, world: World, ctx: EventContext) -> list[tuple[str, Trip, str]]:
    act = state.activity(act_id)
    if act is None or act.status != "planned":
        return [("keep", state, "")]
    out: list[tuple[str, Trip, str]] = [("keep", state, "")]
    dur = act.end_at - act.start_at
    day = world.local(act.start_at).date()
    in_trip = state.start_date <= day <= state.end_date

    # Shift within the same day (closest feasible start times first)
    if in_trip:
        lo, hi = _day_bounds(state, world, day)
        slots = []
        t = lo
        while t + dur <= hi:
            if t != act.start_at and place_fits(world, ctx, act.place_id, t, t + dur):
                moved = act.model_copy(update={"start_at": t, "end_at": t + dur})
                if _neighbors_ok(state, world, moved):
                    slots.append(t)
            t += timedelta(minutes=STEP_MIN)
        slots.sort(key=lambda s: abs((s - act.start_at).total_seconds()))
        for s in slots[:2]:
            out.append(("shift", _replace_activity(state, act_id, start_at=s, end_at=s + dur),
                        f"调整到 {world.local(s):%H:%M}"))

        # Cascade shift: start right after the blocking window and push later activities.
        block = ctx.blocking(act.start_at, act.end_at, world.place(act.place_id).indoor) if world.place(act.place_id) else None
        if block is not None:
            cascaded = _cascade(state, act_id, block.end, world)
            if cascaded is not None:
                out.append(("shift", cascaded, f"顺延到 {world.local(block.end):%H:%M} 之后，后续活动依次顺延"))

    # Move to another trip day (first free slot of each other day)
    for d in _trip_days(state):
        if d == day:
            continue
        lo, hi = _day_bounds(state, world, d)
        t = lo
        while t + dur <= hi:
            if place_fits(world, ctx, act.place_id, t, t + dur):
                moved = act.model_copy(update={"start_at": t, "end_at": t + dur})
                if _neighbors_ok(state, world, moved):
                    out.append(("move_day", _replace_activity(state, act_id, start_at=t, end_at=t + dur),
                                f"改到 {d} {world.local(t):%H:%M}"))
                    break
            t += timedelta(minutes=STEP_MIN)

    # Replace with another place in the same slot
    if in_trip:
        used = {a.place_id for a in state.activities if a.status == "planned"}
        orig_place = world.place(act.place_id)
        options = []
        for p in world.places.values():
            if p.place_id in used or p.category in ("airport", "hotel"):
                continue
            if orig_place and orig_place.category == "food" and p.category != "food":
                continue
            if orig_place and orig_place.category != "food" and p.category == "food":
                continue
            new_dur = min(dur, timedelta(minutes=p.suggested_visit_minutes)) if p.suggested_visit_minutes else dur
            end = act.start_at + new_dur
            if not place_fits(world, ctx, p.place_id, act.start_at, end):
                continue
            cand = act.model_copy(update={"place_id": p.place_id, "end_at": end})
            if not _neighbors_ok(state, world, cand):
                continue
            score = interest_score(p.tags, state.preferences.interests) * 10
            if orig_place:
                score += 5 * len(set(p.tags) & set(orig_place.tags))
            options.append((score, p, end))
        options.sort(key=lambda x: -x[0])
        for _, p, end in options[:3]:
            out.append(("replace", _replace_activity(state, act_id, place_id=p.place_id, end_at=end,
                                                     title=p.name_zh or p.name,
                                                     estimated_cost_minor=p.entry_cost_minor,
                                                     notes=f"替换原活动「{act.title}」"),
                        f"替换为「{p.name_zh or p.name}」"))

    # Remove
    t = _clone(state)
    t.activities = [a for a in t.activities if a.activity_id != act_id]
    out.append(("remove", t, "删除该活动"))
    return out


def _cascade(state: Trip, act_id: str, not_before: datetime, world: World) -> Optional[Trip]:
    """Shift act to start at/after not_before; push later same-day non-locked activities as needed."""
    t = _clone(state)
    act = t.activity(act_id)
    day = world.local(act.start_at).date()
    same = sorted([a for a in t.activities if a.status == "planned" and world.local(a.start_at).date() == day],
                  key=lambda a: a.start_at)
    idx = next(i for i, a in enumerate(same) if a.activity_id == act_id)
    prev_end, prev_place = None, None
    if idx > 0:
        prev_end, prev_place = same[idx - 1].end_at, same[idx - 1].place_id
    cursor = not_before
    for a in same[idx:]:
        if prev_end is not None:
            travel = world.travel_minutes(prev_place, a.place_id) or 0
            cursor = max(cursor, prev_end + timedelta(minutes=travel))
        if a.start_at >= cursor and a.activity_id != act_id:
            break  # nothing more to push
        if a.is_locked or a.category in FLIGHT_CATEGORIES:
            if a.start_at < cursor:
                return None
            break
        dur = a.end_at - a.start_at
        a.start_at, a.end_at = cursor, cursor + dur
        prev_end, prev_place = a.end_at, a.place_id
        cursor = a.end_at
    return t


# ---------------------------------------------------------------------------
# structural changes imposed by the event
# ---------------------------------------------------------------------------

def _apply_structural(trip: Trip, ctx: EventContext, bookings: list[Booking], world: World) -> Trip:
    base = _clone(trip)
    for aid, (s, e) in ctx.forced_moves.items():
        base = _replace_activity(base, aid, start_at=s, end_at=e)
    if ctx.new_end_date is not None and ctx.new_end_date != trip.end_date:
        base.end_date = ctx.new_end_date
        for a in base.activities:
            if a.category != "flight_departure":
                continue
            # Use the airline quote for the new date when available, otherwise keep the clock time.
            booking = next((b for b in bookings if a.activity_id in b.linked_activity_ids), None)
            quote = None
            if booking:
                quote = next((q for q in booking.quotes if q.action == "change_date" and q.target_start
                              and world.local(q.target_start).date() == ctx.new_end_date), None)
            if quote:
                dep = quote.target_start
            else:
                old_dep = world.local(a.end_at)
                dep = old_dep.replace(year=ctx.new_end_date.year, month=ctx.new_end_date.month, day=ctx.new_end_date.day)
            a.start_at, a.end_at = dep - (a.end_at - a.start_at), dep
    return base


def _affected(base: Trip, world: World, ctx: EventContext, original: Trip) -> tuple[list[str], list[str], list[str]]:
    """Return (affected non-locked ids, unresolvable messages, relaxation options)."""
    res = validate(base, world, ctx, original)
    locked = {a.activity_id for a in base.activities if a.is_locked}
    fixed = (locked | set(ctx.forced_moves)
             | {a.activity_id for a in base.activities if a.category in FLIGHT_CATEGORIES})
    affected: list[str] = []
    blockers: list[str] = []
    relax: list[str] = []
    for v in res.hard_violations:
        movable = [aid for aid in v.activity_ids if aid not in fixed]
        if movable:
            for aid in movable:
                if aid not in affected:
                    affected.append(aid)
        else:
            blockers.append(v.message)
            for aid in v.activity_ids:
                a = base.activity(aid)
                if a and a.is_locked and a.category not in FLIGHT_CATEGORIES:
                    opt = f"解除锁定「{a.title}」，允许 PlanB 调整或删除它"
                    if opt not in relax:
                        relax.append(opt)
    affected.sort(key=lambda aid: base.activity(aid).start_at)
    return affected, blockers, relax


# ---------------------------------------------------------------------------
# diff + scoring
# ---------------------------------------------------------------------------

def _brief(a: Activity, world: World) -> dict:
    return {"title": a.title, "place_id": a.place_id,
            "start": world.local(a.start_at).strftime("%m-%d %H:%M"),
            "end": world.local(a.end_at).strftime("%H:%M")}


def diff_trips(original: Trip, candidate: Trip, world: World, reasons: dict[str, str] | None = None) -> list[ActivityChange]:
    reasons = reasons or {}
    out: list[ActivityChange] = []
    new_by_id = {a.activity_id: a for a in candidate.activities if a.status == "planned"}
    for o in original.sorted_activities():
        n = new_by_id.get(o.activity_id)
        if n is None:
            out.append(ActivityChange(change_type="remove", activity_id=o.activity_id, before=_brief(o, world),
                                      reason=reasons.get(o.activity_id, "")))
        elif n.place_id != o.place_id:
            out.append(ActivityChange(change_type="replace", activity_id=o.activity_id, before=_brief(o, world),
                                      after=_brief(n, world), reason=reasons.get(o.activity_id, "")))
        elif n.start_at != o.start_at or n.end_at != o.end_at:
            kind = "extend" if o.category == "flight_departure" else "shift"
            out.append(ActivityChange(change_type=kind, activity_id=o.activity_id, before=_brief(o, world),
                                      after=_brief(n, world), reason=reasons.get(o.activity_id, "")))
        else:
            out.append(ActivityChange(change_type="keep", activity_id=o.activity_id, before=_brief(o, world)))
    orig_ids = {a.activity_id for a in original.activities}
    for n in candidate.sorted_activities():
        if n.activity_id not in orig_ids:
            out.append(ActivityChange(change_type="add", activity_id=n.activity_id, after=_brief(n, world),
                                      reason=reasons.get(n.activity_id, n.notes)))
    return out


def _disruption(original: Trip, candidate: Trip, world: World, ctx: EventContext) -> float:
    total = 0.0
    orig = {a.activity_id: a for a in original.activities}
    new = {a.activity_id: a for a in candidate.activities if a.status == "planned"}
    for aid, o in orig.items():
        if aid in ctx.forced_moves or aid in ctx.released_locks:
            continue  # imposed by the event / explicitly requested
        n = new.get(aid)
        weight = 0.5 + o.priority / 2  # priority 2 -> 1.5x
        if n is None:
            total += CHANGE_WEIGHT["remove"] * weight
        elif n.place_id != o.place_id:
            total += CHANGE_WEIGHT["replace"] * weight
        elif world.local(n.start_at).date() != world.local(o.start_at).date():
            total += CHANGE_WEIGHT["move_day"] * weight
        elif n.start_at != o.start_at or n.end_at != o.end_at:
            delta = abs((n.start_at - o.start_at).total_seconds()) / 60
            total += CHANGE_WEIGHT["shift"] * weight * (0.5 if delta <= 30 else 1.0)
    total += CHANGE_WEIGHT["add"] * len([a for a in new if a not in orig])
    return round(total, 2)


def _travel_minutes(trip: Trip, world: World) -> int:
    acts = [a for a in trip.sorted_activities() if a.status == "planned"]
    total = 0
    for a, b in zip(acts, acts[1:]):
        if world.local(a.start_at).date() == world.local(b.start_at).date():
            total += world.travel_minutes(a.place_id, b.place_id) or 0
    return total


def _pref(trip: Trip, world: World) -> int:
    return sum(interest_score(world.place(a.place_id).tags, trip.preferences.interests)
               for a in trip.activities if world.place(a.place_id))


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------

def replan(trip: Trip, event: DisruptionEvent, world: World, bookings: list[Booking],
           max_proposals: int = MAX_PROPOSALS) -> ReplanResult:
    ctx = build_context(event, trip, bookings)
    if ctx.missing_information:
        return ReplanResult(status="needs_information", event=event, missing_information=ctx.missing_information)

    base = _apply_structural(trip, ctx, bookings, world)
    affected, blockers, relax = _affected(base, world, ctx, trip)

    if blockers:
        return ReplanResult(status="infeasible", event=event, affected_activity_ids=affected,
                            infeasible_reasons=blockers,
                            relaxation_options=relax or ["放宽或取消本次请求中的固定条件"])

    # Beam search over affected activities
    beam: list[tuple[Trip, dict[str, str]]] = [(base, {})]
    for aid in affected:
        expanded = []
        for state, reasons in beam:
            for kind, new_state, why in _actions(state, aid, world, ctx):
                r = dict(reasons)
                if kind != "keep":
                    r[aid] = why
                expanded.append((new_state, r))
        expanded.sort(key=lambda s: (_hard_count(s[0], world, ctx, trip), _disruption(trip, s[0], world, ctx)))
        seen, beam = set(), []
        for state, r in expanded:
            sig = tuple(sorted((a.activity_id, a.place_id, a.start_at) for a in state.activities))
            if sig in seen:
                continue
            seen.add(sig)
            beam.append((state, r))
            if len(beam) >= BEAM_WIDTH:
                break

    finals: list[tuple[Trip, dict[str, str], str]] = [(s, r, "") for s, r in beam]

    # Trip extension: optionally use the new free time (second-style proposal).
    if event.event_type == "trip_extension" and finals:
        filled = _fill_new_time(finals[0][0], trip, world, ctx)
        if filled is not None:
            finals.append((filled, dict(finals[0][1]), "利用新增时间安排推荐活动"))

    proposals: list[PlanProposal] = []
    best_failure = None
    for state, reasons, label in finals:
        res = validate(state, world, ctx, trip)
        if res.hard_violations:
            if best_failure is None or len(res.hard_violations) < len(best_failure.hard_violations):
                best_failure = res
            continue
        proposals.append(build_proposal(trip, state, world, bookings, ctx, event, label, reasons, res))

    if not proposals:
        reasons = [v.message for v in (best_failure.hard_violations if best_failure else [])]
        return ReplanResult(status="infeasible", event=event, affected_activity_ids=affected,
                            infeasible_reasons=reasons or ["在有限搜索范围内找不到满足所有硬约束的方案"],
                            relaxation_options=["解除部分活动的锁定", "允许删除受影响活动", "调整事件时间范围或旅行日期"])

    def rank(p: PlanProposal):
        s = p.score
        cost_rank = (0, s["known_additional_minor"]) if s["cost_known"] else (1, s["known_additional_minor"])
        return (s["disruption"], cost_rank, s["travel_minutes"], -s["preference"])

    proposals.sort(key=rank)
    unique, sigs = [], set()
    for p in proposals:
        sig = tuple(sorted((a.activity_id, a.place_id, a.start_at) for a in p.proposed_trip.activities))
        if sig not in sigs:
            sigs.add(sig)
            unique.append(p)
    labels = ["推荐：改动最少", "备选", "备选"]
    for i, p in enumerate(unique[:max_proposals]):
        if not p.label:
            p.label = labels[min(i, 2)]
    return ReplanResult(status="ok", event=event, affected_activity_ids=affected, proposals=unique[:max_proposals])


def build_proposal(original: Trip, candidate: Trip, world: World, bookings: list[Booking],
                   ctx: EventContext | None = None, event: DisruptionEvent | None = None, label: str = "",
                   reasons: dict[str, str] | None = None, validation=None) -> PlanProposal:
    """Validate + booking impact + cost + diff for any candidate (AI-generated or manual edit)."""
    ctx = ctx or EventContext()
    res = validation or validate(candidate, world, ctx, original)
    impacts = analyze_booking_impact(original, candidate, bookings, world, ctx)
    cost = estimate_cost(impacts, bookings, world, candidate.end_date)
    changes = diff_trips(original, candidate, world, reasons)
    score = {
        "disruption": _disruption(original, candidate, world, ctx),
        "cost_known": cost.is_complete,
        "known_additional_minor": cost.known_additional_minor,
        "travel_minutes": _travel_minutes(candidate, world),
        "preference": _pref(candidate, world),
        "n_changes": sum(1 for c in changes if c.change_type != "keep"),
    }
    return PlanProposal(trip_id=original.trip_id, base_revision=original.revision, label=label, event=event,
                        proposed_trip=candidate, changes=changes, validation=res, booking_impacts=impacts,
                        cost_estimate=cost, score=score)


def _fill_new_time(state: Trip, original: Trip, world: World, ctx: EventContext) -> Optional[Trip]:
    """After an extension, add recommended visits into newly free time."""
    t = _clone(state)
    used = {a.place_id for a in t.activities}
    added_any = False
    d = original.end_date
    while d <= t.end_date:
        lo, hi = _day_bounds(t, world, d)
        lo = max(lo, lo.replace(hour=9, minute=0))
        same = sorted([a for a in t.activities if world.local(a.start_at).date() == d], key=lambda a: a.start_at)
        # find the largest gap of the day
        points = [(lo, t.hotel_place_id)] + [(a.end_at, a.place_id) for a in same]
        nexts = [(a.start_at, a.place_id) for a in same] + [(hi.replace(hour=19, minute=0), t.hotel_place_id)]
        departure = next((a.start_at for a in same if a.category == "flight_departure"), None)
        gaps = [(s, pp, e, np_) for (s, pp), (e, np_) in zip(points, nexts)
                if (e - s) >= timedelta(hours=2) and (departure is None or s < departure)]
        for s, pp, e, np_ in gaps:
            new = fill_window(t, world, ctx, s, e, pp, np_, 2, used)
            if new:
                t.activities.extend(new)
                added_any = True
        d += timedelta(days=1)
    return t if added_any else None
