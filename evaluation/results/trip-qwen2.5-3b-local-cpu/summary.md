# Trip-setup and edit evaluation `trip-qwen2.5-3b-local-cpu`

- LLM: qwen2.5-3b-instruct @ http://127.0.0.1:8080/v1
- Scenarios: 13

| type   | method     |   cases |   success |   status_correct |   extraction_acc |   feasible |   checks_passed |   pref_match |   avg_tokens |   avg_latency_s |   avg_llm_calls |   options_feasible |
|:-------|:-----------|--------:|----------:|-----------------:|-----------------:|-----------:|----------------:|-------------:|-------------:|----------------:|----------------:|-------------------:|
| setup  | direct     |       8 |      0    |            0.875 |            0.66  |      0.143 |           0.729 |        0.556 |        20022 |           182.1 |               1 |             nan    |
| setup  | structured |       8 |      0    |            0.875 |            0.629 |      0     |           0.7   |        0.375 |        20550 |           333.1 |               1 |             nan    |
| setup  | planb      |       8 |      0.25 |            0.875 |            0.752 |      0.667 |           0.686 |        0.871 |         3613 |            53.8 |               1 |             nan    |
| setup  | planb_gold |       8 |      1    |            1     |            1     |      1     |           1     |        0.909 |            0 |             0   |               0 |             nan    |
| edit   | direct     |       5 |      0    |            0.8   |          nan     |    nan     |         nan     |      nan     |        21718 |           580.6 |               1 |               0    |
| edit   | structured |       5 |      0    |            0.8   |          nan     |    nan     |         nan     |      nan     |        21679 |           333.7 |               1 |               0.2  |
| edit   | planb      |       5 |      0.8  |            1     |          nan     |    nan     |         nan     |      nan     |         2872 |            13.4 |               1 |               0.75 |
