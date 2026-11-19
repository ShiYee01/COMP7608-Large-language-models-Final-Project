"""Natural-language trip setup: one paragraph -> a structured TripRequest.

The traveller describes the trip in their own words (dates, places they want to see or avoid,
preferences such as "quiet" or "anime", and what they have ALREADY booked). Nothing is verified:
PlanB plans around what the user says, and anything not stated stays unknown (never 0).

The LLM only extracts; the result is validated with Pydantic and checked against the place
catalogue. Places that are not in the catalogue are reported, never invented. A transparent
rule-based extractor is used in mock mode (no API key) and as a fallback.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from .data import World
from .llm import LLMClient, LLMUsage, extract_json

# Fixed preference vocabulary (the planner scores places by these tags).
TAG_LABELS = {
    "quiet": "安静", "lively": "热闹", "anime": "二次元/动漫", "nature": "自然", "culture": "文化",
    "history": "历史", "art": "艺术", "science": "科学", "shopping": "购物", "food": "美食",
    "photography": "拍照", "city_view": "城市景观",
}
TAG_KEYWORDS = {
    "quiet": ["安静", "清静", "人少", "不要太吵", "quiet", "peaceful"],
    "lively": ["热闹", "lively", "busy"],
    "anime": ["二次元", "动漫", "动画", "漫画", "宅", "anime", "manga"],
    "nature": ["自然", "公园", "花园", "庭园", "nature", "garden"],
    "culture": ["文化", "寺", "神社", "culture", "temple", "shrine"],
    "history": ["历史", "古迹", "history", "historic"],
    "art": ["艺术", "美术", "展览", "art", "museum"],
    "science": ["科学", "科技", "science"],
    "shopping": ["购物", "买东西", "逛街", "shopping"],
    "food": ["美食", "好吃", "小吃", "food"],
    "photography": ["拍照", "摄影", "出片", "photo"],
    "city_view": ["夜景", "城市景观", "观景", "view", "skyline"],
}
UNAMBIGUOUS_TAGS = {"quiet", "lively", "anime", "photography", "city_view", "science", "history"}
PACE_KEYWORDS = {"relaxed": ["轻松", "悠闲", "慢一点", "不要太赶", "relaxed", "slow"],
                 "packed": ["紧凑", "多去几个", "特种兵", "packed", "as many"]}
AREA_HOTELS = {"新宿": "hotel_shinjuku", "浅草": "hotel_asakusa", "银座": "hotel_ginza", "涩谷": "hotel_shibuya",
               "上野": "hotel_ueno", "池袋": "hotel_ikebukuro", "shinjuku": "hotel_shinjuku",
               "asakusa": "hotel_asakusa", "ginza": "hotel_ginza", "shibuya": "hotel_shibuya",
               "ueno": "hotel_ueno", "ikebukuro": "hotel_ikebukuro"}
# Short names people actually type -> catalogue ids (rule-based extractor only).
ALIASES = {
    "teamlab": "teamlab_planets", "晴空塔": "tokyo_skytree", "秋叶原": "akihabara", "吉卜力": "ghibli_museum",
    "高达": "gundam_odaiba", "宝可梦": "pokemon_center_ikebukuro", "乙女路": "ikebukuro_otome_road",
    "中野百老汇": "nakano_broadway", "筑地": "tsukiji_outer_market", "皇居": "imperial_east_gardens",
    "清澄庭园": "kiyosumi_teien", "滨离宫": "hamarikyu", "浜离宫": "hamarikyu", "北斋美术馆": "hokusai_museum",
    "回忆横丁": "omoide_yokocho", "寿司": "sushi_ginza", "国立博物馆": "tokyo_national_museum",
    "科学博物馆": "nature_science_museum", "涩谷sky": "shibuya_sky", "涩谷十字路口": "shibuya_crossing",
    "井之头公园": "inokashira_park", "台场海滨公园": "odaiba_seaside", "动漫人物街": "character_street",
}
NON_VISIT = {"airport", "hotel"}


class MustVisit(BaseModel):
    place_id: str
    day: Optional[date] = None


class HotelStay(BaseModel):
    place_id: Optional[str] = None  # representative hotel of the area in the catalogue
    name: str = ""
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    price_per_night_cny: Optional[float] = None


class StatedBooking(BaseModel):
    kind: Literal["flight_arrival", "flight_departure", "attraction", "restaurant"]
    title: str = ""
    place_id: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    price_cny: Optional[float] = None
    change_fee_cny: Optional[float] = None
    refundable: Optional[bool] = None


class TripRequest(BaseModel):
    destination: str = "Tokyo"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    must_visit: list[MustVisit] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    pace: Optional[Literal["relaxed", "normal", "packed"]] = None
    hotel: Optional[HotelStay] = None
    bookings: list[StatedBooking] = Field(default_factory=list)
    unknown_places: list[str] = Field(default_factory=list)
    budget_cny: Optional[float] = None
    notes: list[str] = Field(default_factory=list)  # sanitizer messages shown to the user

    def missing_required(self) -> list[str]:
        out = []
        if self.start_date is None or self.end_date is None:
            out.append("旅行日期（从哪天到哪天）")
        elif self.end_date < self.start_date:
            out.append("返程日期早于出发日期，请更正")
        return out


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the trip-setup module of PlanB, a travel copilot for Tokyo.
Read the traveller's message and extract ONE JSON object describing their request. Do NOT plan the trip.
Use only place ids from the catalogue in the context. If the traveller names a place that is not in the
catalogue, put its name in "unknown_places" - never map it to a different place. Bookings are whatever the
traveller says they have already booked; do not invent prices, fees or times: use null when not stated.
Dates: ISO format; infer the year from "today" in the context (the trip is in the future).
Datetimes: ISO 8601 with +09:00.

JSON schema:
{
  "start_date": "YYYY-MM-DD" or null, "end_date": "YYYY-MM-DD" or null,
  "must_visit": [{"place_id": "...", "day": "YYYY-MM-DD" or null}],   // places they want to visit
  "avoid": ["place_id", ...],                                       // places they do NOT want
  "interests": [tags from: TAGS],
  "pace": "relaxed" | "normal" | "packed" | null,
  "hotel": {"place_id": hotel id of the matching area or null, "name": "...", "check_in": "YYYY-MM-DD" or null,
            "check_out": "YYYY-MM-DD" or null, "price_per_night_cny": number or null} or null,
  "bookings": [{"kind": "flight_arrival" | "flight_departure" | "attraction" | "restaurant",
                "title": "...", "place_id": "..." or null, "start": ISO datetime or null, "end": ISO datetime or null,
                "price_cny": number or null, "change_fee_cny": number or null, "refundable": true/false/null}],
  "unknown_places": ["names not in the catalogue"],
  "budget_cny": number or null
}
For flights, "start" is the landing time (arrival) or the take-off time (departure); place_id is the airport.
Reply with the JSON object only.""".replace("TAGS", ", ".join(TAG_LABELS))


