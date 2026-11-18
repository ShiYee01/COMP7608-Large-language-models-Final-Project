# PlanB — AI Travel Copilot

> **Codex 项目上下文与开发总说明（Project Context & Technical Design）**  
> **版本：** v1.0 · 2026-11-19  
> **项目性质：** COMP7608 Large Language Models 相关个人 AI 大项目（暂定选题）  
> **状态：** 需求与技术设计阶段，**不代表已有代码已经实现**  
> **使用方式：** 将本文件放在仓库根目录（可命名为 `PROJECT_CONTEXT.md`），让 ClaudeCode在任何开发、重构或评测工作前完整阅读。若仓库代码与本文冲突，先检查并报告，不要擅自覆盖已有有效实现。

---

## 0. 给 ClaudeCode的优先指令（请先阅读）

你是一名协助开发 **PlanB — AI Travel Copilot** 的软件工程与 AI Agent 开发助手。开发目标是实现**完整、可演示、可测试、可比较评估**的个人课程项目，而不是只做一个套壳聊天页面，也不是追求一篇新的算法研究论文。

开发时必须遵守以下原则：

1. **先阅读项目仓库与本文，再改代码。** 检查已有目录、依赖、数据、测试、Git 状态；不要假定这是空仓库或已有功能均正确。
2. **模块化、逐步实现。** 优先数据模型 → 可验证的确定性业务逻辑 → Agent 工作流 → 前端 → Baseline 与实验。每一步能够独立测试。
3. **LLM 负责理解、提议和解释；Python 负责约束验证、费用计算和受控写入。** 不要让模型凭空计算金额或虚构开放时间、交通时长、退款规则。
4. **用户是最后的决策者。** Agent 只能创建 `PlanProposal`（候选方案），**不得未经用户确认修改正式行程，也不得真实改签、订房、取消订单或支付**。
5. **Demo 和评测数据来自用户提供或本地预设的静态资料。** 当前版本**不需要**实时天气、航班、酒店价格、地图路线或外部订票 API。不要自行接入需要付费的外部平台、爬虫或个人账号。
6. **明确未知值。** 缺失价格/退款规则/交通时间应标记为 `unknown`，而不是 0、猜测值或“已验证”。
7. **课程作业详细官方要求尚未公布。** 当前设计只基于老师口头方向：发现 AI 应用问题，提出方法，通过基线对照和量化实验展示效果；任何正式评分标准、交付格式、截止时间都**不能臆造**。
8. **这是一个个人项目。** 以可完成、可解释、可复现实验为目标。优先简单透明的架构；不要无必要地引入多 Agent、微服务、复杂优化器或云服务。
9. **不能把“预期改进”写成实际结论。** 任何成功率、准确率、费用节省等具体提升必须来自真实实验。
10. **每轮开发向用户说明：** 已检查什么、修改哪些文件、执行哪些测试、发现哪些限制、下一步建议，不要宣称未运行的代码已验证通过。

### 0.1 信息优先级

1. 用户后续的最新明确决定；
2. 老师未来发布的正式 Assignment Instructions / Rubric（老师说自由度较高，主要是激发学生兴趣）；
3. 本文中的 **已确定要求**；
4. 本文中的 **暂定设计建议**（可根据技术证据合理调整，修改时说明）；
5. Codex 自行提出的建议（不可擅自当作需求）。

---

## 1. 课程背景、用户目标和选题动机

### 1.1 已知课程/作业背景

- 课程/项目上下文：**COMP7608 — Large Language Models**；此次讨论的是拟开展的 **AI 相关个人大项目 / Final Project**。
- 老师初步说明主题**不限，只要与 AI 相关**。
- 重点不是仅开发可运行的 AI 应用，而是：
  1. 识别一个真实的 AI 应用不足（Problem Identification）；
  2. 提出相应方法或系统改进（Proposed Solution）；
  3. 设置公平的现有方法 / 基线（Baseline）；
  4. 进行量化评测和结果分析（Evaluation & Comparison）。
- **目前没有获得/确认完整正式要求**，例如具体评分标准、数据集要求、是否必须训练模型、团队规则、报告篇幅、展示时长、截止日期等，老师说比较自由。
- 用户选择了**个人完成**，目标是**课程成绩 + 技术能力 + AI Agent 开发简历价值**兼顾。
- 用户不喜欢纯研究型、单纯改善 RAG/幻觉率的抽象题目，更倾向有趣、真实、可交互、可实际体验且能自然设计实验的 AI 产品。

### 1.2 项目选择过程（背景而非新增要求）

用户曾考虑 RAG 优化、Prompt Injection 防御、Computer-Use Agent、AI 教学工具等，最终决定选择 **PlanB**：既能自动规划旅行，又能在突发事件和手动变更时**可靠地修复日程、解释影响并估算订单变更费用**。

PlanB 的重点是 **Agent 工具协作、结构化状态、约束验证、依赖关系和成本感知决策**，不要求原创训练大模型，也不要求从零实现通用旅行搜索平台。

### 1.3 产品定位

**产品名称：** PlanB — AI Travel Copilot  
**英文完整题目：** *PlanB: An AI-Powered Travel Copilot with Constraint-Aware Itinerary Replanning and Booking Cost Impact Analysis*  
**中文名称：** 面向旅行变化的约束感知行程重规划与预订成本分析智能体

一句话说明：

