# Trip-setup and edit evaluation `mock-trip`

- LLM: mock (no LLM)
- Scenarios: 13

> **MOCK RUN — pipeline test only.** Baselines return empty answers; NOT experimental results.

| type   | method     |   cases |   success |   status_correct |   extraction_acc |   feasible |   checks_passed |   pref_match |   avg_tokens |   avg_latency_s |   avg_llm_calls |   options_feasible |
|:-------|:-----------|--------:|----------:|-----------------:|-----------------:|-----------:|----------------:|-------------:|-------------:|----------------:|----------------:|-------------------:|
| setup  | direct     |       8 |      0    |            0.875 |            0.417 |        nan |           0     |      nan     |            0 |               0 |               1 |                nan |
| setup  | structured |       8 |      0    |            0.875 |            0.417 |        nan |           0     |      nan     |            0 |               0 |               1 |                nan |
| setup  | planb      |       8 |      0.25 |            0.625 |            0.707 |          1 |           0.486 |        0.831 |            0 |               0 |               0 |                nan |
| setup  | planb_gold |       8 |      1    |            1     |            1     |          1 |           1     |        0.909 |            0 |               0 |               0 |                nan |
| edit   | direct     |       5 |      0.2  |            0.2   |          nan     |        nan |         nan     |      nan     |            0 |               0 |               1 |                nan |
| edit   | structured |       5 |      0.2  |            0.2   |          nan     |        nan |         nan     |      nan     |            0 |               0 |               1 |                nan |
| edit   | planb      |       5 |      1    |            1     |          nan     |        nan |         nan     |      nan     |            0 |               0 |               0 |                  1 |
