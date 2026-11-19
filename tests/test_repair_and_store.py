import pytest

from conftest import jst
from planb.models import DisruptionEvent
from planb.repair import replan
from planb.store import ApprovalError, TripStore


def test_rain_repairs_only_affected(trip, world, bookings):
    ev = DisruptionEvent(event_type="weather_change", affected_start=jst("2026-12-10T13:00"),
                         affected_end=jst("2026-12-10T18:00"))
    res = replan(trip, ev, world, bookings)
    assert res.status == "ok" and res.affected_activity_ids == ["a2"]
    for p in res.proposals:
        changed = {c.activity_id for c in p.changes if c.change_type != "keep"}
        assert changed == {"a2"}
        assert not p.validation.hard_violations


def test_locked_activities_never_moved(trip, world, bookings):
    ev = DisruptionEvent(event_type="transport_delay", affected_start=jst("2026-12-11T08:30"),
                         affected_end=jst("2026-12-11T10:30"))
    res = replan(trip, ev, world, bookings)
    for p in res.proposals:
        a8 = p.proposed_trip.activity("a8")
        assert a8 is not None and a8.key() == trip.activity("a8").key()


def test_locked_closed_place_is_infeasible(trip, world, bookings):
    trip.activity("a2").is_locked = True
    ev = DisruptionEvent(event_type="place_closed", affected_place_ids=["senso_ji"],
                         affected_start=jst("2026-12-10T00:00"), affected_end=jst("2026-12-11T00:00"))
    res = replan(trip, ev, world, bookings)
    assert res.status == "infeasible"
    assert res.relaxation_options and not res.proposals


def test_reservation_conflict_with_locked_is_infeasible(trip, world, bookings):
    ev = DisruptionEvent(event_type="reservation_change",
                         parameters={"booking_id": "att-teamlab", "new_start": "2026-12-11T18:00:00+09:00"})
    res = replan(trip, ev, world, bookings)
    assert res.status == "infeasible"


def test_missing_info_requests_clarification(trip, world, bookings):
    res = replan(trip, DisruptionEvent(event_type="trip_extension"), world, bookings)
    assert res.status == "needs_information"


def test_approve_commits_and_bumps_revision(trip, world, bookings):
    store = TripStore(trip, bookings, world)
    res = replan(trip, DisruptionEvent(event_type="trip_extension", parameters={"new_end_date": "2026-12-13"}),
                 world, bookings)
    p = store.add_proposal(res.proposals[0])
    new = store.approve(p.proposal_id)
    assert new.revision == 2 and str(new.end_date) == "2026-12-13"
    assert store.find_booking("flight-ret").booking_status == "change_needed"  # not "changed"!
    with pytest.raises(ApprovalError):
        store.approve(p.proposal_id)  # no double commit


def test_stale_revision_rejected(trip, world, bookings):
    store = TripStore(trip, bookings, world)
    res = replan(trip, DisruptionEvent(event_type="trip_extension", parameters={"new_end_date": "2026-12-13"}),
                 world, bookings)
    p1, p2 = store.add_proposal(res.proposals[0]), store.add_proposal(res.proposals[1])
    store.approve(p1.proposal_id)
    with pytest.raises(ApprovalError):
        store.approve(p2.proposal_id)


def test_reject_keeps_trip(trip, world, bookings):
    store = TripStore(trip, bookings, world)
    res = replan(trip, DisruptionEvent(event_type="trip_extension", parameters={"new_end_date": "2026-12-13"}),
                 world, bookings)
    p = store.add_proposal(res.proposals[0])
    store.reject(p.proposal_id)
    assert store.trip.revision == 1 and str(store.trip.end_date) == "2026-12-12"


def test_initial_itinerary_generation_is_valid(world):
    from datetime import date
    from planb.models import Preferences
    from planb.planner import generate_itinerary
    from planb.validator import validate
    t = generate_itinerary(world, "Tokyo", date(2026, 12, 10), date(2026, 12, 12),
                           Preferences(interests=["photography", "nature"], pace="relaxed"),
                           arrival_at=jst("2026-12-10T11:30"), departure_at=jst("2026-12-12T18:00"))
    assert len([a for a in t.activities if a.category == "visit"]) >= 5
    assert not validate(t, world).hard_violations