> 让用户通过自然语言生成和自由编辑旅行计划；当旅行发生变化时，PlanB 能识别受影响的活动与订单，在尽量保留原计划的同时生成可行替代方案，并依据用户提供的退改规则估算额外成本，最终由用户确认。

### 1.4 项目要解决的三个主要问题

1. **缺少可靠的动态重规划：** 普通 LLM 对突发情况常整体重写行程，可能无必要地删除已预订或用户重视的安排。
2. **缺少确定性约束验证：** 生成的行程可能时间重叠、交通来不及、违反开放/预约时段、超预算或更改已锁定活动。
3. **缺少订单连锁影响与成本分析：** 延后返程、变更景点或住宿可能触发机票改签、酒店续住、门票损失；普通 LLM 容易遗漏依赖或猜测费用。

**研究/工程核心问题：** 能否通过结构化行程状态、约束验证、局部修复和订单依赖/成本引擎，比直接 LLM 修改行程更可靠地应对旅行变化？

---

## 2. 已确定的产品决策（必须保留）

| 主题 | 已确定内容 |
|---|---|
| 初始规划 | AI 根据目的地、日期、预算、兴趣、旅行人数等生成初始行程 |
| 用户自由编辑 | 可以手动添加、删除、修改、移动、调整时间、锁定景点和活动；也可以通过聊天提出修改 |
| 主要特色 | 因天气、景点关闭、交通延误、行程日期改变、用户偏好改变等触发**动态重规划** |
| 局部调整 | 优先只修改受影响部分，尽量保留仍可行且用户重视的安排 |
| 行程约束 | 时间、交通、开放时间、预约、锁定活动、预算和行程可行性检查 |
| 订单信息 | Demo 中由用户录入或加载**特定的机票/酒店/景点预约**及其退改条款和备选价格 |
| 成本分析 | 检测受影响订单，按给定条款计算额外费用/退款/损失，比较方案，说明不确定项 |
| 用户确认 | 重大行程/预订关联更改先预览，再由用户批准；批准仅更新 PlanB 本地行程 |
| 展示 | 地图、日程时间轴、原新行程差异、订单影响、费用明细、理由、确认/拒绝 |
| 实时数据 | **不是第一版要求**：无需实时价格、实时天气、实时航班/酒店 API |
| 实际订票 | **不做**预订网站跳转、自动改签、取消、付款，也不要求接入真实账号 |
| 评测 | 静态、可复现的测试案例；Baseline + Proposed Method + 可选消融实验 |
| 个人项目 | MVP 范围有限，优先一个城市（东京）、2–3 日行程、几类典型中断 |

**特别注意：** 用户曾考虑实时公开政策和当日价格，**后来明确改为 Demo/评测只需用户提供特定订单与价格/规则数据，不需要实时抓取**。这是更新后的最终决定。

---

## 3. 功能范围与优先级

### 3.1 P0 — 课程项目核心必须完成

1. 创建 Trip，输入目的地/日期/偏好/预算/人数，生成初始可结构化日程。
2. 浏览按天展示的活动列表与地图；可手动添加、修改、删除、锁定活动。
3. 用户通过自然语言提出编辑请求；可手动选择模拟突发事件。
4. 维护结构化 Trip/Activity/Place/Booking/Policy/TravelTime 数据。
5. 动态事件影响分析：找出受影响活动、时间范围和相关订单。
6. 局部候选修复：Keep、Shift、Replace、Reorder、Remove、Extend；固定锁定活动。
7. 验证硬约束并返回清晰的不可行/待确认原因。
8. Booking Dependency Analysis：识别受影响的酒店、航班、门票/预约。
9. 用静态订单政策和替代报价**确定性计算**已知变更费用和不确定项。
10. 显示原计划 vs 候选方案 Diff、成本明细、确认/拒绝；未批准不提交。
11. 用统一输入跑至少一个普通 LLM Baseline 与 PlanB 的自动化对照实验。
12. 保存确认后的行程版本和本地变更历史。

### 3.2 P1 — 优先扩展（基础稳定后）

- 同时生成和比较 2–3 个可行候选方案（少改动 / 少支出 / 少交通时间）。
- 从用户粘贴的订单**文本**提取结构化条款，提取后要求用户检查；截图/OCR 非必要。
- 增加行程拖拽操作与更直观的地图路线可视化。
- 更深入的 Ablation Study（去除局部修复 / 验证 / 依赖分析）。
- 使用受控测试输入的用户偏好评分和变更解释质量评估。

### 3.3 P2 — 非当前版本范围

- 实时天气与交通监测；真实机票、酒店、景点库存与价格接口。
- 在线订单管理入口、跳转交易、自动改签、取消和付款。
- 用户真实账户绑定、保存支付信息/护照信息。
- 跨国复杂多城旅行优化、通用网页 Computer-Use、全天候自治。
- 多 Agent 团队、在线爬虫、大模型训练或微调。

**重要：** 不应将 P1/P2 当作必须完成，避免压垮个人开发周期。

---

## 4. 典型用户故事与核心操作流程

### Story A — 初次规划

用户："我想在东京玩三天，预算 3000 元，喜欢摄影、自然景点，不想行程太赶。"

系统：从本地地点/时段/交通数据生成初始计划 → 硬约束校验 → 展示每天时间轴与地图 → 用户确认创建。

### Story B — 用户手动修改

