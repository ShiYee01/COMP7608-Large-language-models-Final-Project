# 中英术语对照（Glossary）

本项目文档中常见的英文术语及其中文说法，方便对照阅读英文原文，也方便用中文讲解项目。

## LLM 与模型

| 英文 | 中文 | 说明 |
|---|---|---|
| Large Language Model (LLM) | 大语言模型 | |
| open-weights model | 开源权重模型 | 模型参数公开，可以自己下载运行 |
| parameters (3B, 550B) | 参数量（30 亿、5500 亿） | B = billion，十亿 |
| Mixture of Experts (MoE) | 混合专家模型 | 每次只激活一部分参数，例如“550B 总参数、55B 激活” |
| active parameters | 激活参数 | |
| quantization (Q4_K_M) | 量化 | 用更少的比特存储参数，模型更小、更快，但精度略降 |
| reasoning model | 推理型模型 | 回答前会先生成隐藏的“思考”内容 |
| reasoning tokens | 推理 token | |
| token | token / 词元 | 模型处理文本的基本单位 |
| prompt | 提示词 | |
| temperature | 温度 | 控制随机性；0 表示尽量确定 |
| context window (n_ctx) | 上下文窗口 | 模型一次能读的最大 token 数 |
| inference | 推理（运行模型） | 注意与“推理型模型”的“推理”区分 |
| rate limit | 限流 / 速率限制 | |
| free tier | 免费层 / 免费额度 | |
| quota | 额度 | |
| API key | API 密钥 | |
| endpoint | 接口地址 | |
| OpenAI-compatible API | OpenAI 兼容接口 | |
| tool calling | 工具调用 | |
| orchestrator | 编排器 | |
| state machine | 状态机 | |
| mock mode | 模拟模式 | 不调用真实模型 |
| cache | 缓存 | |
| hallucination | 幻觉 | 模型编造不存在的信息 |

## 项目核心概念

| 英文 | 中文 | 说明 |
|---|---|---|
| travel copilot | 旅行副驾驶 / 旅行助手 | |
| itinerary | 行程 | |
| activity | 活动 | 行程中的一项安排 |
| replanning | 重新规划 | |
| disruption event | 变化事件 / 干扰事件 | 下雨、关闭、延误等 |
| weather change | 天气变化 | |
| place closed | 地点关闭 | |
| transport delay | 交通延误 | |
| trip extension / shortening | 延长 / 缩短行程 | |
| reservation change | 预约变更 | |
| hard constraint | 硬约束 | 必须满足的条件 |
| soft constraint | 软约束 | 尽量满足的偏好 |
| constraint validator | 约束校验器 | |
| deterministic | 确定性的 | 同样的输入永远得到同样的输出 |
| local repair | 局部修复 | 只改受影响的部分 |
| beam search | 束搜索 | 每一步只保留最好的若干个候选 |
| shift / cascade shift | 平移 / 连锁平移 | |
| replace / remove | 替换 / 删除 | |
| locked activity | 锁定的活动 | 用户不允许改动 |
| opening hours | 营业时间 | |
| travel time matrix | 交通时间矩阵 | |
| booking | 订单 / 预订 | |
| booking policy | 退改规则 | |
| change fee | 改签费 | |
| fare difference | 票价差 | |
| refund | 退款 | |
| provider-initiated | 商家发起的 | 例如场馆自己关闭 |
| early checkout | 提前退房 | |
| forfeited loss | 放弃的损失 / 作废损失 | 不可退的钱，不算新增现金支出 |
| incremental cost | 增量费用 | |
| out-of-pocket | 实际掏出的现金 | |
| unknown ≠ 0 | 未知不等于零 | 本项目的核心原则之一 |
| proposal | 方案 | |
| preview → approve → commit | 预览 → 批准 → 提交 | |
| revision | 版本号 | |
| infeasible | 无解 / 不可行 | |
| relaxation option | 放宽选项 | 例如解除某个锁定 |

## 评测

| 英文 | 中文 | 说明 |
|---|---|---|
| baseline | 基线 | 用来对比的方法 |
| direct LLM | 直接问 LLM | 本项目的基线 A（`direct`） |
| constraint-prompted LLM | 加约束提示的 LLM | 本项目的基线 B（`structured`） |
| gold event | 标准事件 / 正确事件 | 人工给出的正确解析结果（`planb_gold`） |
| ground truth | 标准答案 | |
| scenario | 场景 | |
| pilot set | 试点集 | 小规模的开发用数据 |
| held-out set | 留出集 | 开发时不看、只用于最终测试 |
| development set | 开发集 | |
| task success | 任务成功率 | `task_success` |
| feasibility rate | 可行率 | `feasibility_rate` |
| hard violations | 硬约束违规数 | `avg_hard_violations` |
| plan preservation | 行程保留率 | `plan_preservation`：不该改的活动有没有保持不变 |
| precision / recall / F1 | 精确率 / 召回率 / F1 | `booking_f1`：受影响订单找得准不准、全不全 |
| exact match | 完全正确 | `cost_exact_match` |
| status accuracy | 状态准确率 | `status_accuracy` |
| infeasible detected | 无解识别 | `infeasible_detected`（严格：必须明确回答“无解”） |
| unsafe plan refused | 拒绝不安全方案 | `unsafe_plan_refused`（宽松：回答“无解”或“需要更多信息”都算） |
| unknown cost handled | 未知费用处理 | `unknown_cost_handled` |
| latency | 延迟 | |
| ablation study | 消融实验 | 去掉某个模块，看效果变化 |
| statistically significant | 统计显著 | |
| threats to validity | 效度威胁 | 可能让结论不成立的因素 |
| normalisation | 归一化 | |
| artefact | 假象 / 人为因素 | 由评测方式造成、并非真实能力的结果 |

## Presentation 常用表达

| 英文 | 中文 |
|---|---|
| research question | 研究问题 |
| proposed method | 提出的方法 |
| architecture | 架构 |
| preliminary results | 初步结果 |
| limitations | 局限 |
| future work | 后续工作 |
| live demo | 现场演示 |
| Q&A | 答疑 / 问答环节 |
| "The LLM understands and explains; Python checks and calculates; the user decides." | “LLM 负责理解和解释；Python 负责检查和计算；用户负责做决定。” |
