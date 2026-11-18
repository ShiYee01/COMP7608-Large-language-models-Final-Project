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
- Show one real baseline failure from `evaluation/results/qwen2.5-3b-local-cpu/raw_outputs.jsonl`: in s03 the 3B model moved the locked sushi dinner and never computed any cost (see slide 8).

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

## 8. Preliminary results (real run: `evaluation/results/qwen2.5-3b-local-cpu/`)
Model: Qwen2.5-3B-Instruct Q4, local CPU, temperature 0. 10 pilot scenarios × 4 methods.

| method | task success | booking F1 | cost exact (known) | infeasible detected | latency | tokens |
|---|---|---|---|---|---|---|
| Direct LLM | 2/10 | 0.25 | 0/7 | 1/2 | 462 s | 10.1k |
| Constraint-prompted LLM | 1/10 | 0.25 | 0/7 | 0/2 | 480 s | 10.5k |
| **PlanB** | **8/10** | **0.875** | **6/7** | **2/2** | 45 s | 2.2k |
| PlanB + gold event | 10/10 | 1.00 | 7/7 | 2/2 | <0.1 s | 0 |

Put `summary.png` next to the table. Talking points:
- **The baselines solved none of the 8 solvable cases** (0/8). Their only successes were refusals in the
  infeasible cases.
- **The baselines never produced a cost** (always `null`), even though the fees and quotes were in the prompt.
- **The baselines broke constraints.**
  - Rain (s03): moved the locked 18:30 sushi dinner to 14:30, with 9 hard violations.
  - Shortened trip (s09): kept the whole of day 3.
  - Museum closed (s05): invented place ids.
- **Both PlanB failures are parsing errors by the 3B model.**
  - s03: "下午1点" (1 pm) was read as 12:00.
  - s07: the time the delay ends was left out, so PlanB asked for more information instead of guessing.
  - `planb_gold` = 10/10, so the engine itself made no error. The fix is a better parser or a larger model.
- **PlanB is cheaper to run.** One LLM call of about 2k tokens vs about 10k tokens, and it is about 10× faster
  on CPU.
- **Honesty slide.** This is a small pilot set written by the author. The baselines' "unknown cost handled = 1.0"
  is an artefact of always answering `null`. Two scoring fixes are documented in `NOTES.md`.

For the slide 2 failure example, use the s03 Direct LLM output: the locked dinner moved and teamLab moved
outside its ticket slot.

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
