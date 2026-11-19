"""Build the trip-setup (T*) and chat-edit (E*) evaluation scenarios + a Chinese review sheet.

Ground truth is written BY HAND from the request text and catalogue facts (opening hours, closing
days, tags in data/places/tokyo_places_extended.json). It is NOT produced by running PlanB.
Weekdays: 2026-12-10 Thu, 11 Fri, 12 Sat, 13 Sun, 14 Mon, 15 Tue, 16 Wed, 17 Thu.

Run:  python scripts/build_trip_scenarios.py
Out:  evaluation/trip_scenarios/*.json and evaluation/trip_scenarios/REVIEW.md
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation" / "trip_scenarios"
TODAY = "2026-11-19"


def b(kind, place, start, **kw):
    return {"kind": kind, "place_id": place, "start": start, **kw}


# ---------------------------------------------------------------------------
# Trip setup: one paragraph -> structured request -> daily plan
# gold_request : what a correct reading of the paragraph contains
# plan_checks  : facts any correct plan must satisfy
#   must_include / must_exclude      place ids
#   on_day / not_on_day              {place_id: date or [dates]}
#   locked_at                        bookings that must appear at exactly this start time
#   no_visits_on                     days with no sightseeing possible
#   expected_unplaceable             must-visits that cannot be scheduled (must be reported, not scheduled)
#   max_visits_per_day               from the stated pace (relaxed 3, normal 4, packed 5)
#   preference_tags                  added suggestions should carry at least one of these tags
# ---------------------------------------------------------------------------
SETUP = [
    dict(id="t01_monday_closure", category="closed_weekday",
         request="12月14日到16日去东京，住上野那边。想去东京国立博物馆和上野公园，喜欢自然和历史，节奏适中。"
                 "14号上午10点到成田，16号晚上8点从成田起飞回国。",
         why="12/14 是周一，东京国立博物馆周一闭馆：必须排在 15 或 16 号。成田机场离市区远，返程当天要预留交通时间。",
         gold_request=dict(start_date="2026-12-14", end_date="2026-12-16",
                           must_visit=["tokyo_national_museum", "ueno_park"], must_visit_days={},
                           avoid=[], interests_required=["nature", "history"], interests_allowed=["culture", "quiet", "photography"],
                           pace="normal", hotel_place_id="hotel_ueno",
                           bookings=[b("flight_arrival", "narita_airport", "2026-12-14T10:00:00+09:00"),
                                     b("flight_departure", "narita_airport", "2026-12-16T20:00:00+09:00")],
                           unknown_places=[]),
         plan_checks=dict(must_include=["tokyo_national_museum", "ueno_park"], must_exclude=[],
                          on_day={}, not_on_day={"tokyo_national_museum": ["2026-12-14"]},
                          locked_at=[b("flight_arrival", "narita_airport", "2026-12-14T10:00:00+09:00"),
                                     b("flight_departure", "narita_airport", "2026-12-16T20:00:00+09:00")],
                          no_visits_on=[], expected_unplaceable=[], max_visits_per_day=4,
                          preference_tags=["nature", "history"])),
    dict(id="t02_anime_tuesday_closure", category="closed_weekday",
         request="我15号到17号在东京，酒店在池袋。我是动漫迷，一定要去吉卜力美术馆和中野百老汇，也想逛逛秋叶原。"
                 "节奏可以紧凑一点。15号中午12点落地羽田，17号下午5点的飞机回去。",
         why="“15号到17号”按今天（11/19）推断为 12 月。12/15 是周二，吉卜力美术馆周二闭馆；中野百老汇 12:00 才开门。",
         gold_request=dict(start_date="2026-12-15", end_date="2026-12-17",
                           must_visit=["ghibli_museum", "nakano_broadway", "akihabara"], must_visit_days={},
                           avoid=[], interests_required=["anime"], interests_allowed=["shopping", "lively"],
                           pace="packed", hotel_place_id="hotel_ikebukuro",
                           bookings=[b("flight_arrival", "haneda_airport", "2026-12-15T12:00:00+09:00"),
                                     b("flight_departure", "haneda_airport", "2026-12-17T17:00:00+09:00")],
                           unknown_places=[]),
         plan_checks=dict(must_include=["ghibli_museum", "nakano_broadway", "akihabara"], must_exclude=[],
                          on_day={}, not_on_day={"ghibli_museum": ["2026-12-15"]},
                          locked_at=[b("flight_arrival", "haneda_airport", "2026-12-15T12:00:00+09:00"),
                                     b("flight_departure", "haneda_airport", "2026-12-17T17:00:00+09:00")],
                          no_visits_on=[], expected_unplaceable=[], max_visits_per_day=5,
                          preference_tags=["anime"])),
    dict(id="t03_places_not_in_catalogue", category="unknown_place",
         request="12月10日到11日去东京，住银座。想去东京迪士尼乐园和筑地市场，还想去一趟横滨中华街。喜欢美食和购物。"
                 "没有订机票，自己安排交通。",
         why="迪士尼和横滨中华街不在地点库里：必须报告“没有”，不能换成别的地点，也不能编造。筑地周三、周日休息，10/11 号是周四、周五，可以去。",
         gold_request=dict(start_date="2026-12-10", end_date="2026-12-11",
                           must_visit=["tsukiji_outer_market"], must_visit_days={}, avoid=[],
                           interests_required=["food", "shopping"], interests_allowed=["lively"],
                           pace=None, hotel_place_id="hotel_ginza", bookings=[],
                           unknown_places=["东京迪士尼乐园", "横滨中华街"]),
         plan_checks=dict(must_include=["tsukiji_outer_market"], must_exclude=[], on_day={}, not_on_day={},
                          locked_at=[], no_visits_on=[], expected_unplaceable=[], max_visits_per_day=4,
                          preference_tags=["food", "shopping"])),
    dict(id="t04_english_avoid_quiet", category="avoid_and_language",
         request="We're in Tokyo from Dec 12 to Dec 13, staying in Shibuya. We love quiet gardens and art museums, "
                 "and want a relaxed pace. Please avoid crowded spots like Shibuya Crossing and Takeshita Street. "
                 "We land at Haneda at 9:00 on the 12th and fly out of Haneda at 21:00 on the 13th.",
         why="英文请求。两处“不想去”必须避开；节奏轻松（每天最多 3 个景点）；推荐应偏向安静的庭园和美术馆。",
         gold_request=dict(start_date="2026-12-12", end_date="2026-12-13", must_visit=[], must_visit_days={},
                           avoid=["shibuya_crossing", "harajuku_takeshita"],
                           interests_required=["quiet", "art"], interests_allowed=["nature", "culture"],
                           pace="relaxed", hotel_place_id="hotel_shibuya",
                           bookings=[b("flight_arrival", "haneda_airport", "2026-12-12T09:00:00+09:00"),
                                     b("flight_departure", "haneda_airport", "2026-12-13T21:00:00+09:00")],
                           unknown_places=[]),
         plan_checks=dict(must_include=[], must_exclude=["shibuya_crossing", "harajuku_takeshita"], on_day={},
                          not_on_day={},
                          locked_at=[b("flight_arrival", "haneda_airport", "2026-12-12T09:00:00+09:00"),
                                     b("flight_departure", "haneda_airport", "2026-12-13T21:00:00+09:00")],
                          no_visits_on=[], expected_unplaceable=[], max_visits_per_day=3,
                          preference_tags=["quiet", "art", "nature"])),
    dict(id="t05_bookings_with_prices", category="stated_bookings",
         request="12月10日到12日，住新宿。10号下午3点半到羽田，12号上午11点从羽田起飞，返程机票1800元，改签费200元。"
                 "我已经订了11号晚上7点银座的寿司（定金300元）和11号上午10点的teamLab门票（180元）。想去明治神宫。",
         why="已订的寿司和 teamLab 必须锁定在说好的时间；12 号 11:00 起飞、09:00 值机，当天没有游览时间；"
             "明治神宫 16:30 关门，10 号 16:00 才出机场赶不上，只能排在 11 号。价格和改签费要按原数提取。",
         gold_request=dict(start_date="2026-12-10", end_date="2026-12-12", must_visit=["meiji_jingu"],
                           must_visit_days={}, avoid=[], interests_required=[],
                           interests_allowed=["food", "art", "culture", "nature"],
                           pace=None, hotel_place_id="hotel_shinjuku",
                           bookings=[b("flight_arrival", "haneda_airport", "2026-12-10T15:30:00+09:00"),
                                     b("flight_departure", "haneda_airport", "2026-12-12T11:00:00+09:00",
                                       price_cny=1800, change_fee_cny=200),
                                     b("restaurant", "sushi_ginza", "2026-12-11T19:00:00+09:00", price_cny=300),
                                     b("attraction", "teamlab_planets", "2026-12-11T10:00:00+09:00", price_cny=180)],
                           unknown_places=[]),
         plan_checks=dict(must_include=["meiji_jingu", "sushi_ginza", "teamlab_planets"], must_exclude=[],
                          on_day={"meiji_jingu": "2026-12-11"}, not_on_day={},
                          locked_at=[b("flight_arrival", "haneda_airport", "2026-12-10T15:30:00+09:00"),
                                     b("flight_departure", "haneda_airport", "2026-12-12T11:00:00+09:00"),
                                     b("restaurant", "sushi_ginza", "2026-12-11T19:00:00+09:00"),
                                     b("attraction", "teamlab_planets", "2026-12-11T10:00:00+09:00")],
                          no_visits_on=["2026-12-12"], expected_unplaceable=[], max_visits_per_day=4,
                          preference_tags=[])),
    dict(id="t06_must_visit_on_given_days", category="day_constraints",
         request="我12月11日到13日在东京玩，住浅草。11号一定要去筑地场外市场，12号想去皇居东御苑，13号去东京晴空塔。"
                 "喜欢拍照。11号早上8点就到羽田了，13号晚上7点羽田起飞。",
         why="三个地点都指定了日期。筑地周三/周日休息（11 号周五可以）；皇居东御苑周一/周五闭园（12 号周六可以，11 号不行）。",
         gold_request=dict(start_date="2026-12-11", end_date="2026-12-13",
                           must_visit=["tsukiji_outer_market", "imperial_east_gardens", "tokyo_skytree"],
                           must_visit_days={"tsukiji_outer_market": "2026-12-11",
                                            "imperial_east_gardens": "2026-12-12",
                                            "tokyo_skytree": "2026-12-13"},
                           avoid=[], interests_required=["photography"], interests_allowed=["city_view", "culture"],
                           pace=None, hotel_place_id="hotel_asakusa",
                           bookings=[b("flight_arrival", "haneda_airport", "2026-12-11T08:00:00+09:00"),
                                     b("flight_departure", "haneda_airport", "2026-12-13T19:00:00+09:00")],
                           unknown_places=[]),
         plan_checks=dict(must_include=["tsukiji_outer_market", "imperial_east_gardens", "tokyo_skytree"],
                          must_exclude=[],
                          on_day={"tsukiji_outer_market": "2026-12-11", "imperial_east_gardens": "2026-12-12",
                                  "tokyo_skytree": "2026-12-13"}, not_on_day={},
                          locked_at=[b("flight_arrival", "haneda_airport", "2026-12-11T08:00:00+09:00"),
                                     b("flight_departure", "haneda_airport", "2026-12-13T19:00:00+09:00")],
                          no_visits_on=[], expected_unplaceable=[], max_visits_per_day=4,
                          preference_tags=["photography"])),
    dict(id="t07_impossible_must_visit", category="infeasible_part",
         request="12月16日一天在东京转机，想去筑地场外市场和东京国立博物馆。16号早上9点到羽田，晚上9点羽田起飞。不住酒店。",
         why="12/16 是周三，筑地周三休息：不能排进去，必须明确告诉用户；东京国立博物馆周三开放，可以排。",
         gold_request=dict(start_date="2026-12-16", end_date="2026-12-16",
                           must_visit=["tsukiji_outer_market", "tokyo_national_museum"], must_visit_days={},
                           avoid=[], interests_required=[], interests_allowed=[], pace=None, hotel_place_id=None,
                           bookings=[b("flight_arrival", "haneda_airport", "2026-12-16T09:00:00+09:00"),
                                     b("flight_departure", "haneda_airport", "2026-12-16T21:00:00+09:00")],
                           unknown_places=[]),
         plan_checks=dict(must_include=["tokyo_national_museum"], must_exclude=["tsukiji_outer_market"], on_day={},
                          not_on_day={},
                          locked_at=[b("flight_arrival", "haneda_airport", "2026-12-16T09:00:00+09:00"),
                                     b("flight_departure", "haneda_airport", "2026-12-16T21:00:00+09:00")],
                          no_visits_on=[], expected_unplaceable=["tsukiji_outer_market"], max_visits_per_day=4,
                          preference_tags=[])),
    dict(id="t08_missing_dates", category="needs_information",
         request="下个月想去东京玩几天，喜欢二次元和热闹的地方，想去秋叶原。",
         why="没有具体日期：正确做法是追问日期，而不是自己编一个日期去排行程。",
         expected_status="needs_information",
         gold_request=dict(start_date=None, end_date=None, must_visit=["akihabara"], must_visit_days={}, avoid=[],
                           interests_required=["anime", "lively"], interests_allowed=["shopping"], pace=None,
                           hotel_place_id=None, bookings=[], unknown_places=[]),
         plan_checks=None),
]

# ---------------------------------------------------------------------------
# Chat edits on a fixed, hand-written base itinerary (2 days, Fri 12/11 - Sat 12/12)
# ---------------------------------------------------------------------------
J = "+09:00"


def act(aid, place, title, start, end, category="visit", locked=False, notes=""):
    return {"activity_id": aid, "place_id": place, "title": title, "start_at": f"2026-12-{start}{J}",
            "end_at": f"2026-12-{end}{J}", "category": category, "is_locked": locked, "notes": notes}


EDIT_BASE = {
    "trip": {
        "trip_id": "edit-base", "title": "东京两日（编辑测试）", "destination": "Tokyo",
        "start_date": "2026-12-11", "end_date": "2026-12-12", "timezone": "Asia/Tokyo",
        "preferences": {"interests": ["quiet", "anime"], "pace": "relaxed"}, "hotel_place_id": "hotel_shinjuku",
        "activities": [
            act("e1", "haneda_airport", "抵达羽田机场", "11T08:30:00", "11T09:00:00", "flight_arrival", True),
            act("e2", "senso_ji", "浅草寺", "11T10:15:00", "11T11:45:00", notes="你想去的地点"),
            act("e3", "senso_ji", "午餐（自由安排）", "11T12:00:00", "11T13:00:00", "free_time", notes="附近自由用餐"),
            act("e4", "teamlab_planets", "teamLab Planets（已预订）", "11T14:00:00", "11T16:00:00", locked=True,
                notes="你已预订"),
            act("e5", "character_street", "东京站动漫人物街", "11T16:30:00", "11T17:15:00", notes="PlanB 推荐"),
            act("e6", "character_street", "晚餐（自由安排）", "11T18:00:00", "11T19:30:00", "free_time",
                notes="附近自由用餐"),
            act("e7", "akihabara", "秋叶原电器街", "12T10:00:00", "12T11:30:00", notes="你想去的地点"),
            act("e8", "akihabara", "午餐（自由安排）", "12T12:00:00", "12T13:00:00", "free_time", notes="附近自由用餐"),
            act("e9", "hamarikyu", "滨离宫恩赐庭园", "12T13:30:00", "12T14:45:00", notes="PlanB 推荐"),
            act("e10", "haneda_airport", "羽田机场返程（18:00 起飞）", "12T16:00:00", "12T18:00:00",
                "flight_departure", True),
        ],
    },
    "bookings": [
        {"booking_id": "bk-out", "booking_type": "flight", "title": "去程航班（12/11 08:30 抵达羽田）",
         "place_id": "haneda_airport", "service_start": f"2026-12-11T08:30:00{J}",
         "service_end": f"2026-12-11T08:30:00{J}", "linked_activity_ids": ["e1"]},
        {"booking_id": "bk-team", "booking_type": "attraction", "title": "teamLab Planets 12/11 14:00",
         "place_id": "teamlab_planets", "service_start": f"2026-12-11T14:00:00{J}",
         "service_end": f"2026-12-11T16:00:00{J}", "linked_activity_ids": ["e4"]},
        {"booking_id": "bk-ret", "booking_type": "flight", "title": "返程航班（12/12 18:00 从羽田起飞）",
         "place_id": "haneda_airport", "service_start": f"2026-12-12T18:00:00{J}",
         "service_end": f"2026-12-12T18:00:00{J}", "linked_activity_ids": ["e10"]},
        {"booking_id": "bk-hotel", "booking_type": "hotel", "title": "新宿酒店 12/11–12/12", "place_id": "hotel_shinjuku",
         "service_start": f"2026-12-11T15:00:00{J}", "service_end": f"2026-12-12T11:00:00{J}"},
    ],
}

# expected:  status            ok | refused  (refused = must not change the itinerary on its own)
#            removed           activity ids that must be gone
#            must_keep         activity ids that must stay unchanged (place, start, end)
#            added_tags_any    an added visit (if any) must carry one of these tags
#            added_place       a specific place that must be added, with its allowed window
#            must_not_use      catalogue places that must NOT be used (substitutes for something else)
#            unknown_expected  the answer must say the restaurant's hours/price are unknown (not claim them)
# status "ask_with_options": when it does not fit, ask the user with concrete options (swap X / move to another
#            day or time); a bare "it does not fit" is wrong. Every option must be feasible.
# Preferences (decided with the reviewer): a case is correct when all interests_required are extracted;
# associated extras (interests_allowed or others) are not penalised.
EDITS = [
    dict(id="e01_remove_with_preference", request="我不想去浅草寺了，换一个安静一点的地方。",
         why="删掉浅草寺；如果补一个地点，必须是“安静”的，并且放得下；其余项目（尤其已订的 teamLab 和航班）不动。",
         expected=dict(status="ok", removed=["e2"], must_keep=["e1", "e4", "e5", "e7", "e9", "e10"],
                       added_tags_any=["quiet"], added_place=None, must_not_use=[], unknown_expected=False)),
    dict(id="e02_recommend_on_full_day", request="推荐一个二次元的地方加到12号。",
         why="12 号排满了（秋叶原、午餐、滨离宫、16:00 去机场）。不能只回答“放不下”：要给出具体选项询问用户，"
             "例如“把某某换成某个二次元地点”或“改到某天某时段去”。每个选项都必须可行，已订的 teamLab 和航班不能动。",
         expected=dict(status="ask_with_options", removed=[], must_keep=["e1", "e4", "e10"],
                       added_tags_any=["anime"], added_place=None, must_not_use=[], unknown_expected=False)),
    dict(id="e03_lunch_at_catalogue_restaurant", request="12号午饭想去筑地吃。",
         why="12/12 周六筑地营业（06:00–14:00）。午餐要放在 11:30–13:30 之间、在筑地，其余项目不动。",
         expected=dict(status="ok", removed=["e8"], must_keep=["e1", "e4", "e7", "e9", "e10"], added_tags_any=[],
                       added_place={"place_id": "tsukiji_outer_market", "day": "2026-12-12",
                                    "window": ["11:30", "13:30"]},
                       must_not_use=[], unknown_expected=False)),
    dict(id="e04_restaurant_not_in_catalogue", request="11号晚饭想去浅草那家天妇罗店。",
         why="这家店不在地点库里：不能换成库里的寿司店、思い出横丁或筑地；营业时间和价格未知，必须说明“无法确认”，不能编。",
         expected=dict(status="ok", removed=["e6"], must_keep=["e1", "e2", "e4", "e7", "e9", "e10"],
                       added_tags_any=[], added_place=None,
                       must_not_use=["sushi_ginza", "omoide_yokocho", "tsukiji_outer_market", "ameyoko"],
                       unknown_expected=True)),
    dict(id="e05_refuse_removing_booking", request="teamLab不想去了。",
         why="teamLab 是已预订、锁定的项目：不能自己删掉，应提示用户先确认/解锁（取消会涉及订单和费用）。",
         expected=dict(status="refused", removed=[], must_keep=["e1", "e2", "e4", "e5", "e7", "e9", "e10"],
                       added_tags_any=[], added_place=None, must_not_use=[], unknown_expected=False)),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for s in SETUP:
        s = {"type": "trip_setup", "today": TODAY, "split": "pilot", "expected_status": "ok", **s}
        (OUT / f"{s['id']}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
    (OUT / "edit_base.json").write_text(json.dumps(EDIT_BASE, ensure_ascii=False, indent=1))
    for e in EDITS:
        e = {"type": "edit", "base": "edit_base.json", "split": "pilot", **e}
        (OUT / f"{e['id']}.json").write_text(json.dumps(e, ensure_ascii=False, indent=1))
    write_review()
    print(f"{len(SETUP)} trip-setup + {len(EDITS)} edit scenarios -> {OUT}")


def write_review():
    from planb.data import load_world  # noqa: E402  (names for the review sheet only)

    w = load_world(extended=True)
    n = lambda pid: (w.place(pid).name_zh if w.place(pid) else pid)  # noqa: E731
    kind = {"flight_arrival": "去程到达", "flight_departure": "返程起飞", "restaurant": "餐厅", "attraction": "景点门票"}
    tags = {"quiet": "安静", "lively": "热闹", "anime": "二次元", "nature": "自然", "culture": "文化", "history": "历史",
            "art": "艺术", "science": "科学", "shopping": "购物", "food": "美食", "photography": "拍照", "city_view": "城市景观"}
    L = ["# 新功能评测场景：请核对（试点）", "",
         "这些标准答案是我根据**请求原文**和**地点库数据**（营业时间、休息日、标签）手写的，**没有用 PlanB 的输出**。",
         "请逐条看：请求是否自然？标准答案是否就是你作为用户期望的？有不同意见直接在对应条目下写，或在聊天里告诉我编号。",
         "", "日期对应星期：12/10 周四，11 周五，12 周六，13 周日，14 周一，15 周二，16 周三，17 周四。", "",
         "## 一、对话式新建行程（T01–T08）", ""]
    for s in SETUP:
        g, c = s["gold_request"], s["plan_checks"]
        L += [f"### {s['id']}", "", f"**请求**：{s['request']}", "", f"**考点**：{s['why']}", "", "**应理解为**："]
        L.append(f"- 日期：{g['start_date'] or '（未提供 → 应追问）'} ～ {g['end_date'] or '（未提供）'}")
        if g["must_visit"]:
            L.append("- 想去：" + "、".join(n(p) + (f"（{g['must_visit_days'][p]}）" if p in g["must_visit_days"] else "")
                                         for p in g["must_visit"]))
        if g["avoid"]:
            L.append("- 不去：" + "、".join(n(p) for p in g["avoid"]))
        L.append("- 喜好（必须有）：" + ("、".join(tags[t] for t in g["interests_required"]) or "无")
                 + ("；（合理联想，有也算对）" + "、".join(tags[t] for t in g["interests_allowed"]) if g["interests_allowed"] else ""))
        L.append("- 节奏：" + {"relaxed": "轻松", "normal": "适中", "packed": "紧凑", None: "未说明（默认适中）"}[g["pace"]])
        L.append("- 酒店：" + (n(g["hotel_place_id"]) if g["hotel_place_id"] else "未提供"))
        for bk in g["bookings"]:
            extra = "，".join(f"{k}={v}" for k, v in bk.items() if k in ("price_cny", "change_fee_cny"))
            L.append(f"- 预订：{kind[bk['kind']]} {n(bk['place_id'])} {bk['start'][5:16].replace('T', ' ')}"
                     + (f"（{extra}）" if extra else ""))
        if g["unknown_places"]:
            L.append("- 地点库里没有（应报告，不能替换）：" + "、".join(g["unknown_places"]))
        if c:
            L += ["", "**计划必须满足**："]
            if c["must_include"]:
                L.append("- 必须包含：" + "、".join(n(p) for p in c["must_include"]))
            if c["must_exclude"]:
                L.append("- 必须不出现：" + "、".join(n(p) for p in c["must_exclude"]))
            for p, d in c["on_day"].items():
                L.append(f"- {n(p)} 必须在 {d}")
            for p, ds in c["not_on_day"].items():
                L.append(f"- {n(p)} 不能在 " + "、".join(ds))
            for d in c["no_visits_on"]:
                L.append(f"- {d} 没有游览时间（不应安排景点）")
            for p in c["expected_unplaceable"]:
                L.append(f"- {n(p)} 排不进去，必须明确告诉用户")
            L.append(f"- 预订必须锁定在原时间；每天景点不超过 {c['max_visits_per_day']} 个；没有硬约束冲突；不出现地点库以外的地点")
            if c["preference_tags"]:
                L.append("- 额外推荐的地点应符合：" + "、".join(tags[t] for t in c["preference_tags"]))
        else:
            L += ["", "**正确结果**：不生成行程，追问日期。"]
        L.append("")
    L += ["## 二、聊天修改（E01–E05）", "", "所有修改都在同一个手写的基础行程上进行（12/11 周五 – 12/12 周六，住新宿，喜好：安静、二次元）：", "",
          "| 编号 | 时间 | 活动 | 说明 |", "|---|---|---|---|"]
    for a in EDIT_BASE["trip"]["activities"]:
        lock = "🔒 " if a["is_locked"] else ""
        L.append(f"| {a['activity_id']} | {a['start_at'][5:16].replace('T', ' ')}–{a['end_at'][11:16]} | {lock}{a['title']} | {a['notes']} |")
    L.append("")
    for e in EDITS:
        x = e["expected"]
        L += [f"### {e['id']}", "", f"**请求**：{e['request']}", "", f"**考点**：{e['why']}", "", "**标准答案**："]
        L.append("- 结果：" + {"ok": "生成修改方案", "refused": "不自动修改，提示用户确认",
                               "ask_with_options": "给出具体选项询问用户（替换某项 / 改到某天某时段），不能只说放不下"}[x["status"]])
        if x["removed"]:
            L.append("- 必须去掉：" + "、".join(x["removed"]))
        L.append("- 必须保持不变：" + "、".join(x["must_keep"]))
        if x["added_tags_any"]:
            L.append("- 新加的地点必须带标签：" + "、".join(tags[t] for t in x["added_tags_any"]))
        if x["added_place"]:
            ap = x["added_place"]
            L.append(f"- 必须加入：{n(ap['place_id'])}，{ap['day']} {ap['window'][0]}–{ap['window'][1]} 之间")
        if x["must_not_use"]:
            L.append("- 不能用来代替的库内地点：" + "、".join(n(p) for p in x["must_not_use"]))
        if x["unknown_expected"]:
            L.append("- 必须说明营业时间/价格未知（不能当作已确认）")
        L.append("")
    L += ["## 三、已确认的评分规则（2026-11-19 核对）", "",
          "1. **喜好**：原文明确说的必须提取到；联想出来的额外喜好（如“历史 → 文化”）也算对，不扣分。",
          "2. **T03**：“筑地市场”对应地点库的“筑地场外市场”。",
          "3. **E02**：放不下时不能只说“放不下”，必须给出具体选项询问用户（把某某换成 X / 改到某天某时段）。",
          "", "## 四、还没确认的地方", "",
          "- T05 “明治神宫只能排在 11 号”是根据营业时间和到达时间推出来的（10 号最早 17:05 到，16:30 已关门）。",
          "- E04：餐厅不在地点库时，必须说明“营业时间/价格未知”。",
          "- 还缺什么类型的场景？例如：多人出行、预算限制、规划时就知道会下雨……"]
    (OUT / "REVIEW.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(ROOT))
    main()
