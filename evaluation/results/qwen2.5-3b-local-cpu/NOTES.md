# Notes on run `qwen2.5-3b-local-cpu` (pilot, 10 scenarios × 4 methods)

**Setup.** Qwen2.5-3B-Instruct, GGUF Q4_K_M, served locally by `llama-cpp-python` (OpenAI-compatible API) on
4 CPU cores, temperature 0, n_ctx 12288. All model responses are cached in `.cache/llm/` (not committed), so
re-scoring does not call the model again; latency figures are the original measured ones.

**Status.** Pilot / development set, written by the system author. These are preliminary numbers, not final
results. The scoring rules were fixed before this write-up, with two changes made after looking at the outputs.
Both are documented, and neither changes any PlanB number:
1. `infeasible_detected` is strict: only an explicit `infeasible` counts. The lenient
   `unsafe_plan_refused` also accepts `needs_information`.
2. Baseline itineraries go through neutral ID normalisation (`evaluation/common.py::_normalize_ids`). An item
   re-emitted under a new id (e.g. `a12_new`) at the same place is mapped back to the original activity. Without
   this, a correctly moved return flight was scored as "locked flight deleted".

## Summary

| method | task success | feasible (ok cases) | avg hard violations | preservation | booking F1 | cost exact (known) | infeasible detected (strict) | unsafe plan refused | latency (s) | tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| direct | 2/10 | 0.25 | 3.67 | 0.63 | 0.25 | 0/7 | 1/2 | 2/2 | 462 | 10,093 |
| structured | 1/10 | 0.25 | 1.86 | 0.85 | 0.25 | 0/7 | 0/2 | 1/2 | 480 | 10,520 |
| planb | 8/10 | 0.75 | 0.14 | 0.88 | 0.875 | 6/7 | 2/2 | 2/2 | 45 | 2,211 |
| planb_gold | 10/10 | 1.00 | 0.00 | 1.00 | 1.00 | 7/7 | 2/2 | 2/2 | 0.01 | 0 |

The averages are taken over the cases each column applies to. See `summary.md` for the raw table and
`per_case.csv` for every case.

## Observations (from `per_case.csv` and `raw_outputs.jsonl`)

**Baselines (3B model)**
- **No solvable scenario was solved.** Both baselines succeeded on 0 of the 8 solvable scenarios. Every
  baseline success came from refusing in the two infeasible cases.
- **The baselines never computed a cost.** All 20 baseline outputs have `additional_cost_cny: null`, even though
  the change fee, fare-difference quotes and hotel quote were in the prompt. So their "unknown cost handled = 1.0"
  on s02 is an artefact, not a skill. Cost exact match on the 7 known-cost cases is 0/7.
- **They broke locks and constraints.**
  - s03 (rain 08:00–13:00): `direct` moved the locked sushi dinner (booked 18:30) to 14:30, and moved
    teamLab (ticket slot 14:00–14:30) to 08:30. 9 hard violations.
  - s05 (museum closed): `direct` used place ids that are not in the catalogue (`UNKNOWN_PLACE`) and moved a
    locked item. 7 hard violations.
- **They did not apply the event.**
  - s09 (trip shortened to 12/11): both baselines kept all of day 3 (Ueno, the museum, Akihabara). They also
    put the return flight before the sushi dinner. 5–6 hard violations.
  - s03/s04/s07: activities were left inside the rain or delay window (`EVENT_BLOCKED`). s05 `structured`
    still visited the closed museum (`EVENT_CLOSURE`).
- **Wrong refusals.** s06 (teamLab closed): both baselines answered `needs_information` instead of replanning.
  s07 (`direct`): answered `infeasible` for a solvable delay.
- **Their booking sets were wrong.** Booking F1 0.25. For example, in s03 they named `flight-ret` as affected by
  rain.
- **Infeasible cases.** The strict and lenient scores differ: `structured` answered `ok` on the reservation
  conflict (s08) and `needs_information` on s10.

**PlanB**
- **Every case where it parsed the request correctly succeeded.** Ranking, booking impact and cost were exact:
  - s01 ¥1,150;
  - s02 "unknown" (not 0);
  - s06 −¥180 (provider refund);
  - s09 ¥300 (¥200 change fee + ¥100 fare difference; the unused hotel night, ¥600, is reported separately as forfeited, not as new cash).
- **Both failures are request-parsing errors by the 3B model.** `planb_gold` solves both cases:
  - **s03:** "上午8点到下午1点有暴雨" was parsed as 08:00–**12:00** instead of 13:00. The repair then left
    one activity in the 12:00–13:00 rain window (1 hard violation, judged with the gold event).
  - **s07:** the model returned `affected_end = null` for "10点半之前无法到达". PlanB therefore asked for
    more information (safe, but counted as a failure).
- **Cost of using PlanB.** One LLM call of about 2.2k tokens and about 45 s on CPU. Each baseline call was about
  10k tokens and 7–8 min, because the baseline must read the full facts and generate a whole itinerary.

## Threats to validity
- 10 hand-written scenarios, one simulated city, one small model. The evaluation needs a held-out set and a
  larger model.
- A 3B model is weak at long structured generation. A larger model will likely narrow the gap for the baselines,
  which is why the final report should compare model sizes.
- The ground truth was written by the system author. Ideally the user, or a second person, audits it.
