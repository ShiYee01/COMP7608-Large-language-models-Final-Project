# PlanB — AI 旅行副驾驶（中文版）

> 本文件夹（`zh/`）存放仓库中 Markdown 文档的中文译本，目录结构与原文件一一对应。
> 原文以英文版为准；英文版更新后，中文版可能需要同步修改。
> 文件路径、命令、代码标识符（如 `planb`、`direct`、`task_success`）保持英文，方便对照代码。
> 中英术语对照见 [`GLOSSARY.md`](GLOSSARY.md)。
>
> | 中文版 | 对应原文 |
> |---|---|
> | `zh/README.md` | `README.md` |
> | `zh/data/README.md` | `data/README.md` |
> | `zh/docs/decisions.md` | `docs/decisions.md` |
> | `zh/docs/evaluation_protocol.md` | `docs/evaluation_protocol.md` |
> | `zh/docs/presentation_outline.md` | `docs/presentation_outline.md` |
> | `zh/docs/presentation_script.md` | 中文讲稿（逐页对应 slides 的演讲者备注，无英文原文） |
> | `zh/evaluation/results/...` | `evaluation/results/...`（各次评测的说明和汇总表） |
>
> `PROJECT_CONTEXT.md` 原本就是中文，没有另做译本。

---

*考虑约束的行程重规划与订单费用影响分析* · COMP7608 期末项目（个人）

旅行途中情况有变时（下雨、景点关闭、列车延误、延长或缩短行程），普通的 LLM 往往会：把整个行程重写一遍、
违反时间或营业时间的约束、漏掉相关联的订单、凭空猜测费用。PlanB 把这件事拆开来做：

- **LLM**：理解用户的请求（自然语言 → 结构化事件），并解释最终结果。
- **确定性的 Python 代码**：校验硬约束，只修复行程中受影响的部分，找出受影响的订单，
  并依据用户自己提供的订单规则计算增量费用（未知 ≠ 0）。
- **用户**：批准或拒绝。批准只会更新 PlanB 里的行程，绝不会改动真实的订单。

```
请求 ─► LLM 解析器 ─► 变化事件(DisruptionEvent) ─► 影响分析 ─► 局部修复（束搜索）
                                                    │                    │
                                                    ▼                    ▼
                                           订单依赖分析 ◄──── 约束校验器
                                                    │
                                                    ▼
                         费用引擎（整数“分”、能处理未知值）─► 排序后的方案
                                                    │
                                 LLM 解释（金额受校验）─► 用户批准 / 拒绝
```

## 快速开始

```bash
pip install -r requirements.txt
python -m pytest -q                      # 38 个单元测试，不需要 LLM
streamlit run app/streamlit_app.py       # 演示界面（没有 API key 也能用：mock 模式）
python evaluation/run_eval.py --mock     # 评测流程测试（mock，不是真实结果）
```

如果要使用真实的（免费 / 开源）模型，把 `.env.example` 复制为 `.env`，并设置 `LLM_BASE_URL`、`LLM_MODEL`、
`LLM_API_KEY`（可用 Groq、OpenRouter 的 `:free` 模型、SiliconFlow，或本地的 Ollama / llama.cpp 服务）。然后运行：

```bash
python evaluation/run_eval.py --run-name my-model
```

结果保存在 `evaluation/results/<run-name>/`（`summary.md`、`summary.csv`、`per_case.csv`、`summary.png`、
`raw_outputs.jsonl`）。LLM 的回复会缓存在 `.cache/llm/`，所以重复运行不花钱，结果也可复现。

## 已实现的功能

