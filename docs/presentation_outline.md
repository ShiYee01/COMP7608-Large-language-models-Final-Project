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
- Show one real baseline failure: even the 550B model answered ¥950 instead of ¥1,150 for "stay one more day"
  (it forgot the ¥200 change fee). See `evaluation/results/nemotron-3-ultra-openrouter-free/raw_outputs.jsonl`, s01.

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

## 8. Preliminary results: two free open models (real runs)
10 pilot scenarios × 4 methods, temperature 0. Show `evaluation/results/model_comparison.png`.

| method | Qwen2.5-3B (local CPU) | Nemotron 3 Ultra 550B (OpenRouter free) |
|---|---|---|
| Direct LLM | 2/10 success, cost 0/7 | 6/10 success, cost 3/7 |
| Constraint-prompted LLM | 1/10, cost 0/7 | 8/10, cost 6/7 |
| **PlanB** | **8/10, cost 6/7** | **10/10, cost 7/7** |
| PlanB + gold event | 10/10, cost 7/7 | 10/10, cost 7/7 |

Talking points:
- **Small model (3B): the baselines collapse.** They solve 0 of the 8 solvable cases and never compute a cost.
  - Rain (s03): moved the locked 18:30 dinner to 14:30, with 9 hard violations.
  - Shortened trip (s09): kept the whole of day 3.
- **Large model (550B): the baselines plan well.** They have 0 hard violations and detect every infeasible case.
  Be honest about this: a strong model is a good planner when it is given all the facts.
- **But money is still wrong with the large model.**
  - s01: ¥950 instead of ¥1,150, because the ¥200 change fee was forgotten.
  - The change fee was forgotten in 3 of the 4 baseline outputs where it applied.
  - Cost exact match: direct 3/7, structured 6/7, PlanB 7/7.
- **PlanB is stable across model size.** The engine is deterministic: PlanB + gold event is 10/10 for both
  models. The 3B model's two failures are parsing errors (s03 read "下午1点" as 12:00; s07 left out the time
  the delay ends, so PlanB asked instead of guessing).
- **PlanB is cheaper.** One call of about 2.5k tokens vs about 14k for a baseline. With the large model, PlanB
  took about 6 s and a baseline 54–64 s.
- **Honesty.** This is a small pilot set written by the author, so a difference of 1–2 cases is not significant.
  The scoring fixes are documented in each run's `NOTES.md`.

**Refined claim:** the LLM is good at understanding and, when strong, at planning. Exact money calculation and
guaranteed constraint satisfaction should come from code. PlanB makes a small free model usable.

For the slide 2 failure example, use s01 from the large model: it gave a convincing explanation that was missing
¥200. For a dramatic example, use s03 from the 3B model.

## 9. Limitations and plan to the final
- Pilot set is small and written by the author → expand to ~40 scenarios with a held-out split.
- Simulated data, one city, synthetic travel times.
- Next: more scenarios, more cost-heavy scenarios (fees + fare differences + refunds across several bookings), ablations
  (without local repair / without validator / LLM-only cost), a mid-size Qwen as a third model, booking-text extraction, React front end if time allows.

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
- *Why these models? Why not Qwen for the large one?* The budget is zero, so only free open-weights models are
  used. The small model is Qwen2.5-3B, run locally. The large model was the biggest free open model on OpenRouter
  that could actually be called on the day of the run. No Qwen model was in the free list then, and Gemma 4 31B
  was rate-limited upstream. The system talks to any model through an OpenAI-compatible API, so swapping in a
  Qwen model is a configuration change and is planned for the final.
- *With a strong model the baselines are close. Is PlanB still needed?* Yes, for three reasons:
  - Money is still wrong (cost exact 3/7 and 6/7 vs 7/7).
  - PlanB's output is checked by construction, not by trust.
  - PlanB costs about 5× fewer tokens and works with a 3B model.