用户在时间轴中把某景点从上午拖到下午，或添加新的活动。系统自动检查是否冲突；若影响相关预约或已锁定内容，进入预览和影响分析，而不是直接静默覆盖。

### Story C — 景点关闭/天气变化

用户点击模拟事件 "明天下午暴雨" 或 "上野某景点关闭"。PlanB 识别受影响户外活动，仅修复有冲突的时间段，提供室内备选，尽可能保留已预订晚餐和其他有效安排。

### Story D — 延长旅期并估算费用（首选课堂 Demo）

原行程：东京 12 月 10–12 日，12 月 12 日返程；用户提供已确认订单及静态退改条件。

用户："我想在东京多待一天，12 月 13 日再回来，之前安排好的景点尽量不要改。"

系统应：

1. 将该请求解析为 `trip_extension`，目标结束日为 12 月 13 日；
2. 检测返程航班日期与酒店退房日受影响；
3. 优先保留旧景点与不受影响预约；
4. 根据用户提供的续住价格、机票改签费与票价差计算额外费用；
5. 输出新方案、费用组成、必要的外部人工操作提醒；
6. 经用户确认后**只更新系统内部行程及待处理状态**，不得宣称已经实际完成改签/续住。

**模拟示例（绝非实时价）：**

- 原返程机票 12 月 12 日，已购价格 ¥1,800；可改至 13 日，改签手续费 ¥200，票价差 ¥350；
- 酒店原入住 12 月 10–12 日，新增 12 日晚住宿的参考价格 ¥600，假设可续住；
- 原 12 月 11 日景点预约不受影响；
- **增量费用 = ¥200 + ¥350 + ¥600 = ¥1,150**，不应把已付的 ¥1,800 再次计入新增支出。

这是教学用静态演示数据；真正的不同订单需要不同的计算规则。

### Story E — 不可行请求

用户要求同时保留两个时间重叠且均被锁定的活动。系统必须返回冲突和可供用户选择的放宽方案，不能伪造“成功重规划”。

### Story F — 费用未知

用户只说“允许改签”，但没有手续费、差价或替代航班报价。系统给出已知费用小计 + “机票费用未知”，不猜数，不把未知当零。

---

## 5. 核心架构与模块责任

```text
React + TypeScript + Vite UI
├── My Trips / Trip Workspace / AI Chat
├── Day Timeline + Map + Booking & Budget
└── Proposal Compare / Approval
             |
             | HTTP / JSON
             v
FastAPI Backend
├── API controllers / Auth? (MVP 无需真实账号)
├── Trip & Itinerary State Manager
├── Agent Orchestrator (LLM + structured tool calls)
│   ├── get_trip_state
│   ├── search_places / get_travel_time
│   ├── analyze_disruption
│   ├── repair_itinerary
│   ├── validate_itinerary
│   ├── analyze_booking_impact
│   ├── estimate_cost
│   └── compare_proposals
├── Constraint Validator (deterministic Python)
├── Plan Repair Engine (bounded heuristic search)
├── Booking Dependency Analyzer
├── Cost Engine (deterministic money arithmetic)
└── Proposal Approval + Revision Control
             |
             v
SQLite + static fixtures + test scenarios
```

### 5.1 LLM 的职责

- 意图识别、自然语言结构化：目的地、时间变化、约束、偏好、事件类型；
- 选择工具和组合工作流；
- 根据已知候选地点生成/解释合理的行程修复候选；
- 将约束或费用分析转为对用户清楚的解释；
- 对缺失的关键事实发起必要的澄清。

### 5.2 确定性代码的职责

- Trip/Activity/Booking 数据读写和修订版本；
- 日期、时区、时长、活动重叠和交通时间计算；
- 预约/开放时间、用户锁定、预算硬约束检查；
- 依赖关系检测和订单受影响判定；
- 退款/改签/续住等增量成本计算、币种一致性与未知字段处理；
- 最终确认时重新验证，并在事务中安全提交。

### 5.3 架构选择理由

- **单一 Agent / Orchestrator + 业务工具**，不必一开始做 Multi-Agent。
- Python + FastAPI / React + TypeScript 是暂定而合理的技术栈；若仓库已有其他成熟实现，应先征询改造成本再选择。
- 初期启发式局部搜索足够；OR-Tools、LangGraph 均为**可选**而非必须依赖。
- 实验输入固定，避免外部 API 返回变化导致无法复现。

---

## 6. 数据模型与字段设计

**总原则：** 日期使用 ISO 8601，跨日期的活动采用带时区的日期时间；旅行时区显式保存（如 `Asia/Tokyo`）。金额不要用浮点数，应存储为 `amount_minor`（最小货币单位，如 CNY 分）、`currency`（ISO 4217）；`null` = 未知，**不同于 0**。所有可选事实携带来源和验证状态。

### 6.1 Trip

| 字段 | 类型/作用 |
|---|---|
| `trip_id` | UUID |
| `destination` | 城市或区域 |
| `start_date`, `end_date` | ISO 日期，需统一是含首尾日期还是退房/离开日期 |
| `timezone` | IANA timezone |
| `party_size` | 人数 |
| `budget` | `{amount_minor, currency, is_hard_limit}` |
| `preferences` | 兴趣、节奏、优先级、每日开始/结束时间 |
| `status` | `draft/active/completed` |
| `revision` | 乐观锁版本号 |

### 6.2 Place

