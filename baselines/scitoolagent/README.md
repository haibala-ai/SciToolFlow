# SciToolAgent baseline（SciToolFlow 适配版）

所有 planner/executor/summarizer 共用 `--backend api|vllm|local` 与 `--model`。生成 API 与检索 embedding 的配置独立；本地 actor 仍需与工具索引同源的 embedding 服务。可选 LLM judge 同样支持上述后端，可以与 actor 选用不同模型。统一部署和命令见[交付 README](../../README.md)。

参照 [HICAI-ZJU/SciToolAgent](https://github.com/HICAI-ZJU/SciToolAgent) 的提交 `ac1cf19fcef84e69f149db6da424afe4e9b2f11f`。来源文件、哈希和改动见 [upstream.json](upstream.json)，MIT 授权见 [LICENSE.upstream](LICENSE.upstream)。本目录实现 KG 检索、预先规划、逐工具参数提取、总结及至多三轮重规划，不是 ReAct 改名，也不声称逐字复现原论文结果。

```bash
conda activate SciTool-Unified
cd SciToolFlow
python baselines/scitoolagent/run.py --tasks FLOW-0285 --output results/scitoolagent_demo/predictions.json
# 等价的公共入口
python cli.py run --baseline scitoolagent --tasks FLOW-0285 --output results/scitoolagent_other/predictions.json
python cli.py score --tasks FLOW-0285 --predictions results/scitoolagent_demo/predictions.json --output results/scitoolagent_demo/scores.json
```

## 算法与代码

- `retrieval.py`：对问题做同源 API embedding，以功能向量找 5 个语义种子；按输入/输出/功能关系展开至深度 3，过滤只共享输入或输出的同类路径；将候选功能与种子上下文一起编码、按相似度乘积累加权重，最多保留 10 个工具。
- `runtime.py`：planner 先输出有序工具链；executor 针对链中的每次工具出现生成参数并执行，成功后推进；summarizer 根据真实输出回答，未完成可重规划。相同工具处理多个输入时保留重复链条。
- `system_prompt.md`：三个角色的公共协议；运行时补入当前角色说明。工具候选来自公开图谱，执行契约来自当前唯一 catalog。
- `config.json`：检索规模、三轮规划和规划阶段的单独轮数上限；全局预算直接使用 ReAct 的公共默认配置和 CLI。

原版采用 LlamaIndex 图谱对象、多次 embedding 请求、自由文本 Plan Chain/Input/IsCompleted/FinalAnswer，以及无限工具重试。本适配版使用现有 JSON 图谱和向量，以批量/缓存 API 减少重复编码，用统一 JSON 格式、隔离 worker、超时与预算替换这些基础设施。核心阶段顺序和上下文检索加权方法保留；图谱探索、候选数量和重试均有界。重规划会看到已经得到的真实结果。

## 与 ReAct 对齐的 harness

两者共用公开题目和附件、模型客户端及采样设置、答案格式模板和错误反馈、工具执行器、科学调用预算、时间/轮数限制、resume 指纹，以及独立评分器。所有 planner/executor/summarizer 请求都计入模型轮数和 tokens，不能只计执行阶段。

SciToolAgent 使用 `baselines/react/runtime.py` 中的有界执行循环来实现每个角色会话；它的顶层策略由本目录的图谱检索与计划链控制。executor 仅可调用当前计划工具，成功后立即交回控制；planner/summarizer 不可额外执行科学工具。

2026-10-18 全量测试前进一步落实了角色权限：三个角色都不能自行调用 DescribeTools；执行前由 harness 自动读取并提供契约，仍计入 discovery 成本。planner/summarizer 的协议不开放 actions；executor 的 actions 只开放当前计划工具。普通 ReAct 的按需 DescribeTools 行为保持原样。planner 的 `answer_schema` 是计划结构，另行提供 `task_answer_schema` 表达最终任务目标，二者在提示中明确区分。

每次 executor 交接均携带完整 `ordered_plan`、从 1 开始的 `plan_position` 和历史科学调用的参数/输出摘要；可以用 inspect 读取未截断的参数或结果。这样同一工具处理不同实体时不会丢失计划位置。规划阶段单独耗尽八轮时记录 `PlannerDecisionBudget`，与全局 `DecisionBudget` 区分。

共享 harness 当前还包含连续 10 个同工具同参决策步终止，以及答案格式错误后的公开 schema 结构约束。连续计数跨 executor 会话保留，其他角色决策会打断计数；RepeatedToolLoop 不会触发重规划。max_consecutive_identical_tool_steps 取跨阶段峰值，answer_schema_guard_requests 按实际请求累加。格式约束仍允许全部合法决策，不填答案；详情见 [ReAct 协议](../react/README.md)。

每题一个 `trajectory.json`，`steps` 每个响应一条，带 `phase`/`cycle`；`phases` 保存角色初始上下文，`retrievals` 保存检索依据，`preparations` 保存自动契约读取。没有逐工具子轨迹文件。自动读取的 DescribeTools 计入 discovery，不计科学路径；同一工具契约复用。跨阶段观察 ID 连续，允许引用真实的先前输出。

两者的工具发现策略有意不同：ReAct 初始看全部工具名、按需 DescribeTools；SciToolAgent 的 planner 看检索出的图谱候选，executor 自动取得当前工具的契约。这是 baseline 算法差异，时间、embedding API 和契约读取成本分别记录。

## 运行依赖与限制

复用当前四个 conda 环境，无新增环境。查询及上下文 embedding 使用当前索引声明的同一提供商、`text-embedding-3-large`、3072 维和 L2 归一化。读取 `.local/credentials/services.env` 中已有的 embedding 配置，缓存放在 `.local/cache/scitoolagent_embeddings/`。缺少授权或模型/提供商不匹配时明确失败，不使用另一种向量或词法检索伪装成同源 embedding。没有重新计算 546 个工具功能向量。

并发缓存写入改为每个写入者使用独立临时文件后原子替换，避免相同上下文在两个任务中同时编码时冲突。embedding 的网络异常或 HTTP 408/429/500/502/503/504 最多尝试三次，间隔 1、2 秒，受本题总超时约束；401 等授权错误不重试。实际请求与重试次数分别记录，不把失败请求计作成功编码。

2026-10-18 按用户要求移除了 SciToolAgent 额外的 `safety_gate` 参数、输入/输出包装检查及其专有 blocked 返回。现在与 ReAct 直接使用同一工具执行器；执行器原有的参数校验、范围限制、资源检查和失败反馈继续生效。检索不再返回 `requires_security_check` 或 needs/does not need 注释，原始图谱中的历史注释保留存档，不作为 baseline 的额外执行门槛。功能向量未变化，无需重新编码。

首次全量运行已按用户要求暂停，原有 40 条预测及轨迹保留；旧运行对应移除前的源码指纹，不可直接续跑到修改后的代码。当前启动的是独立的 ReAct 500 题全量运行，详见[切换记录](../../results/reports/react_restart_20261018/README.md)。此前的[全量检查报告](../../results/reports/scitoolagent_full_review_20261018/README.md)描述当时的检查器配置，不代表当前机制。

评分方式和 ReAct 相同，提交答案不等于正确。模型原生 thinking 默认关闭；显式 think 及所有角色的模型费用计入统一预算。完整验收和实际轨迹见 [本轮报告](../../results/reports/scitoolagent_baseline_20261017/README.md)。

## 2026-10-18 对齐

继续共用 ReAct 的公开协议/答案格式约束、输入错误 schema 反馈和执行诊断；默认累计失败禁用阈值为 0，连续同参 10 步规则保留。统一评分使用当前任务版本、数学表示等价核验和显式证据条件化；DescribeTools 仍排除于科学路径。工具图、检索功能描述及向量未改变，不需要重建 embedding。新旧任务/代码指纹禁止混合续跑。
