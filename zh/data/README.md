# 演示数据（中文版）

> 原文：`data/README.md`

本文件夹里的所有数据都是为课程演示而**模拟**的，不是实时数据，也没有经过核实。

| 文件 | 内容 | 来源 |
|---|---|---|
| `places/tokyo_places.json` | 东京 24 个地点：大致坐标、示意性的营业时间、门票价格（单位：人民币“分”） | 手写的固定数据（`scripts/build_fixtures.py`） |
| `travel_times/tokyo_matrix.json` | 274 对地点；分钟数由直线距离估算（1.2 公里以内按步行，否则按公共交通公式） | 合成数据（`scripts/build_fixtures.py`） |
| `sample_trips/tokyo_3day.json` | 3 天行程，2026-12-10 → 12-12（周四至周六），12 个活动 | 固定数据（`scripts/build_sample_trip.py`） |
| `sample_bookings/tokyo_bookings.json` | 2 个航班、1 家酒店、teamLab 门票、寿司店订位，附带退改规则和替代报价 | 仿照“用户提供”格式的固定数据 |

`places/tokyo_places_extended.json` + `travel_times/tokyo_matrix_extended.json`：在基础的 24 个地点之外再加 23 个
（各区域代表酒店、成田机场、二次元地点、安静的庭园和神社、热闹的街区），并增加 `quiet`（安静）、`lively`（热闹）、
`history`（历史）等标签。应用用它来规划和推荐；已记录的评测仍使用基础文件，保证提示词和缓存结果可以复现。

故意留的缺口（用来测试对“未知”的处理）：`yanaka_ginza`（谷中银座）的营业时间未知；矩阵中缺少
`yanaka_ginza~ghibli_museum` 和 `yanaka_ginza~odaiba_seaside` 这两对；寿司晚餐的价格未知。

Story D 的数字（PROJECT_CONTEXT.md §4）：返程机票已付 ¥1,800，改签费 ¥200，票价差 ¥350，
酒店多住一晚 ¥600 → 增量费用 **¥1,150**。

重新生成数据：`python scripts/build_fixtures.py && python scripts/build_sample_trip.py && python scripts/build_scenarios.py`。