`place_id`, `name`, `category`, `latitude`, `longitude`, `opening_windows`, `suggested_visit_minutes`, `entry_cost`, `data_source`, `verified_status`。

地点时间窗口应当按具体日期/星期建模；当营业时间未知或节假日特殊时显示未知，不假定营业。

### 6.3 Activity

`activity_id`, `trip_id`, `place_id`, `start_at`, `end_at`, `category`, `priority`, `is_locked`, `status`, `estimated_cost`, `notes`, `booking_links[]`。

不应把“优先级高”和“硬锁定”混成同一概念；已锁定活动修改必须由用户明确解除或批准。

### 6.4 Booking 与订单依赖

- `Booking`: `booking_id`, `trip_id`, `booking_type` (`flight/hotel/attraction/transport`), `provider_name`, `service_start/end`, `paid_amount`, `currency`, `booking_status`, `policy_id`, `quote_options[]`, `source`。
- `BookingActivityLink`: `booking_id`, `activity_id`, `relation_type`；避免假设订单只能关联一个活动。
- `BookingPolicy`: `policy_id`, `booking_id`, `change_allowed`, `cancel_allowed`, `free_cancel_deadline`, `change_fee`, `cancellation_fee`, `refund_rule`, `fare_difference`, `conditions`, `unknown_fields`, `source`。
- `AlternativeQuote`: 操作类型、目标服务日期、报价金额、可用性、适用限制、创建时间、是否模拟。

**订单状态建议区分：** `recorded`（在 PlanB 中录入）、`externally_confirmed`（用户声称/输入已预订）、`change_needed`（待用户在供应商处处理）、`user_marked_handled`（用户自己标记已处理）。**内部行程批准不等于外部订单已更改。**

### 6.5 TravelTimeMatrix

`origin_place_id`, `destination_place_id`, `mode`, `travel_minutes`, `travel_cost`, `valid_window`, `source`。不存在记录时为未知，不能默认 0 分钟。

### 6.6 DisruptionEvent

`event_id`, `trip_id`, `event_type`, `affected_time_range`, `affected_place_ids`, `parameters`, `source`, `created_at`。

支持：`weather_change`, `place_closed`, `transport_delay`, `trip_extension`, `trip_shortening`, `reservation_change`, `user_preference_change`。

### 6.7 PlanProposal 与变更历史

`proposal_id`, `trip_id`, `base_revision`, `proposed_activities`, `changes[]`, `validation_result`, `booking_impacts[]`, `cost_estimate`, `status` (`pending/approved/rejected/expired`), `created_at`。

`ChangeHistory`: 变更前后快照/差异、确认事件、相关 Proposal、时间和原因。

### 6.8 ValidationResult

建议结构：

```json
{
  "is_feasible": false,
  "hard_violations": [
    {"rule": "TRAVEL_TIME", "activity_ids": ["a1", "a2"], "message": "两项活动间交通时间不足"}
  ],
  "soft_warnings": [],
  "unknown_constraints": [
    {"rule": "OPENING_HOURS", "place_id": "p3", "message": "缺少该日期营业时间"}
  ],
  "checked_rules": ["TIME_OVERLAP", "TRAVEL_TIME", "LOCKED", "BUDGET"]
}
```

**语义说明：** `is_feasible=true` 只表示**所有已验证硬约束通过**；若 `unknown_constraints` 非空，不得在 UI 宣称“全部现实条件已验证”。也可设计更明确的 `feasibility_status=valid/invalid/unknown` 三态以避免误解。

### 6.9 CostEstimate

```json
{
  "currency": "CNY",
  "known_additional_minor": 115000,
  "estimated_min_minor": 115000,
  "estimated_max_minor": 115000,
  "is_complete": true,
  "components": [
    {"kind": "flight_change_fee", "booking_id": "flight-1", "amount_minor": 20000},
    {"kind": "flight_fare_difference", "booking_id": "flight-1", "amount_minor": 35000},
    {"kind": "hotel_extension", "booking_id": "hotel-1", "amount_minor": 60000}
  ],
  "unknown_components": [],
  "assumptions": ["演示中假设酒店可续住", "价格来自用户输入的静态测试数据"]
}
```

这是**格式示例**；真实字段命名可调整，但必须保留可追溯明细、未知项与假设。

### 6.10 建议的静态 Demo 文件

- `data/places/tokyo_places.json`
- `data/travel_times/tokyo_matrix.json`
- `data/sample_trips/tokyo_3day.json`
- `data/sample_bookings/tokyo_bookings.json`
- `data/disruption_scenarios/*.json`
- `data/README.md`（记录数据是否模拟、来源、许可和边界）

---

## 7. Agent 工具定义与执行状态

### 7.1 建议的工具集合

| Tool | 输入 / 输出原则 | 副作用 |
|---|---|---|
| `get_trip_state` | 获取指定 Trip、约束、预订与 revision | 只读 |
| `search_places` | 从静态 POI 库按日期/类型/兴趣过滤 | 只读 |
| `get_travel_time` | 从矩阵获取时间和费用，缺失显式返回未知 | 只读 |
| `generate_itinerary` | 基于给定候选地点生成初始候选 | 仅候选 |
| `analyze_disruption` | 解析事件并识别活动/订单影响范围 | 只读/分析 |
| `repair_itinerary` | 执行局部修复并返回受限数量候选 | 仅候选 |
| `validate_itinerary` | 运行硬/软约束验证 | 只读 |
| `analyze_booking_impact` | 获取关联订单及变更性质 | 只读 |
| `estimate_cost` | 规则引擎输出费用明细、未知、假设 | 只读 |
| `compare_proposals` | 仅对已知可比较指标排序 | 只读 |

