from planb.models import DisruptionEvent
from planb.repair import replan


def _top(trip, world, bookings, **kw):
    res = replan(trip, DisruptionEvent(**kw), world, bookings)
    assert res.status == "ok", res
    return res.proposals[0]


def test_story_d_extension_costs_exactly_1150(trip, world, bookings):
    p = _top(trip, world, bookings, event_type="trip_extension", parameters={"new_end_date": "2026-12-13"})
    ce = p.cost_estimate
    assert ce.is_complete
    assert ce.total_additional_minor == 115000  # 200 + 350 + 600, the paid 1800 is NOT counted again
    kinds = {c.kind: c.amount_minor for c in ce.components}
    assert kinds == {"flight_change_fee": 20000, "flight_fare_difference": 35000, "hotel_extension": 60000}
    affected = {i.booking_id for i in p.booking_impacts if i.status == "change_required"}
    assert affected == {"flight-ret", "hotel-1"}
    # all original non-flight activities are preserved
    kept = {c.activity_id for c in p.changes if c.change_type == "keep"}
    assert {f"a{i}" for i in range(1, 12)} <= kept


def test_story_f_missing_quote_is_unknown_not_zero(trip, world, bookings):
    ret = next(b for b in bookings if b.booking_id == "flight-ret")
    ret.quotes = []
    ret.policy.change_fee_minor = None
    p = _top(trip, world, bookings, event_type="trip_extension", parameters={"new_end_date": "2026-12-13"})
    ce = p.cost_estimate
    assert not ce.is_complete
    assert ce.total_additional_minor is None
    assert ce.known_additional_minor == 60000  # hotel only
    assert {c.kind for c in ce.unknown_components} == {"flight_change_fee", "flight_fare_difference"}


def test_provider_closure_refund(trip, world, bookings):
    from conftest import jst
    p = _top(trip, world, bookings, event_type="place_closed", affected_place_ids=["teamlab_planets"],
             affected_start=jst("2026-12-11T00:00"), affected_end=jst("2026-12-12T00:00"))
    assert p.cost_estimate.total_additional_minor == -18000


def test_shortening_cost_and_forfeit(trip, world, bookings):
    p = _top(trip, world, bookings, event_type="trip_shortening", parameters={"new_end_date": "2026-12-11"})
    ce = p.cost_estimate
    assert ce.total_additional_minor == 30000
    assert ce.forfeited_minor == 60000  # one unused, non-refundable hotel night (economic loss, not cash)
    assert all(a.start_at.date().isoformat() <= "2026-12-11" or a.category == "flight_departure"
               for a in p.proposed_trip.activities)


def test_negative_fare_difference_not_assumed_refunded(trip, world, bookings):
    ret = next(b for b in bookings if b.booking_id == "flight-ret")
    ret.quotes[0].amount_minor = -5000
    ret.policy.negative_fare_difference_refunded = None
    p = _top(trip, world, bookings, event_type="trip_extension", parameters={"new_end_date": "2026-12-13"})
    assert p.cost_estimate.total_additional_minor is None
