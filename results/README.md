# 实验输出

每个实验使用独立目录，包含以下文件：

| 文件／目录 | 内容 |
| --- | --- |
| predictions.json | 按任务保存的提交答案、完成状态及轨迹位置 |
| task_metrics.json | 逐题运行时间、工具调用数、输入／输出 token 用量；随预测检查点自动更新 |
| experiment.json | 实验流水线保存的题库、模型与阶段状态；CLI 直接运行时设置和指纹保存在 predictions.json |
| progress.json | 批次进度，包含失败记录和活动任务 |
| trajectories/ | 每次任务执行的完整轨迹 |
| trajectories/<任务ID>-<run_id>/analysis/ | 按需离线导出的 SciMas 案例报告和逐步 JSON，运行中不自动生成 |
| tool_artifacts/ | 本次执行生成的工具输出文件 |
| scores.json | 总体指标与逐题判定；评分输出文件名可自定义 |
| scores_review_requests.json | 与评分文件配套的待审方法／证据记录 |

`--dataset full|mini` 统一选择查询、运行与评分题库；题库名称进入预测、轨迹和续跑指纹。`--output results/<experiment>/predictions.json` 指定实验位置。原始轨迹与预测是评分证据，不要只保留汇总分数。续跑使用 `--resume`，要求代码、任务、工具及模型设置的指纹一致；修改后创建新目录。

## 逐题运行成本

`cli.py run` 自动记录，无需额外参数。三种 baseline、API／vLLM／本地模型使用相同字段。每题的预测和 `trajectory.json` 均有 `metrics` 对象；`task_metrics.json` 将当前预测中的统计整理为 `tasks` 数组，便于直接分析。

| 字段 | 含义 |
| --- | --- |
| `runtime_seconds` | 墙钟时间减去通信故障区间中未被实际并行工作覆盖的部分；正常成功请求的响应时间、工具执行、科学纠错及日志计时。API 故障中止的尝试为 `null` |
| `wall_runtime_seconds` | 本次尝试的完整墙钟秒数；并行工具耗时不相加，不含批次排队、模型启动和离线评分 |
| `communication_fault_seconds` | 失败通信请求及失败建连／退避的区间并集，裁剪到本次墙钟范围 |
| `communication_overlap_seconds` | 故障期间仍有真实工具或正常模型响应工作的重叠时间，保留计时 |
| `communication_wait_seconds` | 故障区间扣除有效并行工作覆盖后的等待，仅此部分从墙钟时间扣除 |
| `active_runtime_seconds` | 墙钟时间减去通信等待；即使 API 故障中止也保留已执行部分的诊断耗时 |
| `runtime_reportable` | 是否可作为本次尝试的运行时间样本；基础设施失败中止时为 `false`，速度比较还需筛选完成任务 |
| `tool_calls` | 实际派发的工具调用总次数，含失败、重试和 `DescribeTools`，同一工具多次调用分别计数 |
| `scientific_tool_calls` / `discovery_tool_calls` | 除 `DescribeTools` 外的调用次数／`DescribeTools` 调用次数，二者之和为总调用数 |
| `input_tokens` | 本题全部生成请求的输入 token 总量，对应服务端 `prompt_tokens` |
| `output_tokens` | 本题全部生成请求的输出 token 总量，对应服务端 `completion_tokens` |
| `total_tokens` | 输入与输出之和，仅在两项均完整时给出 |
| `model_requests` | 共享生成 ledger 中的请求次数，包含各角色、协议修正和重规划 |
| `token_usage_complete` | 是否取得每个生成请求完整的输入、输出用量 |
| `observed_input_tokens` / `observed_output_tokens` | 已取得 usage 的输入／输出小计；存在未知请求时不能视为总量 |
| `requests_missing_input_usage` / `requests_missing_output_usage` | 缺少相应 token 用量的生成请求数 |
| `tool_calls_complete` | 任务已退出且全部调用记录已收齐；未收齐时为 `false`，此时调用数是当前已记录的次数，不能视为最终总数 |

输入统计包含重复发送的历史上下文和供应商计入 `prompt_tokens` 的缓存 token；输出包含供应商计入 `completion_tokens` 的思考 token，不再把缓存／思考分项重复相加。检索 embedding 的用量独立保存在 `embedding_usage`，科学工具内部服务的用量不并入生成模型 token。token 数量也不等同于费用。

计时字段采用 `task-metrics.v2`。扣除只依据已测量的通信区间，不使用超时上限估算：请求最终通信失败时，整个失败请求区间已包含其内部重连，不能再加扣重试；重连后成功时，仅扣失败连接与退避，保留成功请求耗时。生成与 embedding 等待重叠时只扣一次；故障期间若工具仍在运行，或有正常模型响应工作，其重叠时间保留，不会把真实并行工作一并扣掉。公式为 `runtime = wall − measure(union(fault_intervals) \ union(work_intervals))`。例如墙钟 20 秒，故障区间为第 2～15 秒，并行工具工作到第 10 秒，则只扣第 10～15 秒，运行时间为 15 秒。原始 `duration_seconds` 与资源截止时间仍使用墙钟。批次 `progress.json` 的 `session_wall_runtime_seconds` 独立计时，不累加并行任务时间。

运行失败仍保留已记录的墙钟时间和调用；超时、断连或后端未返回 usage 时，对应总 token 标记为 `null`，保留已知小计，绝不填零估计。进程被强制终止或机器掉电时，只能保留最后落盘的轨迹检查点，不能声称已测得完整总量。正常中断的在途任务可查看各自轨迹；批次统计表只收录已返回预测的任务。

`--resume` 复用原有逐题统计；`--retry-failed` 显式重跑时，统计表显示该题新一次尝试的成本，旧尝试同时保存在 `attempt_history` 和独立轨迹中，不混算为本次成本。`--resume --retry-infrastructure` 只重跑已标记的通信失败题，保留模型失败；尚未运行的题正常接续。默认连续 3 次基础设施失败后暂停新派发，进度状态为 `paused_infrastructure`。`metrics` 是资源统计，不改变科学评分和工具路径判定。

本机结果默认不提交到版本控制。`python -m scripts.benchmark.index_results` 可生成本机浏览索引；`reports/tool_preflight.json` 是静态工具预检结果，不代表所有外部服务实时可用。正式参考与金标准位于 [evaluation/data](../evaluation/data/README.md)，评分含义见[评分细则](../evaluation/README.md)。
