"""Itinerary edits requested in chat (as opposed to disruptions such as rain or delays).

  "我不想去浅草寺了"            -> remove_activity: alternatives that fit the freed slot, or keep it free
  "推荐一个二次元的地方加到12号"  -> recommend: up to 3 places that fit a free slot, ranked by preference
  "12号午饭去筑地吃"            -> set_meal: put a restaurant into the lunch/dinner slot
  "11号晚饭不用安排"            -> skip_meal
  "我更喜欢安静的地方"           -> update_preferences (remembered for later recommendations)

The LLM (if configured) only extracts an EditRequest; candidates are generated, validated and costed by
code, and every change is a proposal that the user approves. A restaurant that is not in the catalogue is
added as a user-provided place: with an area hint its travel times are estimated from that area, without
one they stay unknown (never 0).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, time, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from .data import World
from .events import EventContext
from .llm import LLMClient, LLMUsage, extract_json
from .models import Activity, Booking, Place, PlanProposal, TravelTime, Trip, new_id
from .planner import MEALS, _fit, _gaps, interest_score
from .repair import build_proposal
from .trip_request import (ALIASES, AREA_HOTELS, TAG_KEYWORDS, TAG_LABELS, _clause_day, _clock, _find_place_ids)

EditKind = Literal["remove_activity", "recommend", "set_meal", "skip_meal", "update_preferences"]

DISRUPTION_HINT = re.compile(r"关闭|闭馆|不开放|延误|晚点|堵车|暴雨|下雨|大雨|雨|雪|台风|天气|多待|延长|推迟|延期|"
                             r"提前.*回|早一天|缩短|改到|改期|航班|起飞|到不了")
MEAL_HINT = re.compile(r"午饭|午餐|中饭|晚饭|晚餐|吃饭|(?:中午|晚上).{0,15}吃|找家.{0,10}吃|餐厅|饭店")
REMOVE_HINT = re.compile(r"不想去|不去了|不要去|别去|删掉|去掉|取消掉|不去")
RECOMMEND_HINT = re.compile(r"推荐|加一个|再加|多加|安排一个|还想去.*(地方|地点)|有什么.*(地方|好玩)")
PREF_HINT = re.compile(r"喜欢|偏好|感兴趣|更想|不喜欢|节奏")
SKIP_MEAL_HINT = re.compile(r"不用安排|不需要安排|不用留|自己解决|不吃|取消")


class EditRequest(BaseModel):
    kind: EditKind
    place_ids: list[str] = Field(default_factory=list)  # catalogue places mentioned (to remove / to add)
    day: Optional[date] = None
    meal: Optional[Literal["lunch", "dinner"]] = None
    restaurant_name: str = ""  # a restaurant that is NOT in the catalogue
    area_hint: str = ""  # e.g. "浅草" or a catalogue place it is near
    start_time: Optional[str] = None  # "HH:MM"
    add_interests: list[str] = Field(default_factory=list)
    remove_interests: list[str] = Field(default_factory=list)
    pace: Optional[Literal["relaxed", "normal", "packed"]] = None


def detect_edit(text: str) -> Optional[str]:
    """Cheap routing: is this an itinerary edit (and not a disruption such as rain or a delay)?"""
    if MEAL_HINT.search(text):
        return "skip_meal" if SKIP_MEAL_HINT.search(text) else "set_meal"
    if DISRUPTION_HINT.search(text):
        return None
    if REMOVE_HINT.search(text):
        return "remove_activity"
    if RECOMMEND_HINT.search(text):
        return "recommend"
    if PREF_HINT.search(text):
        return "update_preferences"
    return None


# ---------------------------------------------------------------------------
# Extraction (LLM with schema validation, rule-based fallback)
# ---------------------------------------------------------------------------

EDIT_PROMPT = """You are the edit-understanding module of PlanB, a Tokyo travel copilot.
The traveller wants to change their itinerary. Extract ONE JSON object; do not plan anything.
Use only activity/place ids from the context. A restaurant that is not in the catalogue goes into
"restaurant_name", written in the traveller's own language and words (never map it to another place); put any
location hint ("near Senso-ji", "in Asakusa") into "area_hint". Use null when something is not stated.
{"kind": "remove_activity" | "recommend" | "set_meal" | "skip_meal" | "update_preferences",
 "place_ids": [catalogue place ids mentioned: to remove, or wanted for recommend/set_meal],
 "day": "YYYY-MM-DD" or null, "meal": "lunch" | "dinner" | null,
 "restaurant_name": "", "area_hint": "", "start_time": "HH:MM" or null,
 "add_interests": [tags from: TAGS], "remove_interests": [tags], "pace": "relaxed" | "normal" | "packed" | null}
