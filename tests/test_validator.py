from datetime import timedelta

from conftest import jst
from planb.events import build_context
from planb.models import DisruptionEvent
from planb.validator import validate


def rules(res):
    return {v.rule for v in res.hard_violations}


def test_base_trip_is_valid(trip, world):
    assert validate(trip, world, original=trip).feasibility_status == "valid"


def test_overlap_detected(trip, world):
    a3 = trip.activity("a3")
    a3.start_at = jst("2026-12-10T14:30")  # overlaps senso-ji 13:30-15:00
    assert "TIME_OVERLAP" in rules(validate(trip, world))


def test_travel_time_exactly_enough_passes(trip, world):
    # senso_ji -> skytree needs 20 min; a2 ends 15:00, a3 starts 15:20
    a3 = trip.activity("a3")
    a3.start_at, a3.end_at = jst("2026-12-10T15:20"), jst("2026-12-10T16:50")
    assert "TRAVEL_TIME" not in rules(validate(trip, world))
    a3.start_at = jst("2026-12-10T15:19")
    assert "TRAVEL_TIME" in rules(validate(trip, world))


def test_opening_hours_and_weekly_closure(trip, world):
    a2 = trip.activity("a2")
    a2.start_at, a2.end_at = jst("2026-12-10T16:00"), jst("2026-12-10T17:30")  # senso-ji closes 17:00
    assert "OPENING_HOURS" in rules(validate(trip, world))


def test_unknown_opening_hours_is_unknown_not_valid(trip, world):
    a11 = trip.activity("a11")
    a11.place_id = "yanaka_ginza"  # opening hours unknown in fixtures
    res = validate(trip, world)
    assert res.feasibility_status == "unknown"
    assert any(v.rule == "OPENING_HOURS" for v in res.unknown_constraints)


def test_missing_travel_matrix_entry_is_unknown(world):
    assert world.travel_minutes("yanaka_ginza", "ghibli_museum") is None
    assert world.travel_minutes("senso_ji", "senso_ji") == 0


def test_locked_activity_change_detected(trip, world):
    original = trip.model_copy(deep=True)
    a8 = trip.activity("a8")
    a8.start_at += timedelta(hours=1)
    a8.end_at += timedelta(hours=1)
    assert "LOCKED" in rules(validate(trip, world, original=original))


def test_weather_blocks_outdoor_only(trip, world, bookings):
    ev = DisruptionEvent(event_type="weather_change", affected_start=jst("2026-12-10T13:00"),
                         affected_end=jst("2026-12-10T18:00"))
    ctx = build_context(ev, trip, bookings)
    res = validate(trip, world, ctx)
    blocked = {aid for v in res.hard_violations if v.rule == "EVENT_BLOCKED" for aid in v.activity_ids}
    assert blocked == {"a2"}  # senso-ji is outdoor; skytree is indoor


def test_unknown_place_is_hard_violation(trip, world):
    trip.activity("a3").place_id = "imaginary_tower"
    assert "UNKNOWN_PLACE" in rules(validate(trip, world))


def test_hard_budget(trip, world):
    trip.budget.is_hard_limit = True
    trip.budget.amount_minor = 10000
    assert "BUDGET" in rules(validate(trip, world))  # known part alone already exceeds
    trip.budget.amount_minor = 10_000_000
    res = validate(trip, world)  # sushi dinner price is unknown -> cannot confirm
    assert "BUDGET" not in rules(res)
    assert any(v.rule == "BUDGET" for v in res.unknown_constraints)