不得给 LLM 一个可绕过审批直接 `commit_trip` 的工具。

### 7.2 核心执行状态

```text
IDLE
 -> UNDERSTANDING_REQUEST
 -> LOADING_CONTEXT
 -> ANALYZING_IMPACT
 -> GENERATING_CANDIDATES
 -> VALIDATING
 -> EVALUATING_COST
 -> WAITING_FOR_APPROVAL
 -> (COMMITTED | REJECTED | EXPIRED)

错误支路：NEEDS_INFORMATION / INFEASIBLE / FAILED
```

状态必须由后端维护，防止 Agent 只靠语言叙述自己的执行进度。

### 7.3 典型重规划调用流程

```text
User intent / UI edit / simulated disruption
   -> Parse request as structured event
   -> Load trip state + base_revision
   -> Analyze affected activities + associated bookings
   -> Keep feasible unaffected activities; freeze locked ones
   -> Generate a bounded set of modifications
   -> Validate hard constraints
   -> Analyze booking impacts
   -> Calculate costs with deterministic rules
   -> Rank feasible proposals, annotate unknowns
   -> Save pending proposal; show diff + reasoning
   -> User approval
   -> Recheck revision and validation in backend transaction
   -> Update local trip + history; never claim external booking changed
```

如果不能满足全部硬约束，输出原因与可让用户选择的放宽项，不应假装完成。

---

## 8. 约束验证设计（Constraint Validator）

### 8.1 硬约束（Hard Constraints）

- 两个不兼容活动不得时间重叠；
- 上一个地点到下一个地点的交通时间必须足够（使用静态矩阵）；
- 已知地点营业时间、门票预约窗口必须满足；
- 用户锁定的活动不得被 Agent 擅自移除或改期；
- 旅行出发/返程日期及已明确固定的时间窗口必须满足；
- 若预算明确是硬上限且费用已知，不得超预算；
- 对导致关联订单变更的操作必须识别并在应用前提示。

### 8.2 软约束（Soft Constraints）

- 尽量保留有效的原活动与顺序；
- 减少交通耗时和改动量；
- 旅行节奏舒适，不要过度拥挤；
- 降低新增费用；
- 满足用户兴趣与优先级。

### 8.3 处理未知条件

不知道某景点开门时间、交通耗时或订单可改签状态，应记录 `unknown`。可以输出带提示的候选方案，但**不能将其作为完全验证方案**。

### 8.4 测试要点

- 同日重叠与跨日活动；
- 不同时区与日期边界；
- 交通时间刚好等于/小于可用间隔；
- 锁定活动冲突；
- 不存在的交通矩阵项；
- 预算等于/超出上限；
- 订单服务时段与 Trip 修改之间的依赖；
- 可行、不可能、信息不足三类结果。

---

## 9. 动态局部重规划算法（Plan Repair Engine）

### 9.1 目标

在**满足硬约束**的情况下，尽量减少对有效原计划的扰动，同时考虑额外费用、交通与偏好。

### 9.2 MVP 算法流程

1. 计算本次请求/事件实际改变的约束（日期、地点可用性、延误区间等）。
2. 建立受影响活动集合和其时间/交通/预订依赖闭包（影响可能向相邻活动传播）。
3. 保留未受影响且仍然可行的活动；冻结 `is_locked=true` 的活动。
4. 对受影响活动生成候选操作：`Keep`, `Shift`, `Replace`, `Reorder`, `Remove`, `Extend`。
5. 限制候选动作、搜索深度和模型调用预算，避免组合爆炸。
6. 执行确定性验证，丢弃违反硬约束的候选。
7. 对每个候选执行 Booking Impact + Cost Estimate。
8. **先满足硬约束，再比较**修改量 → 已知额外费用 → 交通时间 → 偏好满足；用户可以调整软目标权重。
9. 返回排名前 1–3 个候选，附修改 Diff、原因和未知字段。

### 9.3 简化伪代码

```python
def replan(trip, event, places, matrix, bookings, max_candidates=5):
    affected = detect_impacted_activities(trip, event, matrix, bookings)
    candidates = generate_local_edits(trip, event, affected, limit=max_candidates)
    results = []
    for candidate in candidates:
        validation = validate(candidate, trip, places, matrix)
        if validation.has_hard_violations:
            continue
        impacts = analyze_booking_impact(trip, candidate, bookings)
        estimate = estimate_incremental_cost(impacts, bookings)
        results.append((candidate, validation, impacts, estimate))
    return rank_candidates(results)  # 不把未知费用当 0
```

仅为设计示意，不代表已实现，也没有覆盖全部边界情况。

### 9.4 排序的重要约束

- **硬约束必须先过滤**，不能用低成本去抵消硬约束违规。
- 行程保留率只对“原本仍可行/原本可保留”的活动有意义；不能为了保留而保留已经关闭的景点。
- 费用未知的方案不能被自动判定为最便宜。
- 搜索无解时返回明确失败和可调整条件。

---

## 10. 预订关联与费用引擎（Booking Impact & Cost Engine）

