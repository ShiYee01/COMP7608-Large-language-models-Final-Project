# Demo data

All data in this folder is **simulated** for a course demo. It is not real-time and not verified.

| File | Content | Source |
|---|---|---|
| `places/tokyo_places.json` | 24 Tokyo places: approximate coordinates, illustrative opening hours, entry prices in CNY fen | hand-written fixture (`scripts/build_fixtures.py`) |
| `travel_times/tokyo_matrix.json` | 274 place pairs; minutes estimated from straight-line distance (walk < 1.2 km, else transit formula) | synthetic (`scripts/build_fixtures.py`) |
| `sample_trips/tokyo_3day.json` | 3-day trip 2026-12-10 → 12-12 (Thu–Sat), 12 activities | fixture (`scripts/build_sample_trip.py`) |
| `sample_bookings/tokyo_bookings.json` | 2 flights, 1 hotel, teamLab ticket, sushi reservation, with refund/change rules and alternative quotes | user-provided style fixture |

`places/tokyo_places_extended.json` + `travel_times/tokyo_matrix_extended.json`: the base 24 places plus
23 more (area hotels, Narita, anime spots, quiet gardens and shrines, lively streets) and extra tags such as
`quiet`, `lively`, `history`. Used by the app for trip planning and recommendations; the recorded
evaluation keeps the base files so its prompts and cached results stay reproducible.

Deliberate gaps (to test unknown handling): `yanaka_ginza` has unknown opening hours; the pairs
`yanaka_ginza~ghibli_museum` and `yanaka_ginza~odaiba_seaside` are missing from the matrix; the sushi dinner price is unknown.

Story D numbers (PROJECT_CONTEXT.md §4): return flight paid ¥1,800, change fee ¥200, fare difference ¥350,
extra hotel night ¥600 → incremental cost **¥1,150**.

Regenerate with `python scripts/build_fixtures.py && python scripts/build_sample_trip.py && python scripts/build_scenarios.py`.
