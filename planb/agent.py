"""PlanB agent orchestrator (PROJECT_CONTEXT.md §7).

Design choice: a *constrained* single-agent workflow. The LLM is used where language
understanding is needed (parse the request into a structured event, explain the
result); the orchestrator then calls the deterministic tools in a fixed order. This is
deliberately more robust than a free-form tool loop when running small free/open
models, and the backend — not the model — owns the execution state.
The agent has NO commit tool: committing requires an explicit user approval.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from .llm import LLMClient, LLMUsage
from .models import DisruptionEvent, PlanProposal, ReplanResult
from .parser import parse_request
from .repair import replan
from .store import TripStore

EXPLAIN_PROMPT = """You are PlanB, a travel copilot. Explain the proposed itinerary change to the traveller in
Chinese, in at most 6 short bullet points. Use ONLY the facts in the JSON below. Copy every money amount
exactly as given; never invent prices, opening hours or availability. If the cost is incomplete, say which
items are unknown. Remind the user that approving only updates the PlanB itinerary — flight/hotel changes
must still be done with the providers."""


@dataclass
class AgentStep:
    state: str
    detail: str = ""
    tool: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class AgentTurn:
    user_text: str
    state: str = "IDLE"
    steps: list[AgentStep] = field(default_factory=list)
    event: Optional[DisruptionEvent] = None
    parse_method: str = ""
    result: Optional[ReplanResult] = None
    message: str = ""
    usage: LLMUsage = field(default_factory=LLMUsage)


def _yuan(minor: Optional[int]) -> str:
    return "未知" if minor is None else f"¥{minor / 100:,.0f}"


def proposal_facts(p: PlanProposal) -> dict:
    return {
        "label": p.label,
        "event": p.event.description if p.event else "",
        "changes": [{"type": c.change_type, "before": c.before, "after": c.after, "reason": c.reason}
                    for c in p.changes if c.change_type != "keep"],
        "kept_activities": sum(1 for c in p.changes if c.change_type == "keep"),
        "feasibility": p.validation.feasibility_status,
        "unknown_constraints": [v.message for v in p.validation.unknown_constraints],
        "booking_impacts": [{"booking": i.booking_id, "status": i.status, "action": i.required_action,
                             "reason": i.reason} for i in p.booking_impacts if i.status != "unaffected"],
        "cost": {
            "total_additional": _yuan(p.cost_estimate.total_additional_minor),
            "known_subtotal": _yuan(p.cost_estimate.known_additional_minor),
            "components": [{"item": c.kind, "amount": _yuan(c.amount_minor), "basis": c.basis,
                            "cash": c.cash} for c in p.cost_estimate.components],
            "unknown_items": [c.kind for c in p.cost_estimate.unknown_components],
        },
    }


def template_explanation(p: PlanProposal) -> str:
    f = proposal_facts(p)
    lines = []
    for c in f["changes"]:
        b, a = c["before"] or {}, c["after"] or {}
        if c["type"] == "remove":
            lines.append(f"- 删除「{b.get('title')}」（{b.get('start')}）")
        elif c["type"] == "add":
            lines.append(f"- 新增「{a.get('title')}」（{a.get('start')}-{a.get('end')}）")
        elif c["type"] == "replace":
            lines.append(f"- 「{b.get('title')}」替换为「{a.get('title')}」（{a.get('start')}-{a.get('end')}）")
        else:
            lines.append(f"- 「{b.get('title')}」从 {b.get('start')} 调整到 {a.get('start')}")
    lines.append(f"- 其余 {f['kept_activities']} 项安排保持不变")
    for i in f["booking_impacts"]:
        lines.append(f"- 订单 {i['booking']}：{i['reason']}")
    cost = f["cost"]
    if cost["unknown_items"]:
        lines.append(f"- 已知新增费用小计 {cost['known_subtotal']}；以下费用未知：{', '.join(cost['unknown_items'])}")
    else:
        lines.append(f"- 预计新增支出 {cost['total_additional']}")
    lines.append("- 批准后只更新 PlanB 内的行程；机票/酒店变更仍需你在供应商处办理")
    return "\n".join(lines)


def _amounts(text: str) -> set[str]:
    return {m.replace(",", "") for m in re.findall(r"¥\s?-?[\d,]+", text)}


class PlanBAgent:
    def __init__(self, store: TripStore, llm: LLMClient):
        self.store = store
        self.llm = llm

    def explain(self, p: PlanProposal, usage: LLMUsage | None = None) -> str:
        if self.llm.is_mock:
            return template_explanation(p)
        facts = proposal_facts(p)
        r = self.llm.chat([{"role": "system", "content": EXPLAIN_PROMPT},
                           {"role": "user", "content": json.dumps(facts, ensure_ascii=False)}], max_tokens=500)
        if usage:
            usage.add(r)
        text = re.sub(r"<think>.*?</think>", "", r.text, flags=re.S).strip()
        # Guard: every money amount in the explanation must come from the computed facts.
        allowed = _amounts(json.dumps(facts, ensure_ascii=False).replace(" ", ""))
        if not text or not _amounts(text.replace(" ", "")) <= allowed:
            return template_explanation(p)
        return text

    def handle(self, text: str, event: DisruptionEvent | None = None, explain: bool = True) -> AgentTurn:
        turn = AgentTurn(user_text=text)
        trip, bookings, world = self.store.trip, self.store.bookings, self.store.world

        def step(state, detail="", tool=None, t0=None):
            turn.state = state
            turn.steps.append(AgentStep(state, detail, tool, (time.perf_counter() - t0) * 1000 if t0 else 0))

        t0 = time.perf_counter()
        if event is None:
            event, method = parse_request(text, trip, bookings, world, self.llm, turn.usage)
            turn.parse_method = method
        else:
            turn.parse_method = "given"
        step("UNDERSTANDING_REQUEST", f"解析方式: {turn.parse_method}", "parse_request", t0)
        turn.event = event
        if event is None:
            step("NEEDS_INFORMATION")
            turn.message = ("我没能把这条消息理解为行程变化。可以试试：『12月11日上午有暴雨』、"
                            "『我想多待一天，12月13日回』、『东京国立博物馆12月12日闭馆』。")
            return turn

        step("LOADING_CONTEXT", f"trip revision {trip.revision}, {len(trip.activities)} 项活动, {len(bookings)} 个订单",
             "get_trip_state")
        t0 = time.perf_counter()
        result = replan(trip, event, world, bookings)
        step("ANALYZING_IMPACT", f"受影响活动: {result.affected_activity_ids}", "analyze_disruption", t0)
        turn.result = result

        if result.status == "needs_information":
            step("NEEDS_INFORMATION", "; ".join(result.missing_information))
            turn.message = "还需要以下信息才能重新规划：" + "、".join(result.missing_information)
            return turn
        if result.status == "infeasible":
            step("INFEASIBLE", "; ".join(result.infeasible_reasons))
            turn.message = ("在满足全部硬约束的前提下无法完成该调整：\n" +
                            "\n".join(f"- {r}" for r in result.infeasible_reasons) +
                            "\n可以考虑：\n" + "\n".join(f"- {o}" for o in result.relaxation_options))
            return turn

        step("GENERATING_CANDIDATES", f"{len(result.proposals)} 个可行候选", "repair_itinerary")
        step("VALIDATING", "所有候选已通过硬约束验证", "validate_itinerary")
        step("EVALUATING_COST", "已计算订单影响与增量费用", "estimate_cost")
        for i, p in enumerate(result.proposals):
            p.explanation = self.explain(p, turn.usage) if (explain and i == 0) else template_explanation(p)
            self.store.add_proposal(p)
        step("WAITING_FOR_APPROVAL", "等待用户批准或拒绝")
        turn.message = result.proposals[0].explanation
        return turn
