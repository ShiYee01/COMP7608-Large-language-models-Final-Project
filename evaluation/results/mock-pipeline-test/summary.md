# Evaluation run `mock-pipeline-test`

- LLM: mock (no LLM)
- Scenarios: 10
- Methods: direct, structured, planb, planb_gold

> **MOCK RUN — pipeline test only.** Baselines return the unchanged itinerary; these numbers are NOT experimental results.

| method     |   cases |   task_success |   json_valid |   status_accuracy |   feasibility_rate(ok cases) |   avg_hard_violations |   plan_preservation |   booking_f1 |   cost_exact_match(known) |   unknown_cost_handled |   infeasible_detected |   unsafe_plan_refused |   avg_latency_s |   avg_tokens |   avg_llm_calls |
|:-----------|--------:|---------------:|-------------:|------------------:|-----------------------------:|----------------------:|--------------------:|-------------:|--------------------------:|-----------------------:|----------------------:|----------------------:|----------------:|-------------:|----------------:|
| direct     |      10 |              0 |            1 |               0.8 |                         0.25 |                  1.25 |                   1 |          0.5 |                         0 |                      1 |                     0 |                     0 |           0     |            0 |               1 |
| structured |      10 |              0 |            1 |               0.8 |                         0.25 |                  1.25 |                   1 |          0.5 |                         0 |                      1 |                     0 |                     0 |           0     |            0 |               1 |
| planb      |      10 |              1 |            1 |               1   |                         1    |                  0    |                   1 |          1   |                         1 |                      1 |                     1 |                     1 |           0.008 |            0 |               0 |
| planb_gold |      10 |              1 |            1 |               1   |                         1    |                  0    |                   1 |          1   |                         1 |                      1 |                     1 |                     1 |           0.007 |            0 |               0 |
