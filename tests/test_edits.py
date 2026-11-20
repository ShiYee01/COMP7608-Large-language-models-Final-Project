"""Chat edits on a trip created by conversation: meals, removal, recommendations, preferences."""
from datetime import date

import pytest

from planb.agent import PlanBAgent
from planb.data import load_world
from planb.edits import detect_edit
from planb.llm import LLMClient
from planb.planner import plan_trip
from planb.store import TripStore
from planb.trip_request import extract_trip_request

DEMO = ("我12月10日到12日去东京玩，想去浅草寺和秋叶原，不想去涩谷十字路口。我喜欢安静的地方，也喜欢二次元，"
        "节奏轻松一点。我订了10号11:30到羽田的航班、12号18:00起飞的返程，酒店在新宿，11号下午2点有teamLab的门票。")


@pytest.fixture()
def setup():
    world = load_world(extended=True)  # fresh per test: user-provided restaurants are added to the world
    llm = LLMClient(provider="mock")
    req, _ = extract_trip_request(DEMO, world, llm, today=date(2026, 11, 19))
    plan = plan_trip(world, req)
    agent = PlanBAgent(TripStore(plan.trip, plan.bookings, world), llm, avoided=set(req.avoid))
    return world, agent


def _meals(world, trip, day=None):
    return [a for a in trip.sorted_activities() if a.category == "free_time"
            and (day is None or world.local(a.start_at).date() == day)]


def test_routing_keeps_disruptions_on_the_evaluated_path():
    assert detect_edit("天气预报说12月11日上午8点到下午1点有暴雨，帮我调整一下行程。") is None
    assert detect_edit("浅草寺12月10日全天不对外开放。浅草寺这个时间段我已经锁定了，不允许改时间或删除。") is None
    assert detect_edit("我想在东京多待一天，12月13日再回来") is None
    assert detect_edit("我不想去浅草寺了") == "remove_activity"
    assert detect_edit("12号午饭我想去筑地吃") == "set_meal"
    assert detect_edit("12号午饭不用安排了") == "skip_meal"
    assert detect_edit("11号晚上想在浅草找家天妇罗吃") == "set_meal"
    assert detect_edit("teamLab 通知我12月11日的入场时间被改到了晚上18:00，而且不能再改。但我18:30在银座订了寿司，这个不能动。") is None
    assert detect_edit("推荐一个二次元的地方") == "recommend"
    assert detect_edit("把高达加到12号") == "recommend"
    assert detect_edit("我更喜欢安静的地方") == "update_preferences"


def test_plan_has_free_meal_slots_and_stays_valid(setup):
    world, agent = setup
    trip = agent.store.trip
    meals = _meals(world, trip)
    assert {a.title for a in meals} == {"午餐（自由安排）", "晚餐（自由安排）"}
    # no dinner on the departure day (check-in at 16:00)
    assert not [a for a in _meals(world, trip, date(2026, 12, 12)) if "晚餐" in a.title]
    for a in meals:
        h = world.local(a.start_at)
        assert (11, 30) <= (h.hour, h.minute) <= (12, 30) or (17, 30) <= (h.hour, h.minute) <= (18, 30)


def test_remove_offers_replacements_and_a_free_slot(setup):
    world, agent = setup
    turn = agent.handle("我不想去浅草寺了，我更喜欢有历史感的地方。")
    assert turn.state == "WAITING_FOR_APPROVAL"
    props = agent.store.pending()
    assert len(props) >= 2 and props[-1].label == "只删除，留作自由时间"
    assert all(not p.validation.hard_violations for p in props)
    assert "history" in agent.store.trip.preferences.interests
    for p in props:
        assert "senso_ji" not in {a.place_id for a in p.proposed_trip.activities if a.category != "free_time"}
    assert "senso_ji" in agent.avoided


def test_locked_booking_is_not_removed(setup):
    _, agent = setup
    turn = agent.handle("teamLab不想去了")
    assert turn.state == "INFEASIBLE" and not agent.store.pending()


