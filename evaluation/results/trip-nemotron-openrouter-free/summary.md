# Trip-setup and edit evaluation `trip-nemotron-openrouter-free`

- LLM: nvidia/nemotron-3-ultra-550b-a55b:free @ https://openrouter.ai/api/v1
- Scenarios: 13

| type   | method     |   cases |   success |   status_correct |   extraction_acc |   feasible |   checks_passed |   pref_match |   avg_tokens |   avg_latency_s |   avg_llm_calls |   options_feasible |
|:-------|:-----------|--------:|----------:|-----------------:|-----------------:|-----------:|----------------:|-------------:|-------------:|----------------:|----------------:|-------------------:|
| setup  | direct     |       8 |       0.5 |             0.75 |            0.969 |        0.6 |           0.686 |        0.734 |        25574 |            46.8 |               1 |              nan   |
| setup  | structured |       8 |       1   |             1    |            0.984 |        1   |           1     |        0.831 |        29196 |           118.1 |               1 |              nan   |
| setup  | planb      |       8 |       1   |             1    |            1     |        1   |           1     |        0.789 |         4586 |            14   |               1 |              nan   |
| setup  | planb_gold |       8 |       1   |             1    |            1     |        1   |           1     |        0.909 |            0 |             0   |               0 |              nan   |
| edit   | direct     |       5 |       0.8 |             1    |          nan     |      nan   |         nan     |      nan     |        27373 |            53.6 |               1 |                0.8 |
| edit   | structured |       5 |       1   |             1    |          nan     |      nan   |         nan     |      nan     |        28378 |            80.8 |               1 |                0.8 |
| edit   | planb      |       5 |       1   |             1    |          nan     |      nan   |         nan     |      nan     |         3477 |             5.9 |               1 |                1   |
