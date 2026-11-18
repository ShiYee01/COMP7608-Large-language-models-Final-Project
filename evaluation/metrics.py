"""Metrics (PROJECT_CONTEXT.md §14.4). The same deterministic validator judges every method."""
from __future__ import annotations

from common import MethodOutput, Scenario

from planb.events import build_context
from planb.validator import validate

COST_TOLERANCE_MINOR = 100  # ¥1


def _kept(trip, original, aid, world) -> bool:
    o = original.activity(aid)
    if o is None or trip is None:
        return False
    for a in trip.activities:
        if a.status == "planned" and a.place_id == o.place_id and a.start_at == o.start_at and a.end_at == o.end_at:
            return True
    return False


def score_case(s: Scenario, out: MethodOutput) -> dict:
    gt = s.gt
    expected = gt["expected_status"]
    row = {
        "scenario": s.id, "category": s.raw["category"], "method": out.method, "expected_status": expected,
        "pred_status": out.status, "json_ok": out.json_ok, "format_errors": out.format_errors,
        "latency_s": round(out.latency_s, 3), "llm_calls": out.llm_calls,
        "tokens": out.prompt_tokens + out.completion_tokens, "parse_method": out.parse_method,
    }
    # parsed event correctness (PlanB only)
    if out.parsed_event is not None or out.method == "planb":
        pe = out.parsed_event or {}
        row["event_type_correct"] = pe.get("event_type") == s.gold_event.event_type

    if expected == "infeasible":
        row["status_correct"] = out.status in ("infeasible", "needs_information")
        row["success"] = row["status_correct"]
        return row

    row["status_correct"] = out.status == "ok"
    if not out.json_ok or out.trip is None or out.status != "ok":
        row.update(feasible=False, hard_violations=None, preservation=0.0, booking_f1=0.0,
                   cost_correct=False, success=False)
        if gt["cost_unknown"]:
            row["cost_hallucinated"] = out.cost_minor is not None
        return row

    ctx = build_context(s.gold_event, s.trip, s.bookings)
    res = validate(out.trip, s.world, ctx, s.trip)
    row["hard_violations"] = len(res.hard_violations)
    row["violation_rules"] = ";".join(sorted({v.rule for v in res.hard_violations}))
    row["unknown_constraints"] = len(res.unknown_constraints)
    row["feasible"] = not res.hard_violations

    keep = gt["must_keep"]
    row["preservation"] = round(sum(_kept(out.trip, s.trip, a, s.world) for a in keep) / len(keep), 3) if keep else 1.0

    pred, gold = set(out.affected_booking_ids), set(gt["affected_booking_ids"])
    if not pred and not gold:
        p = r = f1 = 1.0
    else:
        tp = len(pred & gold)
        p = tp / len(pred) if pred else 0.0
        r = tp / len(gold) if gold else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
    row.update(booking_precision=round(p, 3), booking_recall=round(r, 3), booking_f1=round(f1, 3))

    row["pred_cost_cny"] = None if out.cost_minor is None else out.cost_minor / 100
    if gt["cost_unknown"]:
        row["cost_correct"] = out.cost_minor is None
        row["cost_hallucinated"] = out.cost_minor is not None
    else:
        exp = gt["expected_cost_minor"]
        row["cost_correct"] = out.cost_minor is not None and abs(out.cost_minor - exp) <= COST_TOLERANCE_MINOR
        row["cost_abs_error_cny"] = None if out.cost_minor is None else abs(out.cost_minor - exp) / 100

    row["success"] = bool(row["feasible"] and row["preservation"] == 1.0 and f1 == 1.0 and row["cost_correct"])
    return row
