"""Fairness of the trip evaluation scorer: a correct answer in the BASELINE format must score as a success.

The correct answers are taken from PlanB on the gold request (setup) and from PlanB's proposals (edits) and
then pushed through the baseline parsing path (JSON -> activities), so both paths are judged identically.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluation"))

from planb.data import load_world  # noqa: E402
from planb.llm import LLMClient  # noqa: E402
from trip_eval import (SCEN, _items_to_acts, gold_request, run_edit, score_edit, score_setup,  # noqa: E402
                       understood_from_request)
from planb.planner import plan_trip  # noqa: E402

SETUPS = [json.loads(f.read_text()) for f in sorted(SCEN.glob("t*.json"))]
EDITS = [json.loads(f.read_text()) for f in sorted(SCEN.glob("e0*.json"))]


def _as_items(acts):
    return [{"activity_id": a.activity_id, "place_id": a.place_id, "title": a.title,
             "start_at": a.start_at.isoformat(), "end_at": a.end_at.isoformat(), "category": a.category}
            for a in acts]


@pytest.mark.parametrize("s", SETUPS, ids=[s["id"] for s in SETUPS])
def test_correct_setup_answer_in_baseline_format_scores_as_success(s):
    world = load_world(extended=True)
    req = gold_request(s)
    if req.missing_required():
        out = {"method": "direct", "status": "needs_information", "understood": understood_from_request(req),
               "acts": [], "llm_calls": 1, "tokens": 0, "latency_s": 0.0, "world": world}
    else:
        plan = plan_trip(world, req)
        data = {"status": "ok", "understood": understood_from_request(req), "itinerary": _as_items(plan.trip.activities),
                "unplaceable": [{"place_id": p, "reason": "closed"} for p in plan.unplaceable]}
        acts, malformed, invented = _items_to_acts(data["itinerary"], world)
        out = {"method": "direct", "status": "ok", "understood": data["understood"], "acts": acts,
               "invented": invented, "unplaceable": [u["place_id"] for u in data["unplaceable"]],
               "llm_calls": 1, "tokens": 0, "latency_s": 0.0, "world": world}
    row = score_setup(s, out)
    assert row["success"] and row["extraction_acc"] == 1.0, row


@pytest.mark.parametrize("e", EDITS, ids=[e["id"] for e in EDITS])
def test_correct_edit_answer_in_baseline_format_scores_as_success(e):
    planb = run_edit(e, "planb", LLMClient(provider="mock"))
    assert score_edit(e, planb)["success"]
    world = load_world(extended=True)
    options = []
    for acts in planb["options"]:
        items = _as_items(acts)
        for it in items:  # restaurants outside the catalogue are 'custom' in the baseline format
            if it["place_id"].startswith("user_"):
                it["custom_name"], it["place_id"] = it["title"], "custom"
        options.append(_items_to_acts(items, world, keep_ids=True)[0])
    status = {"ok": "ok", "refuse": "refuse"}[planb["status"]]
    out = {"method": "direct", "status": status, "options": options, "invented": [], "message": planb["message"],
           "unverified_flag": planb["unverified_flag"], "llm_calls": 1, "tokens": 0, "latency_s": 0.0,
           "world": world, "base": planb["base"]}
    assert score_edit(e, out)["success"]


def test_bare_refusal_on_full_day_is_wrong():
    e = next(x for x in EDITS if x["id"] == "e02_recommend_on_full_day")
    out = {"method": "direct", "status": "refuse", "options": [], "invented": [], "message": "放不下",
           "unverified_flag": False, "llm_calls": 1, "tokens": 0, "latency_s": 0.0,
           "world": load_world(extended=True), "base": run_edit(e, "planb", LLMClient(provider="mock"))["base"]}
    assert not score_edit(e, out)["success"]


def test_free_time_used_as_travel_is_not_penalised():
    s = next(x for x in SETUPS if x["id"] == "t05_bookings_with_prices")
    world = load_world(extended=True)
    plan = plan_trip(world, gold_request(s))
    items = [it for it in _as_items(plan.trip.activities) if it["category"] != "free_time"]
    # a baseline that writes its travel as free_time "Travel to ..." entries, filling every gap exactly
    acts = sorted(items, key=lambda it: it["start_at"])
    travel = [{"place_id": "free_time", "title": "Travel", "start_at": a["end_at"], "end_at": b["start_at"],
               "category": "free_time"} for a, b in zip(acts, acts[1:]) if a["end_at"] < b["start_at"]]
    parsed, _, invented = _items_to_acts(acts + travel, world)
    out = {"method": "direct", "status": "ok", "understood": understood_from_request(gold_request(s)), "acts": parsed,
           "invented": invented, "unplaceable": [], "llm_calls": 1, "tokens": 0, "latency_s": 0.0, "world": world}
    row = score_setup(s, out)
    assert row["c_feasible"] and row["c_no_invented"] and row["success"], row


@pytest.mark.parametrize("e", EDITS, ids=[e["id"] for e in EDITS])
def test_edit_engine_on_gold_edit_request_meets_every_check(e):
    # planb_gold for edits: with a correct reading of the request, PlanB's edit engine must pass every check
    row = score_edit(e, run_edit(e, "planb_gold", None))
    assert row["success"], row