### 10.1 预订影响四态

`unaffected`, `change_required`, `potentially_affected`, `unknown`。

按服务日期/活动/订单关联及退改条件判断。不能凭酒店名称推断一定能延住，或凭航司名称推断特定票价一定允许退改。

### 10.2 示例计算场景

**航班改签（手续费和票价差明确）**

```text
IncrementalCost = ChangeFee + FareDifference
```

若差价为负数，是否可返还取决于订单规则；绝不能自动按通用假设退款。

**航班取消后重购**

```text
IncrementalCost = NewTicketPayment + ApplicableCancellationFee
                  - ConfirmedRefund - OtherCreditedAmounts
```

实际必须遵守该订单的费用定义和退款是否已包含手续费，避免重复扣/加。

**酒店延住**

```text
IncrementalCost = AdditionalNightQuotedPrice + ApplicableExtraFees
```

必须给定延住报价/可用性；未知则标记未知。

**景点取消/改期**

使用订单已付金额、可退款、手续费和替代票价计算*相对于原计划的增量现金支出/损失*；不要把已支付金额重复算作新增成本。

### 10.3 成本的两个口径（需要在 UI 明确）

- **额外需支付现金（Additional Out-of-Pocket）**：改签后需额外付的钱 + 新增项目收费 − 可确认退回或抵扣的金额。
- **经济损失 / 总成本变化（Net Economic Impact）**：可能进一步反映不可退的原有支出、已购买服务损失；注意与现金口径不同，避免双重计算。

MVP 主要采用**相对于原计划的增量支出**，显示每个组成项；如果规则不足，显示已知小计及缺失项，不能声称完整准确总额。

### 10.4 金额处理规则

- 同币种采用整数分/cent 运算；
- 不混算不同币种；没有明确汇率时分币种展示；
- 每个费用组成项都追溯到订单/规则/备选报价；
- `null` 与 `0` 的语义区分；
- 可确定总额则返回数值；可确定区间则返回区间；关键值未知时总额 `unknown`；
- 不将 LLM 输出的“估计 ¥xxx”直接当作事实；
- 不宣称用户确认方案 = 外部订单已改签或续住。

---

## 11. 用户审批、版本控制与本地一致性

所有重要变更采用：**Preview → Approve → Commit**。

1. Agent 建立 `PlanProposal(status=pending)` 和 `base_revision`；
2. 前端显示新增/删除/移动/保留、潜在订单影响、费用、假设；
3. 用户点确认或拒绝；
4. 后端验证 `base_revision == current_trip.revision`，并再次检查必要约束；
5. 在数据库事务中写入新的本地行程与 History，`revision += 1`；
6. Proposal 状态变为 `approved`；
7. 真实机票/酒店订单状态**不会因此自动变更**。

若用户预览后又手动编辑了行程，则旧 Proposal 失效或要求重新验证，不能覆盖新编辑。

无论是**手动编辑**还是**AI 发起修改**，都应经过统一约束检查；若涉及锁定活动/预订，则统一走候选方案与确认流程。不能让普通 `PATCH` 绕开业务保护。

---

## 12. 前端 UX 与页面

### 12.1 My Trips

查看/创建旅行，输入目的地、时间、偏好、人数、预算。

### 12.2 Trip Workspace（核心）

- **Left:** AI Copilot 聊天和事件触发；
- **Center:** 地图地点、路线/地点之间关系；
- **Right:** 按日时间轴，允许用户编辑/锁定/移动活动；
- 顶部显示旅行名称、日期、预算及可用操作。

### 12.3 Booking & Budget

用户添加特定的机票、酒店、景点预约、退改政策、替代报价；查看订单与活动关联及已知/未知费用。

### 12.4 Plan Comparison / Booking Impact Center

- 旧计划与新计划并排/差异标色；
- 显示保留/改变/删除/新增活动；
- 显示为何调整、已锁定项目是否保留；
- 展示受影响订单、变更类型、模拟费用明细、未知事项；
- 显示是否满足已知硬约束，以及尚未验证的条件；
- `Approve` / `Reject` 明确控制，本地应用前需要用户确认。

MVP 优先完成可用、清楚的界面；精美动画、多端全面适配、复杂 UI 组件不是课程核心。

---

## 13. 暂定后端 REST API

| Method | Endpoint | 说明 |
|---|---|---|
| `POST` | `/api/trips` | 创建行程 |
| `GET` | `/api/trips/{id}` | 获取行程和 revision |
| `PATCH` | `/api/trips/{id}` | 修改基础信息；涉及预订/冲突时进入预览流程 |
| `GET` | `/api/trips/{id}/activities` | 查询活动 |
| `POST` | `/api/trips/{id}/activities` | 添加活动（统一验证） |
| `PATCH` | `/api/activities/{id}` | 编辑活动（不能绕过确认） |
| `DELETE` | `/api/activities/{id}` | 删除活动（不能绕过锁定和预订限制） |
| `POST` | `/api/trips/{id}/bookings` | 录入测试预订 |
| `POST` | `/api/trips/{id}/plan` | 生成初始候选计划 |
| `POST` | `/api/trips/{id}/replan` | 创建重规划 Proposal |
| `GET` | `/api/proposals/{id}` | 获取候选详情 |
| `POST` | `/api/proposals/{id}/approve` | 用户批准、原子写入 |
| `POST` | `/api/proposals/{id}/reject` | 拒绝候选 |
| `GET` | `/api/trips/{id}/history` | 查看历史 |