add_interests = preferences expressed in THIS message (e.g. "有历史感" -> history, "人少/安静" -> quiet,
"二次元" -> anime); for a remove request they guide the replacement.
Reply with the JSON object only.""".replace("TAGS", ", ".join(TAG_LABELS))


def _edit_context(trip: Trip, world: World) -> str:
    acts = [{"id": a.activity_id, "title": a.title, "place_id": a.place_id, "date": str(world.local(a.start_at).date()),
             "start": f"{world.local(a.start_at):%H:%M}", "category": a.category} for a in trip.sorted_activities()]
    places = [{"id": p.place_id, "name_zh": p.name_zh, "name": p.name, "category": p.category, "area": p.area}
              for p in world.places.values() if p.category not in ("airport", "hotel")]
    return json.dumps({"trip": {"start_date": str(trip.start_date), "end_date": str(trip.end_date),
                                "preferences": trip.preferences.model_dump()},
                       "activities": acts, "catalogue": places}, ensure_ascii=False)


def extract_edit(text: str, kind: str, trip: Trip, world: World, llm: LLMClient,
                 usage: LLMUsage | None = None) -> tuple[EditRequest, str]:
    if not llm.is_mock:
        messages = [{"role": "system", "content": EDIT_PROMPT},
                    {"role": "user", "content": f"Context:\n{_edit_context(trip, world)}\n\nTraveller message:\n{text}"}]
        r = llm.chat(messages, max_tokens=600)
        if usage:
            usage.add(r)
        data = extract_json(r.text)
        if isinstance(data, dict):
            try:
                req = EditRequest.model_validate({k: v for k, v in data.items() if k in EditRequest.model_fields})
                req.place_ids = [p for p in req.place_ids if world.place(p)]
                req.add_interests = [t for t in req.add_interests if t in TAG_LABELS]
                req.remove_interests = [t for t in req.remove_interests if t in TAG_LABELS]
                # never lose explicit preference words: merge in what the keyword matcher finds
                rule = _rule_edit(text, kind, trip, world)
                req.add_interests = list(dict.fromkeys(req.add_interests + rule.add_interests))
                if req.kind == "set_meal" and not req.place_ids:
                    if resolve_area(req.area_hint, world) is None and rule.area_hint:
                        req.area_hint = rule.area_hint
                    if rule.restaurant_name and rule.restaurant_name != "自选餐厅" and not re.search(r"[一-鿿]", req.restaurant_name):
                        req.restaurant_name = rule.restaurant_name  # keep the traveller's own wording
                return req, "llm"
            except (ValidationError, ValueError, TypeError):
                pass
        return _rule_edit(text, kind, trip, world), "rule_fallback"
    return _rule_edit(text, kind, trip, world), "rule"


def _rule_edit(text: str, kind: str, trip: Trip, world: World) -> EditRequest:
    low = text.lower()
    req = EditRequest(kind=kind, place_ids=_find_place_ids(text, world))
    req.day = _clause_day(text, trip.start_date, trip.start_date)
    hm = _clock(text)
    if hm:
        req.start_time = f"{hm[0]:02d}:{hm[1]:02d}"
    if kind in ("set_meal", "skip_meal"):
        req.meal = "dinner" if re.search(r"晚饭|晚餐|晚上|夜宵", text) else "lunch"
    negative = re.search(r"不喜欢|不想要|讨厌", text)
    scan = low  # place names such as "浅草寺" must not count as a preference for temples
    for pid in req.place_ids:
        p = world.place(pid)
        for n in sorted({p.name_zh, p.name, p.name_zh.split("（")[0]}, key=len, reverse=True):
            scan = scan.replace(n.lower(), " ") if n else scan
    for alias, pid in ALIASES.items():
        if pid in req.place_ids:
            scan = scan.replace(alias.lower(), " ")
    for tag, kws in TAG_KEYWORDS.items():
        if any(k in scan for k in kws):
            (req.remove_interests if negative else req.add_interests).append(tag)
    if re.search(r"轻松|悠闲|慢一点|不要太赶", text):
        req.pace = "relaxed"
    elif re.search(r"紧凑|多去几个|特种兵", text):
        req.pace = "packed"
    if kind == "set_meal":
        food = [p for p in req.place_ids if world.place(p).category == "food"]
        if food:
            req.place_ids = food[:1]
        else:
            m = re.search(r"(?:去|在)\s*([^，。,！!？?；;]+)", text)
            name = re.sub(r"\s*(?:吃饭|吃|用餐)\s*(?:吧|了)?\s*$", "", (m.group(1) if m else "")).strip()
            req.area_hint = next((k for k in AREA_HOTELS if k in low and not k.isascii()), "")
            if req.area_hint and name.startswith(req.area_hint):
                rest = re.sub(r"^(?:找一家|找家|那家|这家|一家|的|附近的|那边的)", "", name[len(req.area_hint):]).strip()
                name = f"{rest}（{req.area_hint}）" if rest else name
            req.restaurant_name = name or "自选餐厅"
            if not req.area_hint and req.place_ids:
                req.area_hint = req.place_ids[0]
            req.place_ids = []
    return req


# ---------------------------------------------------------------------------
# Execution: candidates -> proposals (validated, booking impact, cost)
# ---------------------------------------------------------------------------

class EditOutcome(BaseModel):
    state: Literal["WAITING_FOR_APPROVAL", "PREFERENCES_UPDATED", "NEEDS_INFORMATION", "INFEASIBLE"]
    message: str
    proposals: list[PlanProposal] = Field(default_factory=list)


def _name(world: World, pid: str) -> str:
    p = world.place(pid)
    return (p.name_zh or p.name) if p else pid


def _tags_text(world: World, pid: str, interests: list[str]) -> str:
    tags = [TAG_LABELS[t] for t in world.place(pid).tags if t in interests]
    return "、".join(tags) if tags else "顺路"


def _rank_candidates(world: World, trip: Trip, gap, exclude: set[str], k: int, focus: list[str] | None = None):
    """Places that fit into the gap. With focus tags (e.g. "anime" from this request) only matching places
    are considered; ranking: focus match, then general preference match, then least extra travel."""
    ctx = EventContext()
    out = []
    for p in world.places.values():
        if p.category in ("airport", "hotel", "food") or p.place_id in exclude or p.verified_status == "user_provided":
            continue
        if focus and not set(focus) & set(p.tags):
            continue
        r = _fit(world, ctx, p.place_id, gap)
        if r:
            out.append((-interest_score(p.tags, focus or []), -interest_score(p.tags, trip.preferences.interests),
                        r[2], p.place_id, r[0], r[1]))
    out.sort()
    return [(o[0] + o[1], o[2], o[3], o[4], o[5]) for o in out[:k]]


def _add(trip: Trip, world: World, pid: str, start: datetime, end: datetime, note: str) -> Activity:
    p = world.place(pid)
    a = Activity(activity_id=new_id("act"), place_id=pid, title=_name(world, pid), start_at=start, end_at=end,
                 category="meal" if p.category == "food" else "visit", estimated_cost_minor=p.entry_cost_minor,
                 notes=note)
    trip.activities.append(a)
    return a


def apply_edit(req: EditRequest, trip: Trip, bookings: list[Booking], world: World,
               avoided: set[str]) -> EditOutcome:
    hotel = trip.hotel_place_id or "hotel_shinjuku"
    notes = []

    # Preferences stated in the same message are applied first (they are the user's own words).
    # In a recommend request ("推荐一个二次元的地方") the tags are only the focus of this request, and a meal
    # request ("找家天妇罗吃") says nothing about lasting preferences.
    if req.kind in ("update_preferences", "remove_activity") and (req.add_interests or req.remove_interests or req.pace):
        prefs = trip.preferences
        prefs.interests = [t for t in dict.fromkeys(prefs.interests + req.add_interests) if t not in req.remove_interests]
        if req.pace:
            prefs.pace = req.pace
        notes.append("已记住你的喜好：" + ("、".join(TAG_LABELS[t] for t in prefs.interests) or "（无）") +
                     (f"；节奏：{ {'relaxed': '轻松', 'normal': '适中', 'packed': '紧凑'}[prefs.pace] }" if req.pace else ""))
    if req.kind == "update_preferences":
        return EditOutcome(state="PREFERENCES_UPDATED", message="\n".join(
            notes + ["之后的推荐和修改都会优先考虑这些喜好。想按新喜好调整现有行程，可以说「推荐一个…的地方」或「不想去X了」。"]))

    if req.kind == "remove_activity":
        return _remove(req, trip, bookings, world, avoided, hotel, notes)
    if req.kind == "recommend":
        return _recommend(req, trip, bookings, world, avoided, hotel, notes)
    if req.kind in ("set_meal", "skip_meal"):
        return _meal(req, trip, bookings, world, hotel, notes)
    return EditOutcome(state="NEEDS_INFORMATION", message="没能理解这条修改，请换个说法。")


def _remove(req, trip, bookings, world, avoided, hotel, notes) -> EditOutcome:
    targets = [a for a in trip.sorted_activities() if a.place_id in req.place_ids and a.category in ("visit", "meal")]
    avoided.update(req.place_ids)
    if not targets:
        names = "、".join(_name(world, p) for p in req.place_ids) or "这个地方"
        return EditOutcome(state="NEEDS_INFORMATION", message="\n".join(
            notes + [f"「{names}」不在当前行程里；已记下，之后不会再推荐它。"]))
    locked = [a for a in targets if a.is_locked]
    if locked:
        return EditOutcome(state="INFEASIBLE", message="\n".join(notes + [
            f"「{locked[0].title}」是锁定的项目（例如你已预订），PlanB 不会自动删除。",
            "如果确定要取消，请先在「行程」页解锁它；删除后订单影响和费用会一起计算。"]))
    target = targets[0]
    base = trip.model_copy(deep=True)
    base.activities = [a for a in base.activities if a.activity_id != target.activity_id]
    d = world.local(target.start_at).date()
    gap = next((g for g in _gaps(world, d, base.activities, hotel) if g[0] <= target.start_at < g[1]), None)
    proposals = []
    exclude = {a.place_id for a in base.activities} | avoided
    for _, _, pid, start, end in (_rank_candidates(world, base, gap, exclude, 2) if gap else []):
        cand = base.model_copy(deep=True)
        _add(cand, world, pid, start, end, "PlanB 推荐")
        p = build_proposal(trip, cand, world, bookings, label=f"换成：{_name(world, pid)}",
                           reasons={target.activity_id: "按你的要求删除"})
        p.explanation = (f"删除「{target.title}」，在 {start:%m-%d %H:%M}–{end:%H:%M} 换成「{_name(world, pid)}」"
                         f"（{_tags_text(world, pid, trip.preferences.interests)}）。")
        proposals.append(p)
    p = build_proposal(trip, base, world, bookings, label="只删除，留作自由时间",
                       reasons={target.activity_id: "按你的要求删除"})
    p.explanation = f"删除「{target.title}」，这段时间留作自由活动。"
    proposals.append(p)
    lines = notes + [f"好的，不去「{target.title}」了。给你 {len(proposals)} 个选择："]
    lines += [f"{i + 1}. {x.explanation}" for i, x in enumerate(proposals)]
    lines.append("到「📋 方案对比与审批」选择一个批准即可。")
    return EditOutcome(state="WAITING_FOR_APPROVAL", message="\n".join(lines), proposals=proposals)


def _recommend(req, trip, bookings, world, avoided, hotel, notes) -> EditOutcome:
    days = [req.day] if req.day and trip.start_date <= req.day <= trip.end_date else \
        [trip.start_date + timedelta(days=i) for i in range((trip.end_date - trip.start_date).days + 1)]
    exclude = {a.place_id for a in trip.activities if a.category != "free_time"} | avoided
    wanted = [p for p in req.place_ids if world.place(p) and world.place(p).category not in ("airport", "hotel")]
    focus = list(req.add_interests)
    scored = []
    for d in days:
        for gap in _gaps(world, d, trip.activities, hotel):
            if wanted:
                for pid in wanted:
                    r = _fit(world, EventContext(), pid, gap)
                    if r:
                        scored.append((0, r[2], pid, r[0], r[1]))
            else:
                scored += _rank_candidates(world, trip, gap, exclude, 3, focus)
    seen, best = set(), []
    for item in sorted(scored):
        if item[2] not in seen:
            seen.add(item[2])
            best.append(item)
    best = best[:3]
    what = "、".join(TAG_LABELS[t] for t in focus) if focus else "你的喜好"
    proposals = []
    for _, _, pid, start, end in best:
        cand = trip.model_copy(deep=True)
        _add(cand, world, pid, start, end, "PlanB 推荐")
        p = build_proposal(trip, cand, world, bookings, label=f"加入：{_name(world, pid)}")
        p.explanation = (f"在 {start:%m-%d %H:%M}–{end:%H:%M} 加入「{_name(world, pid)}」"
                         f"（{_tags_text(world, pid, focus or trip.preferences.interests)}）。")
        proposals.append(p)
    if not proposals and not wanted:
        # No free slot: offer to swap out one of PlanB's own suggestions (never a must-visit or a booking).
        for a in trip.sorted_activities():
            if a.notes != "PlanB 推荐" or a.is_locked or world.local(a.start_at).date() not in days:
                continue
            base = trip.model_copy(deep=True)
            base.activities = [x for x in base.activities if x.activity_id != a.activity_id]
            d = world.local(a.start_at).date()
            gap = next((g for g in _gaps(world, d, base.activities, hotel) if g[0] <= a.start_at < g[1]), None)
            for _, _, pid, start, end in (_rank_candidates(world, base, gap, exclude, 1, focus) if gap else []):
                cand = base.model_copy(deep=True)
                _add(cand, world, pid, start, end, "PlanB 推荐")
                p = build_proposal(trip, cand, world, bookings, label=f"把「{a.title}」换成：{_name(world, pid)}",
                                   reasons={a.activity_id: "为你想要的地点腾出时间"})
                p.explanation = (f"把「{a.title}」换成「{_name(world, pid)}」（{start:%m-%d %H:%M}–{end:%H:%M}，"
                                 f"{_tags_text(world, pid, focus or trip.preferences.interests)}）。")
                proposals.append(p)
            if len(proposals) >= 3:
                break
        if proposals:
            where = f"{req.day:%m月%d日}" if req.day else "行程里"
            lines = notes + [f"{where}已经没有空闲时间了，可以用一个符合「{what}」的地点替换掉 PlanB 之前推荐的项目"
                             "（你想去的和已预订的不会动）："]
            lines += [f"{i + 1}. {x.explanation}" for i, x in enumerate(proposals)]
            lines.append("到「📋 方案对比与审批」选择一个批准即可。")
            return EditOutcome(state="WAITING_FOR_APPROVAL", message="\n".join(lines), proposals=proposals)
    if not proposals:
        where = f"{req.day:%m月%d日}" if req.day else "行程中"
        return EditOutcome(state="INFEASIBLE", message="\n".join(notes + [
            f"{where}没有放得下、又符合「{what}」的地点（时间或营业时间不合适）。可以先删掉一个活动，或换一天试试。"]))
    lines = notes + [f"找到 {len(proposals)} 个符合「{what}」、放得下的地点："]
    lines += [f"{i + 1}. {x.explanation}" for i, x in enumerate(proposals)]
    lines.append("到「📋 方案对比与审批」选择一个批准即可。")
    return EditOutcome(state="WAITING_FOR_APPROVAL", message="\n".join(lines), proposals=proposals)


def _meal(req, trip, bookings, world, hotel, notes) -> EditOutcome:
    title = "午餐" if req.meal != "dinner" else "晚餐"
    _, lo, hi, minutes, pref = MEALS[0] if req.meal != "dinner" else MEALS[1]
    day = req.day
    if day is None or not (trip.start_date <= day <= trip.end_date):
        return EditOutcome(state="NEEDS_INFORMATION", message="\n".join(notes + [f"请告诉我是哪一天的{title}。"]))
    tz = world.tz
    slot = next((a for a in trip.sorted_activities() if a.category == "free_time" and title in a.title
                 and world.local(a.start_at).date() == day), None)
    base = trip.model_copy(deep=True)
    if slot:
        base.activities = [a for a in base.activities if a.activity_id != slot.activity_id]
    if req.kind == "skip_meal":
        if not slot:
            return EditOutcome(state="NEEDS_INFORMATION", message=f"{day:%m月%d日}本来就没有安排{title}时间。")
        p = build_proposal(trip, base, world, bookings, label=f"不安排 {day:%m/%d} {title}")
        p.explanation = f"去掉 {day:%m月%d日} 的{title}时间，这段时间空出来。"
        return EditOutcome(state="WAITING_FOR_APPROVAL", message="\n".join(notes + [p.explanation]), proposals=[p])

    # which restaurant?
    if req.place_ids:
        pid, extra = req.place_ids[0], ""
    else:
        pid, extra = add_user_restaurant(world, req.restaurant_name or "自选餐厅", req.area_hint)
    place = world.place(pid)
    duration = (slot.end_at - slot.start_at) if slot else timedelta(minutes=minutes)
    if req.start_time:
        h, m = map(int, req.start_time.split(":"))
        starts = [datetime.combine(day, time(h, m), tzinfo=tz)]
    else:
        wlo, whi = datetime.combine(day, lo, tzinfo=tz), datetime.combine(day, hi, tzinfo=tz)
        p0 = slot.start_at if slot else datetime.combine(day, pref, tzinfo=tz)
        starts = sorted((wlo + timedelta(minutes=15 * i) for i in range(int((whi - wlo).total_seconds() // 900) + 1)),
                        key=lambda x: abs((x - p0).total_seconds()))
    best = None
    for s in starts:
        cand = base.model_copy(deep=True)
        a = Activity(activity_id=new_id("act"), place_id=pid, title=f"{title}：{place.name_zh or place.name}",
                     start_at=s, end_at=s + duration, category="meal", estimated_cost_minor=place.entry_cost_minor,
                     notes="你选的餐厅")
        cand.activities.append(a)
        p = build_proposal(trip, cand, world, bookings, label=f"{day:%m/%d} {title}：{place.name_zh or place.name}",
                           reasons={slot.activity_id: "换成你选的餐厅"} if slot else None)
        if not p.validation.hard_violations:
            best = (p, s)
            break
        best = best or (p, s)
    p, s = best
    lines = notes + [f"{day:%m月%d日}{title}改为「{place.name_zh or place.name}」（{s:%H:%M}–{(s + duration):%H:%M}）。"]
    if extra:
        lines.append(extra)
    if p.validation.hard_violations:
        lines.append("⛔ 这个时间放不下：" + "；".join(v.message for v in p.validation.hard_violations[:2]) +
                     "。可以换一家、换个时间，或先删掉附近的一个活动。")
    elif p.validation.unknown_constraints:
        lines.append("⚠️ 有些条件无法确认：" + "；".join(v.message for v in p.validation.unknown_constraints[:2]))
    p.explanation = lines[-1] if len(lines) > 1 else lines[0]
    lines.append("到「📋 方案对比与审批」确认。")
    return EditOutcome(state="WAITING_FOR_APPROVAL", message="\n".join(lines), proposals=[p])


# ---------------------------------------------------------------------------
# User-provided places (restaurants that are not in the catalogue)
# ---------------------------------------------------------------------------

def _travel_estimate(dist_km: float) -> tuple[str, int, int]:
    """Same synthetic formula as scripts/build_fixtures.py (walk < 1.2 km, else transit)."""
    if dist_km < 1.2:
        return "walk", max(5, math.ceil(dist_km * 15 / 5) * 5), 0
    return "transit", math.ceil((12 + 3.2 * dist_km) / 5) * 5, int(round(8 + 0.6 * dist_km)) * 100


def _haversine(a: Place, b_lat: float, b_lon: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a.latitude, a.longitude, b_lat, b_lon))
    d = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(d))


def resolve_area(hint: str, world: World) -> Optional[Place]:
    """'浅草' / 'Asakusa' / 'near Senso-ji' / a place id -> a catalogue place to estimate travel from."""
    if not hint:
        return None
    h = hint.strip().lower()
    for key, hotel in AREA_HOTELS.items():
        if key.lower() in h:
            return world.place(hotel)
    if world.place(hint.strip()):
        return world.place(hint.strip())
    found = _find_place_ids(hint, world)
    return world.place(found[0]) if found else None


def add_user_restaurant(world: World, name: str, area_hint: str = "") -> tuple[str, str]:
    """Register a restaurant the user named. Returns (place_id, note for the user)."""
    pid = "user_" + hashlib.sha1(f"{name}|{area_hint}".encode()).hexdigest()[:8]
    if world.place(pid):
        return pid, ""
    anchor = resolve_area(area_hint, world)
    area_label = next((k for k, v in AREA_HOTELS.items() if anchor and v == anchor.place_id and not k.isascii()),
                      (anchor.name_zh or anchor.name) if anchor else "")
    world.places[pid] = Place(place_id=pid, name=name, name_zh=name, category="food", indoor=True,
                              latitude=anchor.latitude if anchor else 0.0, longitude=anchor.longitude if anchor else 0.0,
                              area=(f"{area_label}一带（估算）" if anchor else "位置未知"), opening_hours=None,
                              suggested_visit_minutes=60, entry_cost_minor=None, tags=["food"],
                              data_source="user", verified_status="user_provided")
    if anchor is None:
        return pid, (f"「{name}」不在地点库里，也不知道大概位置：交通时间和营业时间都标为「未知」，"
                     "无法确认是否来得及。告诉我它在哪一带（例如「在浅草」）就能估算。")
    for other in list(world.places.values()):
        if other.place_id == pid or (other.latitude == 0.0 and other.longitude == 0.0):
            continue
        mode, minutes, fare = _travel_estimate(_haversine(other, anchor.latitude, anchor.longitude))
        tt = TravelTime(origin_place_id=pid, destination_place_id=other.place_id, mode=mode, travel_minutes=minutes,
                        travel_cost_minor=fare, source="area_estimate")
        world._travel[(pid, other.place_id)] = tt
        world._travel[(other.place_id, pid)] = tt.model_copy(update={"origin_place_id": other.place_id,
                                                                      "destination_place_id": pid})
    return pid, (f"「{name}」不在地点库里：按「{area_label}一带」估算交通时间；营业时间和价格未知，"
                 "PlanB 会标为「无法验证」而不是当作没问题。")
