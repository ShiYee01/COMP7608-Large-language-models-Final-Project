# PlanB — AI Travel Copilot

*Constraint-aware itinerary replanning and booking cost impact analysis* · COMP7608 final project (individual)

When something changes during a trip (rain, a closed venue, a train delay, extending or shortening the trip),
a plain LLM tends to rewrite the whole plan, break time/opening-hour constraints, miss linked bookings, and
guess fees. PlanB splits the job:

- **LLM** — understands the request (natural language → structured event) and explains the result.
- **Deterministic Python** — validates hard constraints, repairs only the affected part of the plan, finds
  affected bookings, and computes incremental cost from the user's own booking rules (unknown ≠ 0).
- **User** — approves or rejects. Approval only updates PlanB's itinerary; it never changes real bookings.

```
request ─► LLM parser ─► DisruptionEvent ─► impact analysis ─► local repair (beam search)
                                                  │                     │
                                                  ▼                     ▼
                                     booking dependency ◄── constraint validator
                                                  │
                                                  ▼
                              cost engine (integer fen, unknown-aware) ─► ranked proposals
                                                  │
                                    LLM explanation (amounts guarded) ─► user approve / reject
```

## Quick start

```bash
pip install -r requirements.txt
python -m pytest -q                      # 30 unit tests, no LLM needed
streamlit run app/streamlit_app.py       # demo UI (works without an API key: mock mode)
python evaluation/run_eval.py --mock     # evaluation pipeline test (mock, NOT real results)
```

To use a real (free / open) model, copy `.env.example` to `.env` and set `LLM_BASE_URL`, `LLM_MODEL`,
`LLM_API_KEY` (Groq, OpenRouter `:free`, SiliconFlow, or a local Ollama / llama.cpp server). Then:

```bash
python evaluation/run_eval.py --run-name my-model
```

Results go to `evaluation/results/<run-name>/` (`summary.md`, `summary.csv`, `per_case.csv`, `summary.png`,
`raw_outputs.jsonl`). LLM replies are cached in `.cache/llm/`, so re-runs are free and reproducible.

## What is implemented

| Area | Module | Status |
|---|---|---|
| Data models (Trip, Activity, Place, Booking, Policy, Quote, Event, Proposal …) | `planb/models.py` | ✅ |
| Tokyo demo data: 24 places, 274-pair travel matrix, 3-day trip, 5 bookings | `data/`, `scripts/` | ✅ simulated |
| Constraint validator: overlap, travel time, opening hours, closures, weather/delay windows, locks, trip window, budget; valid / invalid / unknown | `planb/validator.py` | ✅ |
| Booking impact: unaffected / change_required / potentially_affected / unknown | `planb/booking_impact.py` | ✅ |
| Cost engine: change fee + fare difference, hotel extension, early check-out, cancellation & provider refunds, unknown components, forfeited (non-cash) loss | `planb/cost_engine.py` | ✅ |
| Local repair: Keep / Shift / cascade shift / Move-day / Replace / Remove, beam search, ranking | `planb/repair.py` | ✅ |
| Event types: weather, place closed, transport delay, trip extension, trip shortening, reservation change | `planb/events.py` | ✅ |
| Preview → Approve → Commit with revision check and history | `planb/store.py` | ✅ |
| LLM adapter (OpenAI-compatible, cache, mock), request parser with schema validation + retry + rule fallback | `planb/llm.py`, `planb/parser.py` | ✅ |
| Agent orchestrator with backend state machine and amount-guarded explanations | `planb/agent.py` | ✅ |
| Initial itinerary generation (Story A, deterministic greedy) | `planb/planner.py` | ✅ basic |
| Streamlit demo: timeline, map, manual edits, event presets, chat, diff, booking impact, cost breakdown, approve/reject, history | `app/streamlit_app.py` | ✅ |
| Baselines A (direct LLM) and B (constraint-prompted LLM), metrics, 10 pilot scenarios | `evaluation/` | ✅ |
| 40-scenario test set, ablations, React front end, booking-text extraction | — | planned |

## Evaluation

Methods (same model, temperature 0, same facts and output schema):

- **direct** — Baseline A: the LLM edits the itinerary and computes the cost itself.
- **structured** — Baseline B: same, plus explicit constraint rules, cost rules and a step-by-step checklist.
- **planb** — LLM parses the request; the deterministic engine does the rest.
- **planb_gold** — PlanB with the gold structured event (isolates parsing errors).

Every output is judged by the same validator. Metrics: task success, feasibility, hard violations,
plan preservation, booking-impact P/R/F1, cost exact match (±¥1), unknown-cost handling, infeasible detection,
latency, tokens, LLM calls. Scenario ground truth is written by hand in `scripts/build_scenarios.py` (not produced
by the engine) — see `docs/evaluation_protocol.md`.

Only report numbers from real runs. The `--mock` run is a pipeline test.

### Preliminary results: pilot set, two free open-weights models

These are real numbers. Each run's directory has `summary.md`, `per_case.csv`, `raw_outputs.jsonl` and a
`NOTES.md` with the analysis. `evaluation/results/model_comparison.png` puts the two runs side by side
(`python scripts/compare_runs.py`).

| method | Qwen2.5-3B (local CPU): success | cost exact | Nemotron 3 Ultra 550B-A55B (OpenRouter free): success | cost exact | tokens (Nemotron) |
|---|---|---|---|---|---|
| direct | 2/10 | 0/7 | 6/10 | 3/7 | 14.3k |
| structured | 1/10 | 0/7 | 8/10 | 6/7 | 15.0k |
| planb | 8/10 | 6/7 | 10/10 | 7/7 | 2.7k |
| planb_gold | 10/10 | 7/7 | 10/10 | 7/7 | 0 |

How to read this:
- **Small model.** The baselines fail almost everywhere. They break locks and constraints and never compute a
  cost. Both PlanB failures are request-parsing errors.
- **Large model.** The baselines produce feasible plans with correct booking sets. Their remaining errors are
  about money: they forget the ¥200 change fee (3 of 4 outputs where it applied) or say "unknown" when the
  cost is ¥0.
- **PlanB does not depend on model size** once the request is parsed correctly. It also uses about 5× fewer tokens.

The pilot set is 10 hand-written development scenarios, so these numbers are preliminary.

## Repository layout

```
planb/        core package (models, validator, repair, booking impact, cost, store, llm, parser, agent)
app/          Streamlit demo
data/         simulated Tokyo fixtures (see data/README.md)
evaluation/   scenarios, baselines, metrics, run_eval.py, results/
scripts/      fixture / scenario generators
tests/        unit tests
docs/         design decisions, evaluation protocol, presentation outline
zh/           Chinese translations of the Markdown docs (see zh/README.md)
```

See `PROJECT_CONTEXT.md` for the full requirements and design.