| 领域 | 模块 | 状态 |
|---|---|---|
| 数据模型（行程、活动、地点、订单、退改规则、报价、事件、方案……） | `planb/models.py` | ✅ |
| 东京演示数据：24 个地点、274 对交通时间矩阵、3 天行程、5 个订单 | `data/`、`scripts/` | ✅ 模拟数据 |
| 约束校验器：时间重叠、交通时间、营业时间、关闭、天气/延误时段、锁定、行程日期、预算；结果分为 有效 / 无效 / 未知 | `planb/validator.py` | ✅ |
| 订单影响：不受影响 / 需要变更 / 可能受影响 / 未知 | `planb/booking_impact.py` | ✅ |
| 费用引擎：改签费 + 票价差、酒店续住、提前退房、取消退款与商家退款、未知项、放弃的（非现金）损失 | `planb/cost_engine.py` | ✅ |
| 局部修复：保留 / 平移 / 连锁平移 / 换天 / 替换 / 删除，束搜索，排序 | `planb/repair.py` | ✅ |
| 事件类型：天气、地点关闭、交通延误、延长行程、缩短行程、预约变更 | `planb/events.py` | ✅ |
| 预览 → 批准 → 提交，带版本号检查和历史记录 | `planb/store.py` | ✅ |
| LLM 适配层（OpenAI 兼容、缓存、mock），请求解析器（结构校验 + 重试 + 规则兜底） | `planb/llm.py`、`planb/parser.py` | ✅ |
| Agent 编排器：后端状态机，解释中的金额受校验 | `planb/agent.py` | ✅ |
| 对话式新建行程：一段话（日期、想去/不想去、喜好如“安静”“二次元”、用语言说明的已订航班酒店门票）→ 复述确认 → 一句话更正 → 生成每日计划，已订项目锁定 | `planb/trip_request.py`、`planb/planner.py`（`plan_trip`） | ✅ 新功能，尚未评测 |
| 应用使用的扩展地点库：47 个地点，含二次元、安静等标签（评测仍使用 24 个地点的基础库） | `data/*_extended.json` | ✅ 模拟数据 |
| Streamlit 演示：时间轴、地图、手动编辑、事件预设、聊天、差异对比、订单影响、费用明细、批准/拒绝、历史 | `app/streamlit_app.py` | ✅ |
| 基线 A（直接问 LLM）和基线 B（加约束提示的 LLM）、评测指标、10 个试点场景 | `evaluation/` | ✅ |
| 聊天中“不想去 X 了”+ 按喜好推荐；对话式新建行程的评测 | — | 下一步 |
| 40 个场景的测试集、消融实验、React 前端 | — | 计划中 |

## 评测

各方法使用相同的模型、temperature 0、相同的事实信息和输出格式：

- **direct**：基线 A。LLM 自己修改行程并自己计算费用。
- **structured**：基线 B。同上，另外加上明确的约束规则、费用规则和逐步检查清单。
- **planb**：LLM 只解析请求，其余全部由确定性引擎完成。
- **planb_gold**：给 PlanB 正确（标准答案）的结构化事件，用来单独分离出解析错误。

所有输出都由同一个校验器评判。指标：任务成功率、可行性、硬约束违规数、行程保留率、订单影响的
精确率/召回率/F1、费用完全正确（误差 ±¥1）、未知费用的处理、无解识别、延迟、token 数、LLM 调用次数。
场景的标准答案是在 `scripts/build_scenarios.py` 里手工写的（不是由引擎生成的），详见 `docs/evaluation_protocol.md`。

只报告真实运行得到的数字。`--mock` 运行只是流程测试。

### 初步结果：试点集，两个免费的开源权重模型

以下都是真实的数字。每次运行的目录里都有 `summary.md`、`per_case.csv`、`raw_outputs.jsonl`，以及写有分析的
`NOTES.md`。`evaluation/results/model_comparison.png` 把两次运行放在一起对比（由 `python scripts/compare_runs.py` 生成）。

| 方法 | Qwen2.5-3B（本地 CPU）：成功 | 费用完全正确 | Nemotron 3 Ultra 550B-A55B（OpenRouter 免费）：成功 | 费用完全正确 | token 数（Nemotron） |
|---|---|---|---|---|---|
| direct | 2/10 | 0/7 | 6/10 | 3/7 | 14.3k |
| structured | 1/10 | 0/7 | 8/10 | 6/7 | 15.0k |
| planb | 8/10 | 6/7 | 10/10 | 7/7 | 2.7k |
| planb_gold | 10/10 | 7/7 | 10/10 | 7/7 | 0 |

怎么解读：
- **小模型。** 基线几乎全部失败：它们违反锁定和约束，而且从来不计算费用。PlanB 的两次失败都是请求解析错误。
- **大模型。** 基线能做出可行的行程，受影响订单也找得对。剩下的错误都和钱有关：漏掉 ¥200 的改签费
  （在需要算改签费的 4 次输出里漏了 3 次），或者在费用其实是 ¥0 时说“未知”。
- **只要请求解析正确，PlanB 的表现就不受模型大小影响。** 它用的 token 也少了大约 5 倍。

试点集只有 10 个手工编写的开发场景，所以这些数字是初步的。

## 仓库结构

```
planb/        核心包（模型、校验器、修复、订单影响、费用、存储、llm、解析器、agent）
app/          Streamlit 演示
data/         模拟的东京数据（见 data/README.md）
evaluation/   场景、基线、指标、run_eval.py、results/
scripts/      数据 / 场景生成脚本
tests/        单元测试
docs/         设计决策、评测规范、presentation 提纲
zh/           以上 Markdown 文档的中文译本
```

完整的需求和设计见 `PROJECT_CONTEXT.md`。