补充设计：返回统一错误结构与明确错误码；审批接口需要防止重复提交（幂等/状态检查）。具体路径可以按仓库现状调整，但审批边界不得丢失。

---

## 14. 可复现评测与 Baseline 设计

### 14.1 评测目的

**不只是演示有 AI 聊天，而是验证 PlanB 的系统改进是否相对简单 LLM 方案更可靠。**

### 14.2 三种对照方法

1. **Baseline A — Direct LLM:** 给模型原行程、事件、订单及相关已知数据，直接让模型输出修改后的行程与费用。
2. **Baseline B — Structured/Constraint-Prompted LLM:** 给同样输入，但使用明确的约束提示、结构化输出格式；不增加 PlanB 的独立验证和费用引擎。
3. **PlanB — Proposed:** LLM Agent + 结构化状态 + 局部修复 + 硬约束验证 + 订单关联 + 确定性费用计算。

公平原则：相同模型版本、温度、数据、任务输入与评测标准；允许记录不同调用次数和成本，不能偷偷给 PlanB 更多事实或只为其配置简单案例。

### 14.3 测试集

计划建立约 **40 个静态场景**（具体数量可按时间缩放）：

| 类别 | 建议数量 | 检验内容 |
|---|---:|---|
| 天气突变 | 10 | 户外活动与替换安排 |
| 交通延误 | 10 | 时间窗口、连锁延误 |
| 延长/缩短旅行日期 | 10 | 酒店和机票依赖、费用 |
| 预约取消/改期 | 10 | 票务规则、安排冲突、费用 |

每个场景包含：原计划、静态地点/时间矩阵、预订和政策、用户偏好、事件、正确影响项、可验证费用、硬约束判定。覆盖正常、无解和信息不足三类。

**先做 6–10 个 Pilot 场景，跑通评测流程后扩展。** 开发调试集与最终保留的评估集分开，避免针对最终测试集过拟合。

### 14.4 主要指标

| 指标 | 计算/判定含义 | 方向 |
|---|---|---|
| `Feasibility Rate` | 产出行程满足所有可验证硬约束的比例，单独报告未知条件 | ↑ |
| `Constraint Violations` | 每个方案硬性违规数量/类型 | ↓ |
| `Plan Preservation Rate` | 原计划中**仍可行且用户希望保留**的活动保留比例 | ↑ |
| `Booking Impact Precision/Recall/F1` | 与 Ground Truth 对比，是否识别正确受影响订单 | ↑ |
| `Cost Exact Match / MAE` | 对有充分规则的案例计算费用准确率/平均绝对误差 | 更准 |
| `Unknown Cost Handling` | 无法核算时能否正确识别缺失，而非编造金额 | ↑ |
| `Latency` | 单次重规划端到端耗时 | ↓ |
| `Token Consumption / Calls` | 每例模型 Token 与调用次数 | ↓ |

对完全没有可行替代方案的情境，正确报告无法满足，也应算作合理系统行为，不应一律判失败。

### 14.5 消融实验（有时间后完成）

- Full PlanB；
- Without Local Repair；
- Without Constraint Validator；
- Without Booking Dependency Analysis（或只用 LLM 估价）。

注意消融必须明确怎样替换被移除模块，保持其余设置不变，才有可解释结果。

### 14.6 报告要求（建议结构，正式标准未公布）

Introduction / Problem / Related Work / System Design / Implementation / Baselines / Experiments / Results / Ablation / Failure Analysis / Limitations / Demo。

结果需实际跑出表格图表，包括失败案例、增益与额外调用成本。不得伪造实验数值。

---

## 15. 工程质量、隐私和安全边界

- 测试订单尽量用**模拟信息**，不要提交真实姓名、身份证、护照、订单号、付款凭据到公开仓库。
- 若导入真实订单文本，前端提示用户去除个人敏感字段；保留最少必要业务字段。
- `.env` 存放 API key，加入 `.gitignore`；提供 `.env.example`，不提交真实密钥。
- 所有 LLM 输出通过 Pydantic 校验；工具参数做白名单与边界校验。
- LLM 不可以执行任意 shell/系统命令、直接操作支付或预订网站；Agent 的工具是定义明确的受控函数。
- 不允许假装接入实时信息；静态数据注明 `demo`/`user_provided`/`fixture`。
- 若使用开源地图数据或组件，核对许可、署名要求；无在线底图也应可显示日程与基础地点信息。
- 数据库写入和用户确认需要事务与版本检查；测试不应修改生产示例数据。
- 实验保持配置、种子（如适用）、模型版本、时间、输入与输出存档，便于重复分析。

---

## 16. 建议项目仓库结构

```text
planb/
├── PROJECT_CONTEXT.md              # 本文
├── README.md                       # 安装、启动、运行 Demo、项目说明
├── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── types/
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── agents/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── itinerary/
│   │   │   ├── replanning/
│   │   │   ├── validation/
│   │   │   ├── bookings/
│   │   │   └── cost/
│   │   └── database/
│   └── requirements.txt / pyproject.toml
├── data/
│   ├── places/
│   ├── travel_times/
│   ├── sample_trips/
│   ├── sample_bookings/
│   └── disruption_scenarios/
├── evaluation/
│   ├── baselines/
│   ├── metrics/
│   ├── scenarios/
│   ├── scripts/
│   └── results/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── agent/
└── docs/
    ├── architecture.md
    ├── evaluation_protocol.md
    └── decisions.md
```

