"""Trip state store with Preview -> Approve -> Commit (PROJECT_CONTEXT.md §11).

The LLM never gets access to this module's commit path; only an explicit user
approval (UI button / API call) can commit a proposal.
"""
from __future__ import annotations

from typing import Optional

from .data import World
from .events import build_context
from .models import Booking, ChangeRecord, PlanProposal, Trip
from .validator import validate


class ApprovalError(Exception):
    pass


class TripStore:
    def __init__(self, trip: Trip, bookings: list[Booking], world: World):
        self.trip = trip
        self.bookings = bookings
        self.world = world
        self.proposals: dict[str, PlanProposal] = {}
        self.history: list[ChangeRecord] = []

    def add_proposal(self, proposal: PlanProposal) -> PlanProposal:
        self.proposals[proposal.proposal_id] = proposal
        return proposal

    def pending(self) -> list[PlanProposal]:
        return [p for p in self.proposals.values() if p.status == "pending"]

    def approve(self, proposal_id: str) -> Trip:
        p = self.proposals.get(proposal_id)
        if p is None:
            raise ApprovalError("方案不存在")
        if p.status != "pending":
            raise ApprovalError(f"方案状态为 {p.status}，不能重复批准")
        if p.base_revision != self.trip.revision:
            p.status = "expired"
            raise ApprovalError("行程在生成方案后已被修改（revision 不一致），方案已失效，请重新生成")
        # Re-validate on the backend before committing.
        ctx = build_context(p.event, self.trip, self.bookings)
        res = validate(p.proposed_trip, self.world, ctx, self.trip)
        if res.hard_violations:
            raise ApprovalError("提交前复核未通过：" + "; ".join(v.message for v in res.hard_violations))
        new_trip = p.proposed_trip.model_copy(deep=True)
        new_trip.revision = self.trip.revision + 1
        actions = [f"{i.booking_id}: {i.required_action}（需你在供应商处自行办理）"
                   for i in p.booking_impacts if i.status == "change_required"]
        for b in self.bookings:
            if any(i.booking_id == b.booking_id and i.status == "change_required" for i in p.booking_impacts):
                b.booking_status = "change_needed"  # NOT changed externally — user must handle it
        self.history.append(ChangeRecord(revision_before=self.trip.revision, revision_after=new_trip.revision,
                                         proposal_id=p.proposal_id,
                                         reason=p.event.description if p.event else p.label,
                                         changes=[c for c in p.changes if c.change_type != "keep"],
                                         booking_actions=actions))
        self.trip = new_trip
        p.status = "approved"
        for other in self.pending():
            other.status = "expired"
        return self.trip

    def reject(self, proposal_id: str) -> None:
        p = self.proposals.get(proposal_id)
        if p is None or p.status != "pending":
            raise ApprovalError("只能拒绝待处理的方案")
        p.status = "rejected"

    def find_booking(self, booking_id: str) -> Optional[Booking]:
        return next((b for b in self.bookings if b.booking_id == booking_id), None)
