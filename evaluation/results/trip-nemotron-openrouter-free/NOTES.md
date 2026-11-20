# Notes on run `trip-nemotron-openrouter-free` (new features: trip setup + chat edits)

**Setup.**
- Model: `nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter's free tier, temperature 0,
  `LLM_MIN_MAX_TOKENS=16000` for every method.
- Scenarios: `evaluation/trip_scenarios/`. There are 8 trip-setup cases (T01–T08) and 5 chat-edit cases
  (E01–E05). The ground truth was hand-written from the request and catalogue facts and reviewed by the project
  owner before any model was run.
- Methods:
  - `direct`: the LLM plans or edits the trip itself, given the full catalogue and travel matrix.
  - `structured`: the same, plus explicit rules and a checklist.
  - `planb`: the LLM only extracts the request.
  - `planb_gold`: the planner run on the gold request.
- The run took two days because of the free daily quota (50 requests). Calls from day 1 were cached and reused.
  Re-scoring makes no new calls.

**Status.** This is a pilot / development set of 13 cases, so a difference of 1–2 cases is not significant.

## Changes made after looking at outputs (all documented, all in favour of the baselines)
1. **Planner bug (found in the mock run, before any model call).** A dinner slot on the departure day could take
   the travel time to the airport. Fixed with `settle_meal_slots`.
2. **Baseline schema.** The baseline's `understood.bookings` did not say that a flight's time is the take-off
   time; PlanB's prompt did. The same sentence was added (found in a 1-call smoke test, whose result was discarded).
3. **Scorer: `free_time` items.** The setup schema listed a `free_time` category without defining it. The
   baselines used it for "Travel to X", "Transfer to hotel" and "Lunch break", and once with place id
   `free_time`. PlanB uses it for "eat nearby" meal slots. The scorer first counted such items as invented places
   or as time unavailable for travel, which created false violations for the baselines. Now `free_time` items are
   ignored when judging feasibility, for every method. This raised `direct` setup success from 1/8 to 4/8 and
   `structured` from 7/8 to 8/8. PlanB's numbers did not change.

## Summary

| method | setup success (8) | extraction acc. | plans feasible | preference match | edit success (5) | tokens setup / edit | latency setup / edit |
|---|---|---|---|---|---|---|---|
| direct | 4/8 | 0.969 | 3/5 plans | 0.73 | 4/5 | 25.6k / 27.4k | 47 s / 54 s |
| structured | **8/8** | 0.984 | 7/7 | **0.83** | **5/5** | 29.2k / 28.4k | 118 s / 81 s |
| planb | **8/8** | **1.000** | 7/7 | 0.79 | **5/5** | **4.6k / 3.5k** | **14 s / 6 s** |
| planb_gold | 8/8 | — | 7/7 | 0.91 | 5/5 | 0 | <0.1 s |

"Plans feasible" counts only the cases where a method returned a plan: 7 of the 8 setup cases need one; T08 is
the missing-dates case.

## Observations (from `per_case.csv` and `raw_outputs.jsonl`)

**`direct` (no rules) failed 4 of 8 setup cases:**
- **T02 (anime, 3 days):** a visit to Otome Road at 19:55–21:10, after its 21:00 closing time, and 0 minutes of
  travel between the Pokemon Center and Otome Road.
- **T06 (must-visits on given days):** sushi lunch at 12:00, but the restaurant opens at 17:00. Also three
  transfers shorter than the travel time, e.g. Tsukiji → Senso-ji with 10 of 35 minutes.
- **T03, T07:** it asked a question instead of planning.
  - In T03 it asked for arrival and departure times, although the traveller said they would arrange transport
    themselves.
  - In T07 it reported correctly that Tsukiji is closed on Wednesday, but then asked whether to replace it rather
    than planning the museum.
  - Both are safe but too conservative; the agreed standard requires a plan here.

**Other `direct` behaviour:** in T04 it listed six of its own suggestions as must-visits (an extraction error). In
E03 it moved Hamarikyu, which needed no change, 15 minutes later, breaking "keep everything else unchanged".

**`structured` (rules + checklist):** every setup and edit case passed. Its only extraction slip was T02, where it
did not treat "也想逛逛秋叶原" as a must-visit; it still scheduled Akihabara. Its suggestions matched the stated
preferences best of the three LLM-based methods (0.83).

**`planb`:**
- Every case passed. Every request was parsed correctly, including the English request (T04), the unknown places
  (T03), and the prices and change fee (T05).
- On the full day (E02) it asked with an option (swap Hamarikyu for the Gundam statue).
- In E05 it refused to remove the booked teamLab ticket. Both baselines asked for confirmation instead, offering
  "remove teamLab" as an option; this is also acceptable under the agreed standard.

**Cost:**
- PlanB used about 6× fewer tokens than a baseline for trip setup (4.6k vs 25.6–29.2k) and about 8× fewer for edits.
- It was 3–8× faster for setup and 9–14× faster for edits.

## What this means for the claim
- **For these new features, a strong model with a rule-heavy prompt matches PlanB on correctness** (8/8 and 5/5).
  The difference that remains is cost and speed, plus guarantees by construction: PlanB's constraints are checked
  by code, the baseline's are only asked for in the prompt.
- **Without the rules, the same model fails half of the setup cases** (opening hours, travel time, over-asking).
- These results come from the strong 550B model only. The original evaluation showed that small models fail far
  more often. The same scenarios have since been run with Qwen2.5-3B (`trip-qwen2.5-3b-local-cpu`): there both
  baselines solve 0 of 13 cases, the rule-heavy prompt does not help, and PlanB solves 2/8 setup and 4/5 edit
  cases (every PlanB failure is a request-understanding error).
- 13 hand-written cases are a pilot. The final report needs a held-out set.

## Later change (re-scored from the cache, numbers unchanged)
The 3B run found a planner bug that correct requests never trigger: a stop PlanB suggested just before a meal slot
could leave too little travel time to an early flight. `drop_unfit_suggestions` now removes such suggestions.
This run was re-scored from the cached replies afterwards; every number above is unchanged.

## Gold edit requests added (2026-11-20, after the model runs)
At first `planb_gold` covered trip setup only, because the edit scenarios had no hand-written structured reading
of the request. A `gold_edit` (the correct `EditRequest`, written from the traveller's words only) was then added to
each edit scenario in `scripts/build_trip_scenarios.py` and shown in `REVIEW.md`. It runs PlanB's edit engine with
no LLM, so it needs no model calls and is the same for both models. **Result: 5/5.** No check was changed, and
every other number in this run is unchanged. Test: `test_edit_engine_on_gold_edit_request_meets_every_check`.
