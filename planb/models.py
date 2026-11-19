"""Core data models for PlanB.

Conventions (see PROJECT_CONTEXT.md §6):
- Money is stored as integer minor units (CNY fen). ``None`` means UNKNOWN and is
  never the same as 0.
- Datetimes are timezone-aware (trip timezone, e.g. Asia/Tokyo).
- Every fact carries a ``source`` (fixture / user_provided / simulated).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# World data
# ---------------------------------------------------------------------------

class Place(BaseModel):
    place_id: str
    name: str
    name_zh: str = ""
    category: str  # temple / park / museum / viewpoint / shopping / food / airport / hotel ...
    indoor: bool
    latitude: float
    longitude: float
    area: str = ""
    # weekday ("mon".."sun") -> list of ["HH:MM", "HH:MM"] windows.
    # None = opening hours UNKNOWN. A weekday missing from the dict = closed that day.
    opening_hours: Optional[dict[str, list[tuple[str, str]]]] = None
    closed_dates: list[date] = Field(default_factory=list)
    suggested_visit_minutes: int = 90
    entry_cost_minor: Optional[int] = None
    tags: list[str] = Field(default_factory=list)
    reservation_required: bool = False
    data_source: str = "fixture"
    verified_status: Literal["simulated", "user_provided", "verified"] = "simulated"


class TravelTime(BaseModel):
    origin_place_id: str
    destination_place_id: str
    mode: str = "transit"
    travel_minutes: int
    travel_cost_minor: Optional[int] = None
    source: str = "fixture"


# ---------------------------------------------------------------------------
# Trip state
# ---------------------------------------------------------------------------

class Budget(BaseModel):
    amount_minor: Optional[int] = None
    currency: str = "CNY"
    is_hard_limit: bool = False


class Preferences(BaseModel):
    interests: list[str] = Field(default_factory=list)
    pace: Literal["relaxed", "normal", "packed"] = "normal"
    day_start: str = "08:00"
    day_end: str = "22:00"


ActivityCategory = Literal["visit", "meal", "flight_arrival", "flight_departure", "free_time"]


class Activity(BaseModel):
    activity_id: str
    place_id: str
    title: str
    start_at: datetime
    end_at: datetime
    category: ActivityCategory = "visit"
    priority: int = 2  # 1=low 2=normal 3=high (NOT the same as locked)
    is_locked: bool = False
    status: Literal["planned", "cancelled"] = "planned"
    estimated_cost_minor: Optional[int] = None
    notes: str = ""

    def key(self) -> tuple:
        """Identity used to decide whether an activity was changed."""
        return (self.place_id, self.start_at, self.end_at)


class Trip(BaseModel):
    trip_id: str
    title: str = ""
    destination: str
    start_date: date  # first day of the trip (inclusive)
    end_date: date  # last day of the trip (inclusive, departure day)
    timezone: str = "Asia/Tokyo"
    party_size: int = 1
    budget: Budget = Field(default_factory=Budget)
    preferences: Preferences = Field(default_factory=Preferences)
    hotel_place_id: Optional[str] = None
    activities: list[Activity] = Field(default_factory=list)
    status: Literal["draft", "active", "completed"] = "active"
    revision: int = 1

    def activity(self, activity_id: str) -> Optional[Activity]:
        return next((a for a in self.activities if a.activity_id == activity_id), None)

    def sorted_activities(self) -> list[Activity]:
        return sorted(self.activities, key=lambda a: a.start_at)


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

class BookingPolicy(BaseModel):
    change_allowed: Optional[bool] = None
    cancel_allowed: Optional[bool] = None
    change_fee_minor: Optional[int] = None
    # Amount returned to the traveller if THEY cancel (after fees). None = unknown.
    refund_on_cancel_minor: Optional[int] = None
    # Amount returned if the PROVIDER cancels / closes. None = unknown.
    provider_cancellation_refund_minor: Optional[int] = None
    # Hotel: amount returned for an early check-out. None = unknown.
    early_checkout_refund_minor: Optional[int] = None
    # Flights: is a negative fare difference refunded? None = unknown.
    negative_fare_difference_refunded: Optional[bool] = None
    free_cancel_deadline: Optional[datetime] = None
    conditions: str = ""
    source: str = "user_provided"


QuoteAction = Literal["change_date", "extend_stay", "new_booking"]


class AlternativeQuote(BaseModel):
    quote_id: str
    action: QuoteAction
    target_start: Optional[datetime] = None
    target_end: Optional[datetime] = None
    # change_date: fare/price DIFFERENCE; extend_stay: price of the extra night(s);
    # new_booking: full price. None = unknown.
    amount_minor: Optional[int] = None
    available: Optional[bool] = None
    notes: str = ""
    simulated: bool = True


class Booking(BaseModel):
    booking_id: str
    booking_type: Literal["flight", "hotel", "attraction", "restaurant", "transport"]
    title: str
    provider_name: str = ""
    place_id: Optional[str] = None
    service_start: Optional[datetime] = None
    service_end: Optional[datetime] = None
    paid_minor: Optional[int] = None
    currency: str = "CNY"
    booking_status: Literal["recorded", "externally_confirmed", "change_needed", "user_marked_handled"] = (
        "externally_confirmed"
    )
    linked_activity_ids: list[str] = Field(default_factory=list)
    policy: BookingPolicy = Field(default_factory=BookingPolicy)
    quotes: list[AlternativeQuote] = Field(default_factory=list)
    source: str = "user_provided"


# ---------------------------------------------------------------------------
# Events, validation, cost, proposals
# ---------------------------------------------------------------------------

EventType = Literal[
    "weather_change",
    "place_closed",
    "transport_delay",
    "trip_extension",
    "trip_shortening",
    "reservation_change",
]


class DisruptionEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    event_type: EventType
    description: str = ""
    affected_start: Optional[datetime] = None
    affected_end: Optional[datetime] = None
    affected_place_ids: list[str] = Field(default_factory=list)
    # trip_extension / trip_shortening: new_end_date (YYYY-MM-DD)
    # reservation_change: booking_id, new_start, new_end
    parameters: dict[str, Any] = Field(default_factory=dict)
    source: str = "user"


class Violation(BaseModel):
    rule: str
    activity_ids: list[str] = Field(default_factory=list)
    place_id: Optional[str] = None
    message: str


class ValidationResult(BaseModel):
    feasibility_status: Literal["valid", "invalid", "unknown"]
    hard_violations: list[Violation] = Field(default_factory=list)
    soft_warnings: list[Violation] = Field(default_factory=list)
    unknown_constraints: list[Violation] = Field(default_factory=list)
    checked_rules: list[str] = Field(default_factory=list)

    @property
    def is_feasible(self) -> bool:
        """True only means: no KNOWN hard constraint is violated."""
        return not self.hard_violations


ImpactStatus = Literal["unaffected", "change_required", "potentially_affected", "unknown"]


class BookingImpact(BaseModel):
    booking_id: str
    status: ImpactStatus
    required_action: Optional[Literal["change_date", "extend_stay", "shorten_stay", "cancel"]] = None
    reason: str = ""
    target_start: Optional[datetime] = None
    target_end: Optional[datetime] = None
    provider_initiated: bool = False


class CostComponent(BaseModel):
    kind: str
    booking_id: Optional[str] = None
    amount_minor: Optional[int]  # None = unknown
    basis: str = ""  # human readable trace to the rule / quote used
    cash: bool = True  # False = economic loss only (e.g. forfeited non-refundable amount)


class CostEstimate(BaseModel):
    currency: str = "CNY"
    known_additional_minor: int = 0  # sum of KNOWN cash components
    total_additional_minor: Optional[int] = None  # None if any cash component is unknown
    forfeited_minor: int = 0  # known economic loss that is not a cash payment
    is_complete: bool = True
    components: list[CostComponent] = Field(default_factory=list)
    unknown_components: list[CostComponent] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class ActivityChange(BaseModel):
    change_type: Literal["keep", "shift", "replace", "remove", "add", "extend"]
    activity_id: str
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    reason: str = ""


class PlanProposal(BaseModel):
    proposal_id: str = Field(default_factory=lambda: new_id("prop"))
    trip_id: str
    base_revision: int
    label: str = ""
    event: Optional[DisruptionEvent] = None
    proposed_trip: Trip
    changes: list[ActivityChange] = Field(default_factory=list)
    validation: ValidationResult
    booking_impacts: list[BookingImpact] = Field(default_factory=list)
    cost_estimate: CostEstimate = Field(default_factory=CostEstimate)
    score: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())


class ReplanResult(BaseModel):
    """Outcome of one replanning request."""

    status: Literal["ok", "infeasible", "needs_information"]
    event: Optional[DisruptionEvent] = None
    affected_activity_ids: list[str] = Field(default_factory=list)
    proposals: list[PlanProposal] = Field(default_factory=list)
    infeasible_reasons: list[str] = Field(default_factory=list)
    relaxation_options: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class ChangeRecord(BaseModel):
    revision_before: int
    revision_after: int
    proposal_id: Optional[str] = None
    reason: str = ""
    changes: list[ActivityChange] = Field(default_factory=list)
    booking_actions: list[str] = Field(default_factory=list)
    committed_at: datetime = Field(default_factory=lambda: datetime.now().astimezone())
