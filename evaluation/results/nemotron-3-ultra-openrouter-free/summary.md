# Evaluation run `nemotron-3-ultra-openrouter-free`

- LLM: nvidia/nemotron-3-ultra-550b-a55b:free @ https://openrouter.ai/api/v1
- Scenarios: 10
- Methods: direct, structured, planb, planb_gold

| method     |   cases |   task_success |   json_valid |   status_accuracy |   feasibility_rate(ok cases) |   avg_hard_violations |   plan_preservation |   booking_f1 |   cost_exact_match(known) |   unknown_cost_handled |   infeasible_detected |   unsafe_plan_refused |   avg_latency_s |   avg_tokens |   avg_llm_calls |
|:-----------|--------:|---------------:|-------------:|------------------:|-----------------------------:|----------------------:|--------------------:|-------------:|--------------------------:|-----------------------:|----------------------:|----------------------:|----------------:|-------------:|----------------:|
| direct     |      10 |            0.6 |            1 |                 1 |                            1 |                     0 |               1     |        0.958 |                     0.429 |                      1 |                     1 |                     1 |          53.907 |      14308   |               1 |
| structured |      10 |            0.8 |            1 |                 1 |                            1 |                     0 |               0.989 |        1     |                     0.857 |                      1 |                     1 |                     1 |          64.151 |      14972.8 |               1 |
| planb      |      10 |            1   |            1 |                 1 |                            1 |                     0 |               1     |        1     |                     1     |                      1 |                     1 |                     1 |           6.003 |       2663.9 |               1 |
| planb_gold |      10 |            1   |            1 |                 1 |                            1 |                     0 |               1     |        1     |                     1     |                      1 |                     1 |                     1 |           0.008 |          0   |               0 |
