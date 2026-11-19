"""Write the 10 pilot evaluation scenarios.

Ground truth is HAND-SPECIFIED from the fixture rules (not produced by the PlanB
engine) and should be audited by a human. Cost = additional out-of-pocket cash
caused by changes to EXISTING bookings, in CNY fen; entry fees of new activities
are excluded.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evaluation/scenarios"
ALL = [f"a{i}" for i in range(1, 13)]


def keep_except(*ids):
    return [a for a in ALL if a not in ids]


S = [
    dict(scenario_id="s01_extend_known_cost", category="trip_extension",
         description="Story D：延长一天，机票改签费/差价与续住报价都已知",
         user_request="我想在东京多待一天，12月13日再回来，之前安排好的景点尽量不要改。",
         gold_event={"event_type": "trip_extension", "parameters": {"new_end_date": "2026-12-13"}},
         ground_truth={"expected_status": "ok", "affected_booking_ids": ["flight-ret", "hotel-1"],
                       "expected_cost_minor": 115000, "cost_unknown": False,
                       "must_keep": keep_except("a12"), "must_change": ["a12"]}),
    dict(scenario_id="s02_extend_unknown_flight_cost", category="trip_extension",
         description="Story F：延长一天，但缺少改签手续费和新航班报价",
         user_request="航空公司说可以改签，我想把回国日期推迟到12月13日，其他安排不变。",
         overrides={"bookings": {"flight-ret": {"quotes": [], "policy.change_fee_minor": None}}},
         gold_event={"event_type": "trip_extension", "parameters": {"new_end_date": "2026-12-13"}},
         ground_truth={"expected_status": "ok", "affected_booking_ids": ["flight-ret", "hotel-1"],
                       "expected_cost_minor": None, "cost_unknown": True,
                       "must_keep": keep_except("a12"), "must_change": ["a12"]}),
    dict(scenario_id="s03_rain_day2_morning", category="weather_change",
         description="12/11 上午暴雨，明治神宫与竹下通为户外",
         user_request="天气预报说12月11日上午8点到下午1点有暴雨，帮我调整一下行程。",
         gold_event={"event_type": "weather_change", "affected_start": "2026-12-11T08:00:00+09:00",
                     "affected_end": "2026-12-11T13:00:00+09:00"},
         ground_truth={"expected_status": "ok", "affected_booking_ids": [], "expected_cost_minor": 0,
                       "cost_unknown": False, "must_keep": keep_except("a5", "a6"), "must_change": ["a5", "a6"]}),
    dict(scenario_id="s04_rain_day1_afternoon", category="weather_change",
         description="12/10 下午大雨，只有浅草寺是户外",
         user_request="12月10日下午1点到6点会下大雨，请帮我改一下当天的安排。",
         gold_event={"event_type": "weather_change", "affected_start": "2026-12-10T13:00:00+09:00",
                     "affected_end": "2026-12-10T18:00:00+09:00"},
         ground_truth={"expected_status": "ok", "affected_booking_ids": [], "expected_cost_minor": 0,
                       "cost_unknown": False, "must_keep": keep_except("a2"), "must_change": ["a2"]}),
    dict(scenario_id="s05_museum_closed", category="place_closed",
         description="东京国立博物馆 12/12 临时闭馆，无关联订单",
         user_request="东京国立博物馆12月12日临时闭馆，帮我换个安排。",
         gold_event={"event_type": "place_closed", "affected_place_ids": ["tokyo_national_museum"],
                     "affected_start": "2026-12-12T00:00:00+09:00", "affected_end": "2026-12-13T00:00:00+09:00"},
         ground_truth={"expected_status": "ok", "affected_booking_ids": [], "expected_cost_minor": 0,
                       "cost_unknown": False, "must_keep": keep_except("a10"), "must_change": ["a10"]}),
    dict(scenario_id="s06_teamlab_closed_refund", category="place_closed",
         description="teamLab 12/11 闭馆；门票规则：场馆原因全额退款 ¥180",
         user_request="teamLab Planets 通知12月11日全天闭馆，我的行程和门票怎么办？",
         gold_event={"event_type": "place_closed", "affected_place_ids": ["teamlab_planets"],
                     "affected_start": "2026-12-11T00:00:00+09:00", "affected_end": "2026-12-12T00:00:00+09:00"},
         ground_truth={"expected_status": "ok", "affected_booking_ids": ["att-teamlab"],
                       "expected_cost_minor": -18000, "cost_unknown": False,
                       "must_keep": keep_except("a7"), "must_change": ["a7"]}),
    dict(scenario_id="s07_morning_transport_delay", category="transport_delay",
         description="12/11 早上地铁延误到 10:30，连锁影响上午安排；teamLab 入场窗 14:00-14:30",
         user_request="12月11日早上地铁大面积延误，我10点半之前都到不了任何景点。",
         gold_event={"event_type": "transport_delay", "affected_start": "2026-12-11T08:00:00+09:00",
                     "affected_end": "2026-12-11T10:30:00+09:00"},
         ground_truth={"expected_status": "ok", "affected_booking_ids": [], "expected_cost_minor": 0,
                       "cost_unknown": False,
                       "must_keep": ["a1", "a2", "a3", "a4", "a8", "a9", "a10", "a11", "a12"],
                       "must_change": ["a5"]}),
    dict(scenario_id="s08_reservation_conflict_infeasible", category="reservation_change",
         description="teamLab 入场被商家改到 18:00（不可再改），与锁定的 18:30 寿司晚餐冲突 → 无解，需用户决定",
         user_request="teamLab 通知我12月11日的入场时间被改到了晚上18:00，而且不能再改。但我18:30在银座订了寿司，这个不能动。帮我看看怎么办。",
         gold_event={"event_type": "reservation_change",
                     "parameters": {"booking_id": "att-teamlab", "new_start": "2026-12-11T18:00:00+09:00"}},
         ground_truth={"expected_status": "infeasible", "affected_booking_ids": [], "expected_cost_minor": None,
                       "cost_unknown": False, "must_keep": [], "must_change": []}),
    dict(scenario_id="s09_shorten_trip", category="trip_shortening",
         description="提前一天回国（12/11 23:00 红眼航班），酒店提前退房不退款",
         user_request="家里有事，我需要提前一天回去，改成12月11日晚上的航班。",
         gold_event={"event_type": "trip_shortening", "parameters": {"new_end_date": "2026-12-11"}},
         ground_truth={"expected_status": "ok", "affected_booking_ids": ["flight-ret", "hotel-1"],
                       "expected_cost_minor": 30000, "cost_unknown": False,
                       "must_keep": ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8"],
                       "must_change": ["a9", "a10", "a11", "a12"]}),
    dict(scenario_id="s10_locked_place_closed_infeasible", category="place_closed",
         description="用户锁定的浅草寺 12/10 全天不开放 → 无法在保留锁定的前提下修复",
         user_request="浅草寺12月10日全天不对外开放。浅草寺这个时间段我已经锁定了，不允许改时间或删除。",
         overrides={"activities": {"a2": {"is_locked": True}}},
         gold_event={"event_type": "place_closed", "affected_place_ids": ["senso_ji"],
                     "affected_start": "2026-12-10T00:00:00+09:00", "affected_end": "2026-12-11T00:00:00+09:00"},
         ground_truth={"expected_status": "infeasible", "affected_booking_ids": [], "expected_cost_minor": None,
                       "cost_unknown": False, "must_keep": [], "must_change": []}),
]

OUT.mkdir(parents=True, exist_ok=True)
for s in S:
    s.setdefault("split", "pilot")
    s.setdefault("overrides", {})
    (OUT / f"{s['scenario_id']}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
print(len(S), "scenarios")