def _context(world: World, today: date, previous: Optional[TripRequest]) -> str:
    places = []
    for p in world.places.values():
        item = {"id": p.place_id, "name": p.name, "name_zh": p.name_zh, "category": p.category, "area": p.area}
        if p.tags:
            item["tags"] = p.tags
        places.append(item)
    ctx = {"today": str(today), "catalogue": places}
    if previous is not None:
        ctx["previous_request"] = previous.model_dump(mode="json", exclude={"notes"})
    return json.dumps(ctx, ensure_ascii=False)


def extract_trip_request(text: str, world: World, llm: LLMClient, today: date | None = None,
                         previous: TripRequest | None = None, usage: LLMUsage | None = None,
                         max_attempts: int = 2) -> tuple[TripRequest, str]:
    """Return (request, method) where method is 'llm', 'rule_fallback' or 'rule'.

    With `previous`, `text` is a correction ("my hotel is actually in Asakusa") applied to it.
    """
    today = today or date.today()
    if llm.is_mock:
        return _rule_extract(text, world, today, previous), "rule"
    instruction = ("Update previous_request with this correction and return the FULL updated JSON"
                   if previous is not None else "Traveller message")
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Context:\n{_context(world, today, previous)}\n\n{instruction}:\n{text}"}]
    for _ in range(max_attempts):
        r = llm.chat(messages, max_tokens=1200)
        if usage:
            usage.add(r)
        data = extract_json(r.text)
        if data is None:
            err = "Your reply was not valid JSON."
        else:
            try:
                return sanitize(TripRequest.model_validate(_clean_raw(data)), world), "llm"
            except (ValidationError, ValueError, TypeError) as e:
                err = f"Schema validation failed: {str(e)[:500]}"
        messages += [{"role": "assistant", "content": r.text}, {"role": "user", "content": err + " Reply with corrected JSON only."}]
    return _rule_extract(text, world, today, previous), "rule_fallback"