def test_recommend_swaps_only_planb_suggestions_when_the_day_is_full(setup):
    world, agent = setup
    turn = agent.handle("推荐一个二次元的地方加到12号。")
    assert turn.state == "WAITING_FOR_APPROVAL"
    for p in agent.store.pending():
        assert not p.validation.hard_violations
        added = [a for a in p.proposed_trip.activities if a.notes == "PlanB 推荐"
                 and a.activity_id not in {x.activity_id for x in agent.store.trip.activities}]
        assert added and "anime" in world.place(added[0].place_id).tags
        # must-visits and bookings are never swapped out
        kept = {a.place_id for a in p.proposed_trip.activities}
        assert {"akihabara", "teamlab_planets"} <= kept
    # a recommendation focus is not stored as a lasting preference
    assert agent.store.trip.preferences.interests == ["quiet", "anime"]


def test_meal_with_catalogue_restaurant(setup):
    world, agent = setup
    turn = agent.handle("12号午饭我想去筑地吃。")
    p = agent.store.pending()[0]
    assert turn.state == "WAITING_FOR_APPROVAL" and not p.validation.hard_violations
    lunch = [a for a in p.proposed_trip.activities if a.place_id == "tsukiji_outer_market"]
    assert lunch and lunch[0].category == "meal"
    assert not _meals(world, p.proposed_trip, date(2026, 12, 12)) or \
        all("午餐" not in a.title for a in _meals(world, p.proposed_trip, date(2026, 12, 12)))


def test_restaurant_outside_catalogue_is_estimated_or_unknown(setup):
    world, agent = setup
    agent.handle("11号晚饭去浅草那家天妇罗店。")
    p = agent.store.pending()[0]
    dinner = next(a for a in p.proposed_trip.activities if a.category == "meal")
    place = world.place(dinner.place_id)
    assert place.verified_status == "user_provided" and "浅草" in place.name_zh
    assert world.travel_minutes(dinner.place_id, "teamlab_planets") is not None  # estimated from the area
    assert any(v.rule == "OPENING_HOURS" for v in p.validation.unknown_constraints)  # hours unknown, not assumed
    for x in agent.store.pending():
        agent.store.reject(x.proposal_id)
    agent.handle("10号晚饭去一兰拉面吃。")
    p = agent.store.pending()[0]
    dinner = next(a for a in p.proposed_trip.activities if a.category == "meal")
    assert world.travel_minutes(dinner.place_id, "senso_ji") is None  # no location -> unknown, never 0


def test_skip_meal_and_preferences(setup):
    world, agent = setup
    agent.handle("12号午饭不用安排了。")
    p = agent.store.pending()[0]
    assert not [a for a in _meals(world, p.proposed_trip, date(2026, 12, 12)) if "午餐" in a.title]
    turn = agent.handle("我喜欢热闹一点的地方")
    assert turn.state == "PREFERENCES_UPDATED" and "lively" in agent.store.trip.preferences.interests


def test_full_day_asks_with_options_instead_of_refusing():
    import json
    from pathlib import Path

    from planb.models import Booking, Trip

    world = load_world(extended=True)
    base = json.loads((Path(__file__).resolve().parents[1] / "evaluation/trip_scenarios/edit_base.json").read_text())
    agent = PlanBAgent(TripStore(Trip.model_validate(base["trip"]), [Booking.model_validate(b) for b in base["bookings"]],
                                 world), LLMClient(provider="mock"))
    for text in ("推荐一个二次元的地方加到12号。", "把高达加到12号"):
        turn = agent.handle(text)
        assert turn.state == "WAITING_FOR_APPROVAL" and "你想怎么做" in turn.message
        for p in agent.store.pending():
            assert not p.validation.hard_violations
            ids = {a.activity_id for a in p.proposed_trip.activities}
            assert {"e1", "e4", "e7", "e10"} <= ids  # bookings, flights and the must-visit stay
            agent.store.reject(p.proposal_id)
