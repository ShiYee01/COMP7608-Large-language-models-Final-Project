# Evaluation run `qwen2.5-3b-local-cpu`

- LLM: qwen2.5-3b-instruct @ http://127.0.0.1:8080/v1
- Scenarios: 10
- Methods: direct, structured, planb, planb_gold

| method     |   cases |   task_success |   json_valid |   status_accuracy |   feasibility_rate(ok cases) |   avg_hard_violations |   plan_preservation |   booking_f1 |   cost_exact_match(known) |   unknown_cost_handled |   infeasible_detected |   unsafe_plan_refused |   avg_latency_s |   avg_tokens |   avg_llm_calls |
|:-----------|--------:|---------------:|-------------:|------------------:|-----------------------------:|----------------------:|--------------------:|-------------:|--------------------------:|-----------------------:|----------------------:|----------------------:|----------------:|-------------:|----------------:|
| direct     |      10 |            0.2 |            1 |               0.7 |                         0.25 |                 3.667 |               0.63  |        0.25  |                     0     |                      1 |                   0.5 |                   1   |         462.202 |      10092.7 |               1 |
| structured |      10 |            0.1 |            1 |               0.7 |                         0.25 |                 1.857 |               0.851 |        0.25  |                     0     |                      1 |                   0   |                   0.5 |         480.088 |      10519.8 |               1 |
| planb      |      10 |            0.8 |            1 |               0.9 |                         0.75 |                 0.143 |               0.875 |        0.875 |                     0.857 |                      1 |                   1   |                   1   |          44.546 |       2210.8 |               1 |
| planb_gold |      10 |            1   |            1 |               1   |                         1    |                 0     |               1     |        1     |                     1     |                      1 |                   1   |                   1   |           0.007 |          0   |               0 |