def _clean_raw(data: dict) -> dict:
    """Drop keys the model invents and normalise obvious shapes before validation."""
    data = {k: v for k, v in dict(data).items() if k in TripRequest.model_fields}
    mv = []
    for m in data.get("must_visit") or []:
        mv.append({"place_id": m} if isinstance(m, str) else m)
    data["must_visit"] = mv
    if data.get("pace") not in (None, "relaxed", "normal", "packed"):
        data["pace"] = None
    return data


def sanitize(req: TripRequest, world: World) -> TripRequest:
    """Check every id against the catalogue; unknown ids are reported, never guessed."""
    req = req.model_copy(deep=True)
    notes: list[str] = []
    tz = world.tz

    def visitable(pid: Optional[str]) -> bool:
        p = world.place(pid) if pid else None
        return p is not None and p.category not in NON_VISIT

    mv, seen = [], set()
    for m in req.must_visit:
        if not visitable(m.place_id):
            req.unknown_places.append(m.place_id)
        elif m.place_id not in seen:
            seen.add(m.place_id)
            mv.append(m)
    req.avoid = [p for p in dict.fromkeys(req.avoid) if visitable(p)]
    req.must_visit = [m for m in mv if m.place_id not in req.avoid]
    req.interests = [t for t in dict.fromkeys(req.interests) if t in TAG_LABELS]
    if req.hotel and req.hotel.place_id and (world.place(req.hotel.place_id) is None
                                             or world.place(req.hotel.place_id).category != "hotel"):
        notes.append(f"酒店位置「{req.hotel.place_id}」不在地点库中，暂按新宿规划")
        req.hotel.place_id = None

    bookings = []
    for b in req.bookings:
        for f in ("start", "end"):
            v = getattr(b, f)
            if v is not None and v.tzinfo is None:
                setattr(b, f, v.replace(tzinfo=tz))
        if b.kind.startswith("flight"):
            if not (b.place_id and world.place(b.place_id) and world.place(b.place_id).category == "airport"):
                b.place_id = "haneda_airport"
        elif not visitable(b.place_id):
            notes.append(f"预订「{b.title or b.place_id}」没有对应到地点库中的地点，暂不排入行程")
            continue
        if b.start is None:
            notes.append(f"预订「{b.title or b.place_id}」没有说明时间，暂不排入行程")
            continue
        bookings.append(b)
    req.bookings = bookings
    booked = {b.place_id for b in bookings}
    req.must_visit = [m for m in req.must_visit if m.place_id not in booked]
    req.unknown_places = list(dict.fromkeys(u for u in req.unknown_places if u))
    req.notes = notes
    return req


# ---------------------------------------------------------------------------
# Rule-based extraction (mock mode + fallback). Covers common Chinese phrasings only.
# ---------------------------------------------------------------------------

_SPLIT = re.compile(r"[，。,；;！!？?\n、]")
_DAY_RE = re.compile(r"(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*[日号]")
_CLOCK_RE = re.compile(r"(上午|早上|中午|下午|晚上)?\s*(\d{1,2})(?:\s*[:：]\s*(\d{2})|\s*点\s*(半|(\d{1,2})\s*分?)?)")


def _year_for(month: int, today: date) -> int:
    return today.year if month >= today.month else today.year + 1


def _find_place_ids(text: str, world: World) -> list[str]:
    low = text.lower()
    hits: list[tuple[int, int, str]] = []
    names: list[tuple[str, str]] = []
    for p in world.places.values():
        if p.category in NON_VISIT:
            continue
        for n in {p.name_zh, p.name, p.name.split(" (")[0], p.name_zh.split("（")[0]}:
            if n and len(n) >= 2:
                names.append((n.lower(), p.place_id))
    names += [(k.lower(), v) for k, v in ALIASES.items() if v in world.places]
    for n, pid in sorted(names, key=lambda x: -len(x[0])):  # longest names first, no overlaps
        for m in re.finditer(re.escape(n), low):
            if not any(m.start() < e and s < m.end() for s, e, _ in hits):
                hits.append((m.start(), m.end(), pid))
    return [pid for _, _, pid in sorted(hits)]


