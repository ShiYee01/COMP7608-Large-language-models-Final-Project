# Notes on run `trip-qwen2.5-3b-local-cpu` (new features: trip setup + chat edits)

**Setup.**
- Model: Qwen2.5-3B-Instruct (GGUF Q4_K_M), served locally on CPU by llama-cpp-python (4 threads,
  `n_ctx` 28672), temperature 0, OpenAI-compatible API. The same model as the original 3B run.
- Scenarios, methods, prompts and scorer: exactly as in `trip-nemotron-openrouter-free` (same 13 reviewed pilot
  cases, same `evaluation/trip_eval.py`). Only the model changed.
- Speed: about 15 tokens/s for reading the prompt and 3.5 tokens/s for writing. A baseline prompt is about 20k
  tokens, because it contains the whole catalogue and travel matrix. llama.cpp reuses the shared beginning of
  consecutive prompts, so each method was run as one block. **Latencies therefore depend on the order of the
  calls**: the first call of each block also pays about 20 minutes of prompt reading. Compare them only roughly.

**Status.** Pilot / development set of 13 cases; a difference of 1–2 cases is not significant.

## Changes made during or after the run (all documented)
1. **Client timeout (harness, before scoring).** Two `direct` edit calls (E01, E05) hit the OpenAI client's
   default 600 s timeout three times: an answer of about 2,300 tokens takes about 11 minutes at 3.5 tokens/s.
   `LLM_TIMEOUT` was added to `planb/llm.py` and set to 2,400 s, and the two calls were repeated so the
   baseline could finish its answer. This only helps the baselines; no reply was changed or discarded.
2. **Planner bug found by this run (PlanB, after scoring).** In T02, the 3B model misread the departure as 15:00.
   On that day the planner placed one of its own suggestions (Nezu Shrine) right before the lunch slot; when
   checking a gap that ends at a meal slot it did not look past the meal to the flight. When the lunch slot was
   then dropped, only 60 of the 75 minutes needed to reach Haneda were left. This never happened with correct
   requests, so the Nemotron run did not show it. Fix: `drop_unfit_suggestions` in `planb/planner.py` removes any
   stop that PlanB itself suggested if it causes a hard violation (the user's own places and bookings are never
   removed); regression test `test_suggestion_before_lunch_never_breaks_travel_to_an_early_flight`.
   Both runs were re-scored from the cache (no new model calls):
   - this run: T02 for PlanB went from 10 to 8 hard violations (the travel violation is gone; the 8 that remain
     come from the wrong month, see below) and preference match from 0.84 to 0.87. **No success count changed.**
   - `trip-nemotron-openrouter-free`: every number unchanged.

## Summary

| method | setup success (8) | extraction acc. | plans feasible | preference match | edit success (5) | tokens setup / edit | latency setup / edit |
|---|---|---|---|---|---|---|---|
| direct | 0/8 | 0.66 | 1/7 plans | 0.56 | 0/5 | 20.0k / 21.7k | 182 s / 581 s |
| structured | 0/8 | 0.63 | 0/7 plans | 0.38 | 0/5 | 20.6k / 21.7k | 333 s / 334 s |
| planb | **2/8** | **0.75** | **4/6 plans** | **0.87** | **4/5** | **3.6k / 2.9k** | **54 s / 13 s** |
| planb_gold | 8/8 | — | 7/7 | 0.91 | — | 0 | <0.1 s |

"Plans feasible" counts the cases where the method returned a plan, judged against the true facts of the request.

## Observations (from `per_case.csv` and `raw_outputs.jsonl`)

**Baselines (`direct`, `structured`): 0 of 13 cases solved.**
- **The plans are fragments.** For 2–3-day trips the baselines returned 1–3 items in most cases (at most 16).
  Most plans had no departure flight at all, or put it at the wrong time, so `c_bookings_locked` failed in all
  12 returned plans that had bookings to keep (T03 has none).
- **Hard rules broken:** opening hours in 13 of the 14 returned plans, plus travel time and overlaps. For
  example, in T05 `structured` had 7 violations.
- **T08 (no dates given):** both baselines invented dates and planned instead of asking.
- **Edits:** the schema asks for the FULL updated itinerary; the baselines returned only the changed items, so
  every option dropped the locked bookings. Other errors:
  - E03: `direct` put "lunch at Tsukiji" at 18:00.
  - E04: both replaced the traveller's tempura restaurant with the demo sushi restaurant (`direct` also invented
    a place id).
  - E05: both removed the booked teamLab ticket instead of refusing or asking.
- **Adding the rules did not help this model:** `structured` scored no better than `direct`, because a long rule
  list in a 20k-token prompt is beyond a 3B model.

**`planb`: every failure is a request-understanding error by the 3B model; the planner itself made none
(after the fix above).**
- **Passed:** T04 (English request) and T08 (asked for the missing dates).
- **The commonest error was a missed departure flight** (T01, T05, T06, T07). Others:
  - T02: misread the month (15–17 November, which is already past, instead of December), 17:00 as 15:00, and the
    Haneda arrival as Narita.
  - T05: took "arrive at Haneda at 15:30" as the time of the sushi booking. The planner kept the booking where it
    was told and flagged it as outside opening hours.
  - T01 and T03: added landmarks the user did not name (Senso-ji, Ginza Six).
  - T07: lost the end date, so PlanB asked for it instead of guessing.
- **Edits 4/5:**
  - E01–E03 and E05 passed: replacement options, ask with options on the full day, Tsukiji lunch at 12:00, and
    refusal to remove a booking.
  - E04 failed: the model mapped the traveller's own tempura restaurant to Senso-ji. PlanB then reported that
    Senso-ji is closed at 18:00 instead of planning the restaurant.
- **`planb_gold` is 8/8.** With a correct request, the planner meets every check, as it did with Nemotron.

**Cost:** PlanB used about 6× fewer tokens than a baseline for setup and about 7× fewer for edits, and was
3–6× faster for setup and 25–45× faster for edits.

## Comparison with the 550B model (`trip-nemotron-openrouter-free`)

| method | setup: 3B | setup: 550B | edit: 3B | edit: 550B |
|---|---|---|---|---|
| direct | 0/8 | 4/8 | 0/5 | 4/5 |
| structured | 0/8 | 8/8 | 0/5 | 5/5 |
| planb | 2/8 | 8/8 | 4/5 | 5/5 |
| planb_gold | 8/8 | 8/8 | — | — |

- **The original finding repeats on the new features.** With a small model the baselines collapse (0/13) and the
  rule-heavy prompt does not save them. With a strong model the rule-heavy prompt catches up.
- **PlanB degrades much less, but it degrades:** setup drops from 8/8 to 2/8 because extracting a long paragraph
  with several bookings is hard for a 3B model. Edits hold up (4/5) because an edit request is short.
- **The planner is not the bottleneck:** the gold request gives 8/8 for both models. This supports the design
  choice of a read-back step: in the app the traveller sees what PlanB understood (dates, flights, hotel,
  must-visits) and corrects it in one sentence before the plan is made. That step is not part of this one-shot
  evaluation.

## Possible next steps (not done, to avoid tuning on the pilot set)
- Cross-check the LLM extraction with the rule extractor: for example, flag a departure flight that the rule
  extractor finds but the LLM leaves out, and ask the user to confirm it.
- In chat edits, do not accept a catalogue place that the traveller never named (E04).
- Evaluate both on a held-out set, not on these 13 cases.