**上面是建议而非强制目录树。** 已有仓库应先检查后调整，不要因模板而大规模重排代码。

---

## 17. 推荐开发顺序与里程碑

### Milestone 0 — 盘点现有仓库

- 查看项目目录、文件、Git 状态、已有功能与测试；
- 比较实际代码与本文需求差异；
- 给出 MVP 分阶段任务清单与技术风险；
- 如无仓库则创建最小骨架，避免一次生成大量未验证代码。

### Milestone 1 — 数据与业务基础

- 定义 Pydantic/SQLAlchemy 的 Trip、Place、Activity、Booking、Policy、Proposal 模型；
- 准备东京示例数据、交通矩阵与订单；
- 实现 Trip CRUD、版本号和事务；
- 对金额、时间、未知条款做单元测试。

### Milestone 2 — 确定性核心引擎

- `ConstraintValidator`：重叠、交通、营业时间、锁定、预算；
- `BookingDependencyAnalyzer`：受影响订单与原因；
- `CostEngine`：改签费+差额、酒店续住、取消退款、未知金额；
- 单元测试先覆盖关键边界，不依赖 LLM。

### Milestone 3 — 动态重规划 MVP

- 事件类型解析的数据接口；
- 局部修复与候选生成；
- validator 过滤、费用估算、候选排序；
- Proposal Preview → Approve → Commit + 修改历史。

### Milestone 4 — Agent 连接

- 添加明确的 Tool Calling，使用结构化输出与异常重试上限；
- 完成“用自然语言延长旅程一天，并估算机票/酒店影响”的端到端功能；
- 模型不可用时确定性流程仍能单独测试。

### Milestone 5 — 前端 Demo

- 创建旅行、日程编辑与锁定、静态地图、预订输入；
- 突发事件模拟按钮、方案对比、费用卡片、用户确认。

### Milestone 6 — Baselines / 评测 / 报告

- 静态测试集、统一输出格式、统一 Validator；
- A/B/PlanB 实验、误差分析、图表与 Demo 脚本；
- 视时间进行消融实验和界面提升。

---

## 18. MVP 验收标准（可直接转成测试清单）

- [ ] 用户可以输入东京 3 日游条件并生成结构化初始行程。
- [ ] 可以添加/修改/删除/锁定活动，界面和数据库一致。
- [ ] 行程冲突（重叠、交通不足）能被检测并明确提示。
- [ ] 至少三类突发事件可以在静态测试数据下重规划。
- [ ] 重要预约/锁定活动不会被 Agent 未经许可删除或改期。
- [ ] 延长旅行一天能够识别返程机票和酒店的影响。
- [ ] 给定模拟费率，改签 ¥200 + 差额 ¥350 + 续住 ¥600 准确得到**新增 ¥1,150**。
- [ ] 缺失费用时显示“未知/待补充”，不会虚构金额或当作 0。
- [ ] 原计划与候选行程差异、成本及原因可以直观查看。
- [ ] 只有点击批准后才更新本地正式行程；拒绝或旧 revision 不更新。
- [ ] 点击确认后不宣称真实机票、酒店或景点预约已经变更。
- [ ] 至少完成一个 Baseline 对照脚本和统一评估，并输出真实结果。
- [ ] 有 README 安装运行步骤、最小示例数据、核心单元测试。

---

## 19. 待确定问题与开发假设

这些不是用户已确认的强制需求。可按最小可用的默认方案推进，重要设计变化需说明。

1. **最终官方作业要求：** 具体 rubric、时间、报告长度、是否要求本地运行、是否必须展示训练，尚未确认。
2. **目标模型与费用：** 暂未选定具体 LLM 提供商或模型；优先支持可配置的模型适配层和 mock 测试。
3. **地点数据范围：** MVP 假设东京一个城市，少量经过核对或明确模拟的 POI；数据量与地图许可后续确定。
4. **预算口径与多币种：** 第一版可使用单一 CNY 演示；不凭空换算外币。
5. **新增报价与可用性：** 用户输入/静态 Fixture 中明确给出；否则标记未知。
6. **路线目标：** 首先支持静态旅行时间矩阵和步行/公共交通粗粒度模式；不保证实时交通。
7. **可用性与预约验证：** 静态 Fixtures 可以标注场景规则，不能推断真实世界可预订状态。
8. **活动自由编辑方式：** 先表单和时间轴点击操作，拖拽是可选增强。
9. **结果展示与调试：** 保留 Agent 决策摘要、工具输入输出、验证结果，不泄露密钥或敏感资料。
10. **地图：** 即使地图底图不可用，日程和评估应可以独立完成。

---

## 20. 后续维护规则

- 每次明确的新产品决定，更新本文的 **“已确定的产品决策”** 和 `docs/decisions.md`；
- 版本号可以顺序增加 v1.1、v1.2 等；
- 系统最终实现、实验指标与结果都需要回写 README / 报告，保持“设计意图”和“实测能力”区分；
- 最重要的成功标准是：**一个人能够开发、理解、演示、测试并解释 PlanB 为什么比简单 LLM 行程修改更可靠，且知道其边界。**

---

**End of PlanB Codex Project Context v1.0**
