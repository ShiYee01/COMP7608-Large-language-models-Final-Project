# Notes on run `nemotron-3-ultra-openrouter-free` (pilot, 10 scenarios × 4 methods)

**Setup.**
- Model: `nvidia/nemotron-3-ultra-550b-a55b:free`, an open-weights MoE model with 550B total and 55B active
  parameters. It is a reasoning model.
- Served by OpenRouter's free tier, temperature 0.
- `LLM_MIN_MAX_TOKENS=16000` was set for **all** methods. Hidden reasoning tokens count toward the completion
  budget, and with the original budget (600 tokens for parsing) the answers could be cut off.
- Token counts below include reasoning tokens. Latency is wall-clock time through OpenRouter, so it depends on
  provider load.
- Scoring rules are identical to the `qwen2.5-3b-local-cpu` run (strict infeasible detection, neutral baseline
  ID normalisation).

**Status.** Pilot / development set written by the system author. These are preliminary numbers. With 10 cases,
a difference of 1–2 cases is not statistically meaningful.

## Summary

| method | task success | feasible (ok cases) | booking F1 | cost exact (known) | infeasible detected | latency (s) | tokens |
|---|---|---|---|---|---|---|---|
| direct | 6/10 | 1.00 | 0.958 | 3/7 | 2/2 | 54 | 14,308 |
| structured | 8/10 | 1.00 | 1.000 | 6/7 | 2/2 | 64 | 14,973 |
| planb | 10/10 | 1.00 | 1.000 | 7/7 | 2/2 | 6 | 2,664 |
| planb_gold | 10/10 | 1.00 | 1.000 | 7/7 | 2/2 | 0.01 | 0 |

## Observations (from `per_case.csv` and `raw_outputs.jsonl`)

**With a strong model, the baselines become good planners.** Every baseline itinerary had 0 hard violations.
All infeasible cases were detected, and booking F1 was ≥ 0.96. The big gap seen with the 3B model is mostly
gone. Most of it was a model-capacity effect.

**The remaining baseline errors are almost all about money:**
- **The change fee was forgotten.** In s01 both baselines answered ¥950 = ¥350 fare difference + ¥600 hotel
  night, without the ¥200 change fee (correct: ¥1,150). In s09 `direct` answered ¥100 instead of ¥300, again
  without the change fee. It also did not flag the hotel's early checkout (booking F1 0.667). Overall, the change
  fee was missing in 3 of the 4 baseline outputs where it applied.
- **"Unknown" was given when the cost was known.** In s04 and s07, `direct` returned `null` although no booking
  was affected (the correct answer is ¥0).
- **One unnecessary change.** In s04, `structured` also moved Tokyo Skytree, which the rain did not affect
  (preservation 0.909).

**PlanB.**
- Every request was parsed correctly (10/10 event types). This includes s03 and s07, which the 3B model got wrong.
- Results are identical to `planb_gold`, so all cost, booking and repair results are exact.
- It used one LLM call of about 2.7k tokens, about 5× fewer than a baseline. Latency was about 6 s against
  54–64 s for the baselines.

## What this means for the claim
- **Do not claim "LLMs cannot replan".** A strong model plans well when it is given all the facts.
- **The defensible claims are narrower:**
  1. The money calculation is where free-form LLM reasoning stays unreliable, even for a 550B model, and an
     error there means telling a traveller the wrong amount.
  2. PlanB's quality does not depend on the model's size, as long as the model parses the request correctly.
     A 3B model reaches 8/10, and PlanB with the gold event reaches 10/10.
  3. PlanB is much cheaper and faster, because the LLM does not need to read the travel matrix or generate a
     whole itinerary.
- To make claim 1 statistically meaningful, the final evaluation needs more cost-heavy scenarios. Examples: change
  fee plus fare difference, refunds, partial refunds, and several bookings affected at once.
