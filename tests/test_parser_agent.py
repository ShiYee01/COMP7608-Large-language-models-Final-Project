from planb.agent import PlanBAgent
from planb.llm import LLMClient, extract_json
from planb.parser import parse_rule_based
from planb.store import TripStore


def test_extract_json_handles_fences_and_think():
    assert extract_json('<think>x</think>```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json("Sure! {\"b\": 2} hope it helps") == {"b": 2}
    assert extract_json("no json") is None


def test_rule_parser_extension(trip, bookings, world):
    e = parse_rule_based("我想在东京多待一天，12月13日再回来", trip, bookings, world)
    assert e.event_type == "trip_extension" and e.parameters["new_end_date"] == "2026-12-13"


def test_rule_parser_weather_range(trip, bookings, world):
    e = parse_rule_based("12月11日上午8点到下午1点有暴雨", trip, bookings, world)
    assert e.event_type == "weather_change"
    assert (e.affected_start.hour, e.affected_end.hour) == (8, 13)


def test_agent_mock_end_to_end(trip, bookings, world):
    store = TripStore(trip, bookings, world)
    agent = PlanBAgent(store, LLMClient(provider="mock"))
    turn = agent.handle("我想在东京多待一天，12月13日再回来，之前安排好的景点尽量不要改。")
    assert turn.state == "WAITING_FOR_APPROVAL"
    assert "¥1,150" in turn.message
    assert store.trip.revision == 1  # nothing committed without approval
    assert [s.state for s in turn.steps][-1] == "WAITING_FOR_APPROVAL"


def test_agent_unknown_message(trip, bookings, world):
    agent = PlanBAgent(TripStore(trip, bookings, world), LLMClient(provider="mock"))
    assert agent.handle("你好").state == "NEEDS_INFORMATION"
