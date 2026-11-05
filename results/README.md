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
| `runtime_seconds` | 本次 baseline 的墙钟运行时间，单位秒，包含规划、检索、全部角色生成、工具执行、审查、修复和退出清理；并行工具的时间不会重复相加。不含批次排队、模型服务启动或离线评分 |
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

运行失败仍保留已记录的时间和调用；超时、断连或后端未返回 usage 时，对应总 token 标记为 `null`，保留已知小计，绝不填零估计。进程被强制终止或机器掉电时，只能保留最后落盘的轨迹检查点，不能声称已测得完整总量。正常中断的在途任务可查看各自轨迹；批次统计表只收录已返回预测的任务。

`--resume` 复用原有逐题统计；`--retry-failed` 显式重跑时，统计表显示该题新一次尝试的成本，旧尝试保留在独立轨迹中，不混算为本次成本。`metrics` 是资源统计，不改变科学评分和工具路径判定。

本机结果默认不提交到版本控制。`python -m scripts.benchmark.index_results` 可生成本机浏览索引；`reports/tool_preflight.json` 是静态工具预检结果，不代表所有外部服务实时可用。正式参考与金标准位于 [evaluation/data](../evaluation/data/README.md)，评分含义见[评分细则](../evaluation/README.md)。
