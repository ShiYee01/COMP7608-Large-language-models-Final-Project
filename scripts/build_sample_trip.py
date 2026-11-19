"""Build the sample Tokyo 3-day trip and its bookings (SIMULATED demo data).

Story D numbers from PROJECT_CONTEXT.md §4: return flight paid 1800, change fee 200,
fare difference 350, extra hotel night 600  ->  incremental cost 1150 CNY.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TZ = "+09:00"


def t(day, hm):
    return f"2026-12-{day:02d}T{hm}:00{TZ}"


places = {p["place_id"]: p for p in json.loads((ROOT / "data/places/tokyo_places.json").read_text())}


def act(aid, pid, day, start, end, category="visit", locked=False, priority=2, title=None, notes=""):
    p = places[pid]
    return {"activity_id": aid, "place_id": pid, "title": title or p["name_zh"] or p["name"],
            "start_at": t(day, start), "end_at": t(day, end), "category": category, "priority": priority,
            "is_locked": locked, "status": "planned", "estimated_cost_minor": p["entry_cost_minor"], "notes": notes}


trip = {
    "trip_id": "trip-tokyo-3day",
    "title": "东京三日游（演示）",
    "destination": "Tokyo",
    "start_date": "2026-12-10",
    "end_date": "2026-12-12",
    "timezone": "Asia/Tokyo",
    "party_size": 1,
    "budget": {"amount_minor": 800000, "currency": "CNY", "is_hard_limit": False},
    "preferences": {"interests": ["photography", "nature", "culture"], "pace": "relaxed",
                    "day_start": "08:00", "day_end": "22:00"},
    "hotel_place_id": "hotel_shinjuku",
    "activities": [
        act("a1", "haneda_airport", 10, "11:30", "12:00", "flight_arrival", locked=True, title="抵达羽田机场"),
        act("a2", "senso_ji", 10, "13:30", "15:00"),
        act("a3", "tokyo_skytree", 10, "15:30", "17:00"),
        act("a4", "omoide_yokocho", 10, "18:30", "20:00", "meal", title="思い出横丁 晚餐"),
        act("a5", "meiji_jingu", 11, "09:00", "10:30"),
        act("a6", "harajuku_takeshita", 11, "10:45", "12:00"),
        act("a7", "teamlab_planets", 11, "14:00", "16:00", priority=3, notes="已预约 14:00-14:30 入场"),
        act("a8", "sushi_ginza", 11, "18:30", "20:00", "meal", locked=True, priority=3, title="银座寿司晚餐（已订位）"),
        act("a9", "ueno_park", 12, "09:00", "10:00"),
        act("a10", "tokyo_national_museum", 12, "10:15", "12:00"),
        act("a11", "akihabara", 12, "12:30", "14:00"),
        act("a12", "haneda_airport", 12, "16:00", "18:00", "flight_departure", locked=True, title="羽田机场返程（18:00 起飞）"),
    ],
    "status": "active",
    "revision": 1,
}

bookings = [
    {"booking_id": "flight-out", "booking_type": "flight", "title": "去程航班 上海→东京羽田",
     "provider_name": "Demo Air", "place_id": "haneda_airport",
     "service_start": t(10, "08:00"), "service_end": t(10, "11:30"), "paid_minor": 180000,
     "linked_activity_ids": ["a1"],
     "policy": {"change_allowed": True, "cancel_allowed": False, "change_fee_minor": 20000,
                "negative_fare_difference_refunded": False, "conditions": "改签收手续费 ¥200 + 票价差；差价为负不退"},
     "quotes": []},
    {"booking_id": "flight-ret", "booking_type": "flight", "title": "返程航班 东京羽田→上海",
     "provider_name": "Demo Air", "place_id": "haneda_airport",
     "service_start": t(12, "18:00"), "service_end": t(12, "20:30"), "paid_minor": 180000,
     "linked_activity_ids": ["a12"],
     "policy": {"change_allowed": True, "cancel_allowed": False, "change_fee_minor": 20000,
                "negative_fare_difference_refunded": False, "conditions": "改签收手续费 ¥200 + 票价差；差价为负不退"},
     "quotes": [
         {"quote_id": "q-flight-1213", "action": "change_date", "target_start": t(13, "18:00"),
          "target_end": t(13, "20:30"), "amount_minor": 35000, "available": True,
          "notes": "改到 12/13 18:00 同航线，票价差 ¥350（模拟报价）"},
         {"quote_id": "q-flight-1211", "action": "change_date", "target_start": t(11, "23:00"),
          "target_end": t(12, "01:30"), "amount_minor": 10000, "available": True,
          "notes": "改到 12/11 23:00 红眼航班，票价差 ¥100（模拟报价）"},
     ]},
    {"booking_id": "hotel-1", "booking_type": "hotel", "title": "新宿演示酒店 12/10 入住 - 12/12 退房（2 晚）",
     "provider_name": "PlanB Demo Hotel", "place_id": "hotel_shinjuku",
     "service_start": t(10, "15:00"), "service_end": t(12, "11:00"), "paid_minor": 120000,
     "linked_activity_ids": [],
     "policy": {"change_allowed": True, "cancel_allowed": False, "early_checkout_refund_minor": 0,
                "conditions": "提前退房不退款；续住按报价"},
     "quotes": [
         {"quote_id": "q-hotel-ext-1212", "action": "extend_stay", "target_start": t(12, "15:00"),
          "target_end": t(13, "11:00"), "amount_minor": 60000, "available": True,
          "notes": "续住 12/12 一晚 ¥600（模拟报价，假设可续住）"},
     ]},
    {"booking_id": "att-teamlab", "booking_type": "attraction", "title": "teamLab Planets 门票 12/11 14:00-14:30 入场",
     "provider_name": "teamLab (demo)", "place_id": "teamlab_planets",
     "service_start": t(11, "14:00"), "service_end": t(11, "14:30"), "paid_minor": 18000,
     "linked_activity_ids": ["a7"],
     "policy": {"change_allowed": False, "cancel_allowed": False, "refund_on_cancel_minor": 0,
                "provider_cancellation_refund_minor": 18000,
                "conditions": "个人原因不可改不可退；场馆原因关闭全额退款"},
     "quotes": []},
    {"booking_id": "rest-sushi", "booking_type": "restaurant", "title": "银座寿司 12/11 18:30 订位（定金 ¥300）",
     "provider_name": "Ginza Sushi (demo)", "place_id": "sushi_ginza",
     "service_start": t(11, "18:30"), "service_end": t(11, "20:00"), "paid_minor": 30000,
     "linked_activity_ids": ["a8"],
     "policy": {"change_allowed": False, "cancel_allowed": True, "refund_on_cancel_minor": 0,
                "provider_cancellation_refund_minor": 30000,
                "free_cancel_deadline": t(10, "18:30"),
                "conditions": "提前 24 小时取消退定金，否则定金不退"},
     "quotes": []},
]

(ROOT / "data/sample_trips/tokyo_3day.json").write_text(json.dumps(trip, ensure_ascii=False, indent=1))
(ROOT / "data/sample_bookings/tokyo_bookings.json").write_text(json.dumps(bookings, ensure_ascii=False, indent=1))
print("ok")