def _clock(clause: str) -> Optional[tuple[int, int]]:
    m = _CLOCK_RE.search(clause)
    if not m:
        return None
    period, h = m.group(1), int(m.group(2))
    minute = int(m.group(3)) if m.group(3) else (30 if m.group(4) == "半" else int(m.group(5) or 0))
    if period in ("下午", "晚上") and h < 12:
        h += 12
    if period == "中午" and h < 6:
        h += 12
    return (h, minute) if h < 24 and minute < 60 else None


def _clause_day(clause: str, start: Optional[date], today: date) -> Optional[date]:
    for m in _DAY_RE.finditer(clause):
        d = int(m.group(2))
        if m.group(1):
            month = int(m.group(1))
            return date(_year_for(month, today), month, d)
        if start is not None:
            month, year = start.month, start.year
            if d < start.day:  # e.g. trip 12/30 -> "2号" means next month
                month, year = (1, year + 1) if month == 12 else (month + 1, year)
            return date(year, month, d)
    return None


def _trip_dates(text: str, today: date) -> tuple[Optional[date], Optional[date]]:
    m = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?\s*(?:到|至|-|~|～|—)\s*(?:(\d{1,2})\s*月\s*)?(\d{1,2})\s*[日号]", text)
    if not m:
        return None, None
    m1, d1 = int(m.group(1)), int(m.group(2))
    m2, d2 = int(m.group(3) or m1), int(m.group(4))
    start = date(_year_for(m1, today), m1, d1)
    end = date(start.year + (1 if m2 < m1 else 0), m2, d2)
    return start, end


def _rule_extract(text: str, world: World, today: date, previous: Optional[TripRequest]) -> TripRequest:
    req = previous.model_copy(deep=True) if previous is not None else TripRequest()
    tz = world.tz
    s, e = _trip_dates(text, today)
    if s:
        req.start_date, req.end_date = s, e
    low = text.lower()
    # Keywords such as "寺" or "公园" also occur inside place names, so ambiguous tags are only read
    # from clauses that state a preference ("我喜欢……").
    pref_clauses = " ".join(c for c in _SPLIT.split(low) if re.search(r"喜欢|偏好|感兴趣|爱好|热爱|风格|类型|prefer|like", c))
    for tag, kws in TAG_KEYWORDS.items():
        scope = low if tag in UNAMBIGUOUS_TAGS else pref_clauses
        if any(k in scope for k in kws) and tag not in req.interests:
            req.interests.append(tag)
    for pace, kws in PACE_KEYWORDS.items():
        if any(k in low for k in kws):
            req.pace = pace
    m = re.search(r"预算\s*(\d+)", text)
    if m:
        req.budget_cny = float(m.group(1))

    for clause in filter(None, (c.strip() for c in _SPLIT.split(text))):
        cl = clause.lower()
        places = _find_place_ids(clause, world)
        day = _clause_day(clause, req.start_date, today)
        if re.search(r"不想去|不去|不要去|别去|去掉|取消", clause):
            for pid in places:
                if pid not in req.avoid:
                    req.avoid.append(pid)
            req.must_visit = [mv for mv in req.must_visit if mv.place_id not in places]
            continue
        if re.search(r"航班|飞机|起飞|落地|降落|机票", clause):
            departure = bool(re.search(r"返程|回程|回国|回去|起飞|离开", clause)) and not re.search(r"落地|降落|抵达|到达", clause)
            kind = "flight_departure" if departure else "flight_arrival"
            hm = _clock(clause)
            d = day or (req.end_date if departure else req.start_date)
            airport = "narita_airport" if "成田" in clause else "haneda_airport"
            req.bookings = [b for b in req.bookings if b.kind != kind]
            req.bookings.append(StatedBooking(
                kind=kind, title="返程航班" if departure else "去程航班", place_id=airport,
                start=datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=tz) if (d and hm) else None,
                price_cny=_money(clause, r"(?:机票|票价|花了|付了)\s*(\d+)"),
                change_fee_cny=_money(clause, r"改签费\s*(\d+)")))
            continue
        if re.search(r"酒店|住在|入住|住宿", clause):
            area = next((h for k, h in AREA_HOTELS.items() if k in cl), None)
            req.hotel = req.hotel or HotelStay()
            if area:
                req.hotel.place_id = area
                req.hotel.name = world.place(area).name_zh
            req.hotel.price_per_night_cny = _money(clause, r"每晚\s*(\d+)") or req.hotel.price_per_night_cny
            continue
        if re.search(r"门票|预约|订了|订位|预订|订好", clause) and places:
            pid = places[0]
            hm = _clock(clause)
            d = day
            p = world.place(pid)
            kind = "restaurant" if p.category == "food" else "attraction"
            req.bookings = [b for b in req.bookings if b.place_id != pid]
            req.bookings.append(StatedBooking(
                kind=kind, title=f"{p.name_zh}（已预订）", place_id=pid,
                start=datetime(d.year, d.month, d.day, hm[0], hm[1], tzinfo=tz) if (d and hm) else None,
                price_cny=_money(clause, r"(\d+)\s*元")))
            continue
        for pid in places:
            if pid not in [mv.place_id for mv in req.must_visit] and pid not in req.avoid:
                req.must_visit.append(MustVisit(place_id=pid, day=day))
        if not places:
            m = re.search(r"(?:还想去|也想去|想去|要去)\s*([^，。,、；;]+)", clause)
            if m and m.group(1).strip() not in req.unknown_places:
                req.unknown_places.append(m.group(1).strip())
    if req.hotel and (req.hotel.check_in is None or req.hotel.check_out is None):
        req.hotel.check_in = req.hotel.check_in or req.start_date
        req.hotel.check_out = req.hotel.check_out or req.end_date
    return sanitize(req, world)


