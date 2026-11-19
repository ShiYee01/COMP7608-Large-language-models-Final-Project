"""Conversational trip setup: extraction (rule-based path), sanitising and planning."""
from datetime import date

import pytest

from planb.data import load_world
from planb.llm import LLMClient
from planb.planner import plan_trip
from planb.trip_request import MustVisit, StatedBooking, TripRequest, extract_trip_request, sanitize, summarize

TODAY = date(2026, 11, 19)
DEMO = ("我12月10日到12日去东京玩，想去浅草寺和秋叶原，不想去涩谷十字路口。我喜欢安静的地方，也喜欢二次元，"
        "节奏轻松一点。我订了10号11:30到羽田的航班、12号18:00起飞的返程，酒店在新宿，11号下午2点有teamLab的门票。")


@pytest.fixture(scope="module")
def xworld():
    return load_world(extended=True)


@pytest.fixture(scope="module")
def mock():
    return LLMClient(provider="mock")


def test_base_catalogue_is_unchanged():
    # the recorded evaluation uses the base catalogue; it must not grow with the app's catalogue
    assert len(load_world().places) == 24


def test_rule_extraction_of_demo_paragraph(xworld, mock):
    req, how = extract_trip_request(DEMO, xworld, mock, today=TODAY)
    assert how == "rule"
    assert (req.start_date, req.end_date) == (date(2026, 12, 10), date(2026, 12, 12))
    assert [m.place_id for m in req.must_visit] == ["senso_ji", "akihabara"]
    assert req.avoid == ["shibuya_crossing"]
    assert set(req.interests) == {"quiet", "anime"}
    assert req.pace == "relaxed"
    assert req.hotel.place_id == "hotel_shinjuku"
    kinds = {b.kind: b for b in req.bookings}
    assert kinds["flight_arrival"].start.hour == 11 and kinds["flight_arrival"].start.minute == 30
    assert kinds["flight_departure"].start.day == 12 and kinds["flight_departure"].start.hour == 18
    assert kinds["attraction"].place_id == "teamlab_planets" and kinds["attraction"].start.hour == 14
    # nothing about prices was said -> unknown, never 0
    assert all(b.price_cny is None and b.change_fee_cny is None for b in req.bookings)
    assert "未知" in summarize(req, xworld)


def test_correction_updates_previous_request(xworld, mock):
    req, _ = extract_trip_request(DEMO, xworld, mock, today=TODAY)
    req2, _ = extract_trip_request("酒店其实在浅草", xworld, mock, today=TODAY, previous=req)
    assert req2.hotel.place_id == "hotel_asakusa"
    assert req2.bookings == req.bookings and req2.must_visit == req.must_visit


def test_unknown_place_is_reported_not_replaced(xworld, mock):
    req, _ = extract_trip_request("12月10日到11日去东京，还想去火星博物馆", xworld, mock, today=TODAY)
    assert req.unknown_places == ["火星博物馆"]
    assert req.must_visit == []


def test_sanitize_drops_invented_ids(xworld):
    req = TripRequest(start_date=date(2026, 12, 10), end_date=date(2026, 12, 11),
                      must_visit=[MustVisit(place_id="not_a_place"), MustVisit(place_id="akihabara")],
                      interests=["anime", "made_up_tag"],
                      bookings=[StatedBooking(kind="attraction", place_id="nowhere", title="x")])
    clean = sanitize(req, xworld)
    assert [m.place_id for m in clean.must_visit] == ["akihabara"]
    assert clean.unknown_places == ["not_a_place"]
    assert clean.interests == ["anime"]
    assert clean.bookings == [] and clean.notes


def test_plan_respects_bookings_must_visits_and_avoid(xworld, mock):
    req, _ = extract_trip_request(DEMO, xworld, mock, today=TODAY)
    plan = plan_trip(xworld, req)
    acts = plan.trip.sorted_activities()
    places = [a.place_id for a in acts]
    assert plan.validation.feasibility_status == "valid" and not plan.validation.hard_violations
    assert {"senso_ji", "akihabara", "teamlab_planets"} <= set(places)
    assert "shibuya_crossing" not in places
    team = next(a for a in acts if a.place_id == "teamlab_planets")
    assert team.is_locked and xworld.local(team.start_at).hour == 14
    assert acts[0].category == "flight_arrival" and acts[-1].category == "flight_departure"
    # recommendations follow the stated preferences
    recommended = [a for a in acts if a.notes == "PlanB 推荐"]
    assert recommended and all({"quiet", "anime"} & set(xworld.place(a.place_id).tags) for a in recommended)
    # relaxed pace: at most 3 visits per day
    per_day = {}
    for a in acts:
        if a.category == "visit":
            per_day[xworld.local(a.start_at).date()] = per_day.get(xworld.local(a.start_at).date(), 0) + 1
    assert max(per_day.values()) <= 3
    # bookings are recorded with unknown prices/rules, linked to their activities
    assert {b.booking_type for b in plan.bookings} == {"flight", "attraction", "hotel"}
    assert all(b.paid_minor is None for b in plan.bookings)


def test_plan_requires_dates(xworld):
    with pytest.raises(ValueError):
        plan_trip(xworld, TripRequest())


def test_generated_trip_supports_replanning_with_unknown_cost(xworld, mock):
    from planb.agent import PlanBAgent
    from planb.store import TripStore

    req, _ = extract_trip_request(DEMO, xworld, mock, today=TODAY)
    plan = plan_trip(xworld, req)
    agent = PlanBAgent(TripStore(plan.trip, plan.bookings, xworld), mock)
    turn = agent.handle("我想在东京多待一天，12月13日再回来。")
    assert turn.state == "WAITING_FOR_APPROVAL"
    p = agent.store.pending()[0]
    # fees were never stated -> the extra cost must be unknown, not 0
    assert p.cost_estimate.total_additional_minor is None and p.cost_estimate.unknown_components


def test_meal_slot_never_blocks_travel_to_the_airport(xworld):
    # far-west sights on the last day + evening flight: the dinner slot must not eat the travel time
    req = TripRequest(start_date=date(2026, 12, 13), end_date=date(2026, 12, 13), interests=["quiet"], pace="relaxed",
                      must_visit=[MustVisit(place_id="jindaiji")],
                      bookings=[StatedBooking(kind="flight_arrival", place_id="haneda_airport",
                                              start="2026-12-13T09:00:00+09:00"),
                                StatedBooking(kind="flight_departure", place_id="haneda_airport",
                                              start="2026-12-13T21:00:00+09:00")])
    plan = plan_trip(xworld, sanitize(req, xworld))
    assert not plan.validation.hard_violations
