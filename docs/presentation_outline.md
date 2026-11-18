# Proposal presentation outline (Thu 2026-11-26)

About 10 slides / 8–10 minutes. Adjust to the teacher's time limit. Only put real numbers from
`evaluation/results/<run>/summary.md` on the results slide.

## 1. Title
**PlanB: An AI Travel Copilot with Constraint-Aware Itinerary Replanning and Booking Cost Impact Analysis**
Individual project · COMP7608

## 2. Problem — why a plain LLM is not enough
- Travel plans change: rain, closures, delays, extending or shortening the trip.
- A plain LLM, asked to "fix my itinerary", often:
  1. rewrites the whole plan (loses bookings and things the user cared about);
  2. breaks hard constraints (overlaps, too little travel time, closed venues, locked items);
  3. misses linked bookings (return flight, hotel nights) and **guesses fees** or counts paid money twice.
- Show one real baseline failure from `raw_outputs.jsonl` (e.g. wrong cost in s01 or an invented number in s02).

## 3. Research question
Can structured trip state + deterministic constraint validation + local repair + a booking dependency/cost
engine handle travel changes more reliably than letting the LLM edit the itinerary directly?

## 4. Proposed method — architecture
Diagram from README: LLM parses → event → impact analysis → local repair (beam search) → validator →
booking impact → cost engine → ranked proposals → LLM explanation (amount-guarded) → user approval.
Key message: **the LLM understands and explains; Python checks and calculates; the user decides.**

## 5. Key design points
- Unknown ≠ 0: missing fees make the total unknown (Story F).
- Locks respected; conflicts → "infeasible" plus options for the user to relax (Story E).
- Preview → Approve → Commit with revision check; approval never changes real bookings.
- Works with free/open models: one structured LLM call for parsing, the rest is deterministic.

## 6. Live demo (≈3 min) — `streamlit run app/streamlit_app.py`
1. Story D: "多待一天，12月13日回来" → only the return flight moves; flight + hotel flagged;
   cost ¥200 + ¥350 + ¥600 = **¥1,150**; approve → revision 2, reminder to rebook externally.
2. Rain on 12/11 morning → only the two outdoor activities change; teamLab and the locked dinner stay.
3. Reservation conflict → infeasible + "unlock the sushi dinner" option.
Backup: record a screen video beforehand in case the network or the laptop fails.

## 7. Evaluation setup
- 10 pilot scenarios (6 event types; normal, unknown-cost and infeasible cases), hand-written ground truth.
- Methods: Direct LLM (A), Constraint-prompted LLM (B), PlanB, PlanB with gold event.
- Same model / temperature / facts / output schema. One validator judges everything.
- Metrics: task success, feasibility, preservation, booking F1, cost exact match, unknown-cost handling,
  infeasible detection, latency, tokens.

## 8. Preliminary results
Table + `summary.png` from the real run. Comment on where the baselines fail (constraint violations, cost
errors, invented costs when data is missing, never saying "infeasible") and on PlanB's cost (latency, calls).
Mention the `planb` vs `planb_gold` gap = request-parsing errors.

## 9. Limitations and plan to the final
- Pilot set is small and written by the author → expand to ~40 scenarios with a held-out split.
- Simulated data, one city, synthetic travel times.
- Next: more scenarios, ablations (without local repair / without validator / LLM-only cost), a larger free model
  vs a small one, booking-text extraction, React front end if time allows.

## 10. Summary
Reliability comes from splitting responsibilities: language → LLM, constraints & money → code, decision → user.

---
### Q&A preparation
- *Why not let the LLM call tools freely?* Small free models are unreliable at multi-step tool use; a
  constrained orchestrator keeps the LLM where it adds value and keeps state on the backend (docs/decisions.md D3).
- *Isn't the evaluation biased toward your own engine?* Ground truth is hand-written from the booking rules,
  the validator is shared, baselines get the same facts plus a rule-heavy prompt (B). The pilot set is a
  development set; the final numbers will come from a held-out set.
- *Is the cost "real"?* It is exact with respect to the user-provided rules and quotes; PlanB never fetches
  live prices and says so.