def _money(text: str, pattern: str) -> Optional[float]:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Read-back summary (the user confirms or corrects it in their own words)
# ---------------------------------------------------------------------------

def summarize(req: TripRequest, world: World) -> str:
    def pname(pid: Optional[str]) -> str:
        p = world.place(pid) if pid else None
        return (p.name_zh or p.name) if p else str(pid)

    lines = []
    if req.start_date and req.end_date:
        days = (req.end_date - req.start_date).days + 1
        lines.append(f"- **日期**：{req.start_date:%m月%d日} – {req.end_date:%m月%d日}（{days} 天）")
    else:
        lines.append("- **日期**：❔ 还不知道，请告诉我从哪天到哪天")
    if req.must_visit:
        lines.append("- **想去**：" + "、".join(pname(m.place_id) + (f"（{m.day:%m/%d}）" if m.day else "")
                                             for m in req.must_visit))
    if req.avoid:
        lines.append("- **不去**：" + "、".join(pname(p) for p in req.avoid))
    if req.interests:
        lines.append("- **喜好**：" + "、".join(TAG_LABELS[t] for t in req.interests))
    lines.append("- **节奏**：" + {"relaxed": "轻松", "normal": "适中", "packed": "紧凑", None: "适中（默认）"}[req.pace])
    if req.hotel and req.hotel.place_id:
        price = f"，每晚 ¥{req.hotel.price_per_night_cny:,.0f}" if req.hotel.price_per_night_cny else "，价格未提供"
        area = next((k for k, v in AREA_HOTELS.items() if v == req.hotel.place_id), world.place(req.hotel.place_id).area)
        lines.append(f"- **酒店**：{area}一带（按「{pname(req.hotel.place_id)}」规划）{price}")
    else:
        lines.append("- **酒店**：未提供，暂按新宿一带规划")
    if req.bookings:
        lines.append("- **你已经预订的**（会被锁定，不会被改动）：")
        for b in sorted(req.bookings, key=lambda x: x.start):
            t = world.local(b.start)
            extra = []
            if b.price_cny is not None:
                extra.append(f"¥{b.price_cny:,.0f}")
            if b.change_fee_cny is not None:
                extra.append(f"改签费 ¥{b.change_fee_cny:,.0f}")
            what = {"flight_arrival": f"去程航班，{t:%m/%d %H:%M} 抵达{pname(b.place_id)}",
                    "flight_departure": f"返程航班，{t:%m/%d %H:%M} 从{pname(b.place_id)}起飞",
                    }.get(b.kind, f"{pname(b.place_id)}，{t:%m/%d %H:%M}")
            lines.append(f"  - {what}" + (f"（{'，'.join(extra)}）" if extra else ""))
    else:
        lines.append("- **已预订**：没有提到")
    if req.unknown_places:
        lines.append("- ⚠️ **地点库里没有**：" + "、".join(req.unknown_places) + "（不会自行替换成别的地点）")
    for n in req.notes:
        lines.append(f"- ⚠️ {n}")
    if req.bookings and not any(b.price_cny is not None or b.change_fee_cny is not None for b in req.bookings):
        lines.append("- 💡 你没有提到订单价格或改签/退款规则：之后如果行程变化，相关费用会显示为「未知」，不会当作 0。")
    return "\n".join(lines)
