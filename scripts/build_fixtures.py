"""Build the static Tokyo demo fixtures (places + travel-time matrix).

All values are SIMULATED for a course demo. Coordinates are approximate, opening
hours / prices are illustrative and NOT verified real-world data.
Travel times are synthetic estimates derived from straight-line distance:
  walk  if distance < 1.2 km : 15 min per km (min 5)
  transit otherwise          : 12 + 3.2 min per km, rounded up to 5 min
A few pairs are intentionally left out so the system must handle UNKNOWN travel time.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALL = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def hours(open_, close, closed=()):
    return {d: [[open_, close]] for d in ALL if d not in closed}


# place_id, name, name_zh, category, indoor, lat, lon, area, opening, visit_min, entry_cost(CNY fen), tags, reservation
PLACES = [
    ("haneda_airport", "Haneda Airport (HND)", "羽田机场", "airport", True, 35.5494, 139.7798, "Ota", hours("00:00", "23:59"), 120, 0, [], False),
    ("hotel_shinjuku", "PlanB Demo Hotel Shinjuku", "新宿演示酒店", "hotel", True, 35.6905, 139.6995, "Shinjuku", hours("00:00", "23:59"), 0, 0, [], False),
    ("senso_ji", "Senso-ji Temple", "浅草寺", "temple", False, 35.7148, 139.7967, "Asakusa", hours("06:00", "17:00"), 90, 0, ["culture", "photography"], False),
    ("tokyo_skytree", "Tokyo Skytree", "东京晴空塔", "viewpoint", True, 35.7101, 139.8107, "Oshiage", hours("10:00", "21:00"), 90, 15000, ["photography", "city_view"], False),
    ("ueno_park", "Ueno Park", "上野公园", "park", False, 35.7156, 139.7745, "Ueno", hours("05:00", "23:00"), 60, 0, ["nature", "photography"], False),
    ("tokyo_national_museum", "Tokyo National Museum", "东京国立博物馆", "museum", True, 35.7188, 139.7765, "Ueno", hours("09:30", "17:00", closed=("mon",)), 105, 5000, ["culture", "art"], False),
    ("nature_science_museum", "National Museum of Nature and Science", "国立科学博物馆", "museum", True, 35.7163, 139.7764, "Ueno", hours("09:00", "17:00", closed=("mon",)), 90, 3500, ["nature", "science"], False),
    ("meiji_jingu", "Meiji Jingu Shrine", "明治神宫", "shrine", False, 35.6764, 139.6993, "Harajuku", hours("06:00", "16:30"), 90, 0, ["nature", "culture", "photography"], False),
    ("harajuku_takeshita", "Takeshita Street", "竹下通", "shopping", False, 35.6716, 139.7031, "Harajuku", hours("10:00", "20:00"), 75, 0, ["shopping", "photography"], False),
    ("teamlab_planets", "teamLab Planets", "teamLab Planets", "museum", True, 35.6491, 139.7898, "Toyosu", hours("09:00", "22:00"), 120, 18000, ["art", "photography"], True),
    ("sushi_ginza", "Ginza Sushi Dinner (demo)", "银座寿司晚餐（演示）", "food", True, 35.6717, 139.7650, "Ginza", hours("17:00", "22:00"), 90, None, ["food"], True),
    ("omoide_yokocho", "Omoide Yokocho", "思い出横丁", "food", False, 35.6933, 139.6994, "Shinjuku", hours("17:00", "23:59"), 90, 15000, ["food", "photography"], False),
    ("akihabara", "Akihabara Electric Town", "秋叶原电器街", "shopping", True, 35.6984, 139.7731, "Akihabara", hours("10:00", "21:00"), 90, 0, ["shopping", "anime"], False),
    ("shibuya_sky", "Shibuya Sky", "涩谷SKY", "viewpoint", False, 35.6585, 139.7022, "Shibuya", hours("10:00", "22:30"), 75, 12000, ["photography", "city_view"], True),
    ("mori_art_museum", "Mori Art Museum", "森美术馆", "museum", True, 35.6604, 139.7292, "Roppongi", hours("10:00", "22:00"), 90, 10000, ["art", "photography"], False),
    ("tokyo_tower", "Tokyo Tower", "东京塔", "viewpoint", True, 35.6586, 139.7454, "Shiba", hours("09:00", "23:00"), 75, 6000, ["photography", "city_view"], False),
    ("shinjuku_gyoen", "Shinjuku Gyoen National Garden", "新宿御苑", "park", False, 35.6852, 139.7100, "Shinjuku", hours("09:00", "17:30", closed=("mon",)), 90, 2500, ["nature", "photography"], False),
    ("imperial_east_gardens", "Imperial Palace East Gardens", "皇居东御苑", "park", False, 35.6852, 139.7528, "Chiyoda", hours("09:00", "16:00", closed=("mon", "fri")), 75, 0, ["nature", "culture"], False),
    ("tsukiji_outer_market", "Tsukiji Outer Market", "筑地场外市场", "food", False, 35.6654, 139.7707, "Tsukiji", hours("06:00", "14:00", closed=("wed", "sun")), 75, 8000, ["food"], False),
    ("ghibli_museum", "Ghibli Museum (demo)", "吉卜力美术馆（演示）", "museum", True, 35.6962, 139.5704, "Mitaka", hours("10:00", "18:00", closed=("tue",)), 90, 5000, ["art", "anime"], True),
    ("inokashira_park", "Inokashira Park", "井之头恩赐公园", "park", False, 35.7000, 139.5733, "Kichijoji", hours("00:00", "23:59"), 75, 0, ["nature", "photography"], False),
    ("odaiba_seaside", "Odaiba Seaside Park", "台场海滨公园", "park", False, 35.6298, 139.7745, "Odaiba", hours("00:00", "23:59"), 60, 0, ["nature", "photography", "city_view"], False),
    ("ginza_six", "GINZA SIX", "GINZA SIX 商场", "shopping", True, 35.6696, 139.7640, "Ginza", hours("10:30", "20:30"), 75, 0, ["shopping"], False),
    # Opening hours intentionally UNKNOWN to exercise unknown-constraint handling.
    ("yanaka_ginza", "Yanaka Ginza Shopping Street", "谷中银座商店街", "shopping", False, 35.7277, 139.7660, "Yanaka", None, 60, 0, ["culture", "food", "photography"], False),
]

# Pairs intentionally missing from the matrix (travel time UNKNOWN).
MISSING_PAIRS = {("yanaka_ginza", "ghibli_museum"), ("yanaka_ginza", "odaiba_seaside")}


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(d))


def travel(dist):
    if dist < 1.2:
        return "walk", max(5, math.ceil(dist * 15 / 5) * 5), 0
    minutes = math.ceil((12 + 3.2 * dist) / 5) * 5
    return "transit", minutes, int(round(8 + 0.6 * dist)) * 100  # rough fare in CNY fen


def main():
    places = []
    for pid, name, zh, cat, indoor, lat, lon, area, opening, visit, cost, tags, resv in PLACES:
        places.append({
            "place_id": pid, "name": name, "name_zh": zh, "category": cat, "indoor": indoor,
            "latitude": lat, "longitude": lon, "area": area, "opening_hours": opening,
            "closed_dates": [], "suggested_visit_minutes": visit, "entry_cost_minor": cost,
            "tags": tags, "reservation_required": resv, "data_source": "fixture",
            "verified_status": "simulated",
        })
    matrix = []
    for i, a in enumerate(PLACES):
        for b in PLACES[i + 1:]:
            if (a[0], b[0]) in MISSING_PAIRS or (b[0], a[0]) in MISSING_PAIRS:
                continue
            mode, minutes, fare = travel(haversine_km((a[5], a[6]), (b[5], b[6])))
            matrix.append({"origin_place_id": a[0], "destination_place_id": b[0], "mode": mode,
                           "travel_minutes": minutes, "travel_cost_minor": fare, "source": "synthetic_estimate"})
    (ROOT / "data/places/tokyo_places.json").write_text(json.dumps(places, ensure_ascii=False, indent=1))
    (ROOT / "data/travel_times/tokyo_matrix.json").write_text(json.dumps(matrix, ensure_ascii=False, indent=1))
    print(f"{len(places)} places, {len(matrix)} travel pairs")


if __name__ == "__main__":
    main()
