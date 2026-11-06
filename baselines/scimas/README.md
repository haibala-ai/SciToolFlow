# SciMas

SciMas 将科学问题组织为带数据依赖和科学条件的任务图，由 **Planner、Executor、Reviewer** 协作完成工具选择、并行执行、过程审查和局部修复。它使用自己的工具知识图谱，与 SciToolAgent 的图谱和检索策略独立。

## 运行与评分

SciMas 与其他 baseline 共用公开题目、模型客户端、任务预算、预测文件和 `workflow.v1` 评分入口。公开入口默认为Mini-200，Full-500源库需显式选择；两者题号与实验身份分开。

```bash
# 本地 vLLM；服务地址由 SCITOOLFLOW_VLLM_BASE 指定
python cli.py run --baseline scimas --dataset mini --tasks SMAS-0103 \
  --backend vllm --model YOUR_SERVED_MODEL \
  --output results/scimas_mini/predictions.json

python cli.py score --dataset mini --tasks SMAS-0103 \
  --predictions results/scimas_mini/predictions.json \
  --output results/scimas_mini/scores.json

# 生成 API；仍需安装科学工具所需的本地依赖
python cli.py run --baseline scimas --dataset full --tasks FLOW-0029 \
  --backend api --model YOUR_API_MODEL \
  --output results/scimas_api/predictions.json
```

### AIHubMix / DPSK API

提供 [dpsk_api.json](../../configs/services/dpsk_api.json) 配置：`https://aihubmix.com/v1`，模型 `doubao-deepseek-v4.1-flash-1017`。从项目根目录在交互终端执行：

```bash
conda activate SciTool-Unified
python -m scripts.services.configure_api
python -m scripts.services.configure_api --check

python cli.py run --baseline scimas --dataset mini --tasks SMAS-0103 \
  --backend api --model doubao-deepseek-v4.1-flash-1017 \
  --max-output-tokens 32768 \
  --output results/scimas_dpsk/predictions.json
python cli.py score --dataset mini --tasks SMAS-0103 \
  --predictions results/scimas_dpsk/predictions.json \
  --output results/scimas_dpsk/scores.json
```

配置命令隐藏输入密钥，原子保存至 `.local/credentials/services.env`，文件权限为 `600`，保留现有 embedding 和科学服务配置。密钥不作为命令行参数或配置模板内容；该目录由 Git 忽略。`--check` 使用同一生成客户端发起一次小额真实请求，不运行 benchmark。环境变量优先于本地文件。

该配置使用已验证的 `httpx` 传输、`max_tokens`、JSON object 模式、32,768 输出 token 上限和 300 秒请求超时；完整 JSON Schema 由本地协议校验。模型默认思考消耗同一输出额度，运行命令也需显式设置 `--max-output-tokens 32768`；实际用量按服务端返回的 usage 记录。`httpx` 对建立连接失败最多重试两次；收到 HTTP 响应后的错误和发送后的读取／写入失败均不自动重发。长思考请求遇到读取超时时会明确失败，不将联调失败包装成任务通过。生成密钥与检索 embedding 的密钥分别配置。需要更换供应商时，使用 `--profile /path/to/profile.json`，或按部署文档配置其他兼容接口。

### DeepSeek 官方直连与长任务

[deepseek_api.json](../../configs/services/deepseek_api.json) 使用 `https://api.deepseek.com`、`deepseek-flash`、10 秒连接超时、600 秒生成响应等待上限和 65,536 输出 token 上限。连接失败仍按发送前重试规则处理，避免 TLS 建连占用整个长生成超时。`SCITOOLFLOW_API_TRUST_ENV=0` 使生成客户端忽略代理环境变量；embedding 和科学工具仍各自使用原有网络配置，不全局清空代理。各角色请求均明确要求 JSON 对象，满足供应商 JSON 模式的提示词要求。

```bash
python -m scripts.services.configure_api --profile configs/services/deepseek_api.json
python cli.py run --baseline scimas --dataset mini --tasks all \
  --backend api --model deepseek-flash --concurrency 8 \
  --max-context-chars 1500000 --max-output-tokens 65536 \
  --max-model-requests 400 --task-timeout 7200 \
  --output results/scimas_deepseek/predictions.json
```

按[官方模型说明](https://api-docs.deepseek.com/quick_start/pricing/)，模型服务提供 1M token 上下文；本地 150 万字符保护阈值是字符限制，不等同于 token 数。API 路径由字符保护和服务端真实上下文限制检查，`--max-input-tokens` 不作为 API 的精确计数器。思考和回复共享单次输出额度。增加上限不会预先消费这些 token，统计仍取服务端实际 usage。

不设置决策步数或工具调用数硬上限，400 次生成请求由所有角色共享，允许超过 32 步的工作流；初始规划及局部修复边界仍按算法配置执行。`--concurrency 8` 表示最多 8 个独立任务进程，可以跨任务同时请求 API，不改变单题 Planner／Executor／Reviewer 的依赖关系。它与 `tool_concurrency=4`（单题同时执行的工具数）分别控制。本次若只选两题，实际同时在途的模型请求最多两个，不能把配置上限当作已测吞吐。

供应商 JSON 模式可能返回 HTTP 200、`finish_reason=stop`、但正文仅含空白的响应。客户端保留这种原始响应及其 usage，交由已有的协议纠错次数和总请求预算处理；空白不视为有效决策，不跳过科学工具，也不填充答案。传输层不会因此隐式重发，后续纠错请求逐次记录和计费。HTTP 错误、断连、内容过滤与输出截断继续沿用明确失败规则。

也可用 `python -m baselines.scimas.run`，参数与 `cli.py run --baseline scimas` 相同。`--backend local` 使用现有本地 worker；三种后端都通过 `src/models/`，不绑定某个模型。生成服务与 embedding 服务分别配置，参见[安装与部署](../../docs/setup.md)。

只查看规划时，使用 `python cli.py plan --dataset mini --tasks SMAS-0103 --backend vllm --output results/scimas_plan`。`plan` 产物不包含完整执行轨迹，不能提交正式评分。

## 完整工作流

```mermaid
flowchart TD
  Q[公开任务与附件] --> P[Planner：分解需求、检索、绑定端口]
  KG[SciMas 独立工具图谱] --> P
  P --> V[程序校验 DAG 与契约]
  V --> R[Reviewer：检查题意、对象、方法和科学门控]
  R --> E[Executor：选择就绪节点]
  E --> T[隔离工具进程；允许的分支并行]
  T --> C[输出契约校验与 Reviewer 结果审查]
  C -->|有效证据| E
  C -->|需要修复| L[Planner 局部修订]
  L --> V
  C -->|满足全部交付条件| A[Executor 汇总答案]
  A --> F[Reviewer 最终科学审查与格式校验]
  F --> O[正式预测与完整轨迹]
  C --> M[确认的任务内角色经验]
  M --> E
  M --> L
  M --> R
```

1. **规划。** 只读取公开问题、经清单验证的附件和工具知识。Planner 提取有原文依据的需求，按子任务检索工具，按需查询契约，提出 DAG。程序检查参数、字段路径、类型、依赖环路和交付覆盖。每次规划请求都携带已完成的检索及剩余额度；检索额度耗尽后必须基于已有候选建图，或明确报告缺少能力，不能继续重复检索。
2. **执行前审查。** Reviewer 对照原问题核对完整性、计算方向、对象、单位、方法和筛选条件。类型正确不代表科学正确，例如 `inverse × inverse` 不能替代 `original × inverse`。科学门控必须获得绑定当前节点身份的批准。
3. **事件驱动执行。** Executor 选择就绪节点，程序解析真实参数并调用工具。一个分支的结果通过审查后即可推进其后继，无需等待其他独立分支结束。只有已确认可隔离并行的工具才能重叠运行；其余工具独占本任务执行槽。
4. **结果与条件。** 原始输出先通过公共契约及节点检查，再由 Reviewer 检查其科学用途。缺失、失败和陈旧结果不可用于下游，也不会被当作科学筛选的“不通过”。条件为明确假时记录淘汰依据；完整报告需求不允许依赖候选筛选分支。
5. **有限恢复。** 明确的暂时连接、超时和限流失败允许一次重试。其他问题交给 Reviewer 诊断和 Planner 局部修复。修复不得改动无关节点或降低原始需求；保留未受影响的有效结果，作废受影响后继，取消相关在途进程。所有实际尝试，包括失效调用，保留在轨迹中。
6. **提交。** 所有节点均取得有效结果或有合法筛选依据后，Executor 按公开 `answer_schema` 汇总，Reviewer 再核对科学结论。格式错误反馈只来自公开结构，格式纠正不提供参考答案。长数组可用 `{"$observation":"o0001","field":["实际字段"]}` 引用当前已接受输出，程序展开后再验证，避免模型重新抄写造成误差。若缺少必要证据，可申请剩余次数内的局部修复；不能把运行失败包装成完成。

Reviewer 是同一基模的独立角色上下文，并非正确性预言机。`completed` 表示完成了执行与审查协议；是否科学正确仍由独立 benchmark 评分判断。

公开文本附件经过清单和哈希校验后，可作为理解问题的预览。Planner 与 Reviewer 要求文件来源的科学数据先由真实读取工具取得，再通过节点绑定进入下游计算；预览不能替代读取观测。直接公开在任务输入中的值无需额外文件读取。跨 baseline 比较仍应报告附件呈现方式，不能把不同输入条件的成绩直接归因于算法。见[验收记录](ACCEPTANCE.md)。

## 独立工具知识图谱

| 方法 | 图谱与向量 | 用途 |
| --- | --- | --- |
| SciToolAgent | `tools/graph/graph_store.json`、`index_store.json` | 原有工具关系与检索 |
| SciMas | `tools/graph/scimas/graph.json`、`embeddings.json.gz` | 工具与输入输出端口、数据概念、规划约束及资源信息 |

共同契约来自 `tools/catalog/catalog.json`。SciMas 独有补充知识存于 `tools/graph/scimas/annotations.json`，绑定契约及实现来源。全部 **472** 个图谱工具都有契约派生规划信息；**99** 个具有绑定当前源码和契约的补充注释，其中原有 **6** 个保留详细的形状约束、方法限制和端口说明。本轮对 **97** 种本地工具完成生产 Executor 的成对隔离调用检查，补充并行执行提示；这些集合有重叠。记录见 [parallel_review.json](../../tools/graph/scimas/parallel_review.json)。并行权限要求独立 worker 进程、独立工作目录和不变的输入文件，不代表任意线程安全或已测得加速比。未审查工具的并行安全性与未测成本保持未知。`DescribeTools` 是普通通用工具，但不进入图谱或向量索引。

SciMas 独立保存 472 份 `text-embedding-3-large` 功能向量，维数 3072；精确复用相同文本及模型身份的既有向量。端口和约束作为图结构与上下文使用，不声称它们已单独编码。查询仍使用匹配的 embedding API。第二阶段未改工具功能描述，因此无需重新计算这些功能向量。

```bash
python -m baselines.scimas.build_knowledge
```

加载时校验契约、注释、图谱和向量身份；公共描述变化时，应先按工具维护流程更新功能向量，再重建 SciMas 图谱。候选连接和替代工具不自动授权科学方法替换。

## 任务图与证据

每个节点描述一项工具调用：`id`、`tool`、`purpose`、`object`、`arguments`；可声明条件 `when`、单调用映射 `for_each` 和输出 `checks`。数据依赖由参数绑定生成，控制依赖由条件引用生成。

| 绑定 | 含义 |
| --- | --- |
| `literal` | 明确常量，不用于伪造计算结果 |
| `task` | 公开输入字段 |
| `node` | 已接受前置节点的真实输出字段 |
| `item` | 映射中的当前输入元素 |
| `collect` | 映射展开后的有序输出集合 |
| `list` | 多个绑定的有序集合，可保留空集合的来源依赖 |

`decoded=true` 只允许读取契约明确声明的 JSON 字符串。自然语言输出供 Reviewer 阅读和最终报告使用；若下游需要结构化值，须规划实际解析或转换工具，不能把 Reviewer 猜出的字段当作原始工具输出。单位、对象和方法等确认元数据必须引用实际输出字段，并通过精确值核验。

`complete` 需求要求完整报告；`screen` 需求允许有依据的候选早停。`for_each` 每次最多展开 128 项，保留来源与顺序，再审查具体节点；空动态集合保留生产节点证据。它是单调用映射，不是任意嵌套程序。不得用筛选后缺失的结果悄悄填充聚合输入。

解析器契约中明确允许任意 JSON 的字段可绑定运行时确定的子字段。静态校验将其标为待验证，而非已证实；实际字段缺失、下游参数类型不符、映射来源不是数组或超过展开上限仍会失败。封闭对象和标量字段不会因此开放任意路径。

每个结果绑定当前节点及其所有前置依赖的身份。`TaskGraph.revise()` 创建新版本，需求不变，返回改动及失效范围。修订前的原始调用不删除；只有当前有效结果进入后续计算。当前仅在单次任务内复用结果，不提供跨运行的科学缓存。

## 调度、经验与资源

[config.json](config.json) 设置 SciMas 的算法边界：

| 设置 | 默认 | 含义 |
| --- | ---: | --- |
| `tool_concurrency` | 4 | 单题最多同时运行的工具调用 |
| `transient_retries` | 1 | 每个节点身份的暂时故障重试次数 |
| `local_repairs` | 2 | 单题全部角色共享的局部图修复次数 |
| `planning_requests` | 10 | 初始分解、检索反馈及建图的请求上限 |
| `max_map_items` | 128 | 单次映射的最大展开项数 |
| `experience_capacity` | 20 | 当前任务内角色经验总容量 |
| `experience_matches` | 3 | 每次角色决策最多注入的匹配经验 |

`--concurrency` 控制同时运行的题目数，与单题工具并行数不同。每个调用使用独立工作目录和产物目录，子进程组支持取消。先前调用的产物只有出现在已接受输出中、且确实位于本次运行目录，才会加入后续文件访问列表。

各角色共享 `--max-model-requests` 和 `--task-timeout`。工具调用受 `--tool-timeout` 限制；可选的调用数、思考步数和决策数上限继续有效。默认沿用项目统一资源策略，不把参考路径长度当作任务预算。每次真实模型请求都写入同一 ledger；格式修正、审查、重规划和最终汇总均计费。

经验不是跨题答案记忆。Executor 记录经过实际调用验证的参数绑定方式；Reviewer 记录经过程序检查的输出访问方式；Planner 只有在前置输出被后继成功消费后记录衔接方式。经验绑定工具契约，按角色与当前工具匹配；确定性失败会使相关经验失效。不会把一个候选的数值迁移给另一个候选，也不会从评分参考中学习。

## 通信恢复与错误反馈

连续 3 道任务因生成 API 或 embedding 通信故障终止时，批次暂停派发新任务，已在运行的任务继续收齐结果。`progress.json` 显示 `paused_infrastructure` 和具体通信诊断；`--network-failure-threshold` 可修改阈值，0 表示关闭。网络恢复后，在相同代码及配置下继续：

```bash
python cli.py run --baseline scimas --dataset mini --tasks all \
  --backend api --model YOUR_API_MODEL --concurrency 2 \
  --output results/YOUR_RUN/predictions.json --resume --retry-infrastructure
```

恢复时必须保留首次运行的其他参数。`--retry-infrastructure` 只重新运行已标记的基础设施失败题及尚未运行题，模型／科学失败保留；旧尝试保存到预测文件的 `attempt_history`，原轨迹仍保留。代码、prompt 或配置发生变化时必须新建实验目录，不能强行拼接旧结果。

生成客户端只对确定发生在发送前的建连失败进行有界退避重连，并保持原接口和代理路线。读写中断和 HTTP 错误不自动重放可能已计费的生成。通信错误单独标记，不作为科学负面结果。

Executor 选错 ready 节点、Repair 查询未知工具名会收到有限次数的纠错反馈。Reviewer 分别看到声明绑定、实际实参、来源观察和待审核／已接受／过期状态；确定性数值证书辅助审查，不替代科学任务判断。`max_failures_per_action=0` 统一表示关闭累计限制；瞬时工具重试和局部修复仍有各自的次数保护。

## 实现效率

角色请求将任务与图等稳定上下文放在前面，将执行状态放在后面，并采用紧凑 JSON 编码。图谱连接候选、输出预览序列化和角色 prompt 在任务内复用；科学证据有效性仍随图修订重新检查。轨迹保留全部内容与原子检查点，使用紧凑格式减少重复写入。详见[效率设计与测量边界](EFFICIENCY.md)。

## 轨迹与代码

完整轨迹保存在 `results/<运行名>/trajectories/<任务ID>-<run_id>/trajectory.json`。其中保存角色请求、实际工具输入输出、图版本、局部修订、科学审查、筛选依据、经验及资源 ledger；工具产物位于同级 `calls/`。模型看到的是有明确截断标识的预览，可以按观测 ID 和字段路径查看完整值；原始结果保留在轨迹中。

每题自动记录 `metrics.runtime_seconds`（扣除通信故障等待后的运行秒数）、`metrics.tool_calls`（含失败、重试及 `DescribeTools` 的派发总次数）、`metrics.input_tokens` 和 `metrics.output_tokens`（所有角色生成的输入／输出总用量）。同一对象保存在预测与轨迹中，批次另生成 `task_metrics.json`。未知 usage 以 `null` 标记并保留已知小计；缓存和思考 token 不重复累加。完整口径及续跑规则见[实验输出](../../results/README.md#逐题运行成本)。

### 单题案例分析

`trajectory.json` 保存完整公开问题与输入、附件预览、每次模型请求的全部消息和生成参数、原始响应、解析后的决策和协议错误。每步具有 `step_id`、记录时间和相对起点的秒数；模型请求另有起止时间、耗时和 usage。接口实际返回的附加消息字段和输出截断时的部分响应也保留，部分响应不会作为有效决策执行。

工具派发步骤记录实际参数、文件范围、超时、工作目录和并行标记；完成记录保存完整输出、错误及 dispatcher 已脱敏的诊断信息。并行调用的真实起止时间与主循环收集顺序分别记录。`graphs`、`reviews`、`repairs`、`results`、`pruned`、`approved_gates` 和 `experiences` 保留图版本、审查、修复、证据采纳和筛选状态；`pending_calls` 标识尚未收齐的调用。规划过程在完成前保存不重复模型消息的 `planning_progress`。异常或正常中断会保存最后检查点；强制终止或掉电后的完整性以最后实际落盘内容为限。

运行时继续使用原有紧凑 JSON 检查点，不增加逐步文件写入，不为生成案例报告调用模型。运行结束后按需离线导出：

```bash
python -m baselines.scimas.trajectory \
  results/YOUR_RUN/trajectories/TASK_ID-RUN_ID/trajectory.json
```

默认在该次任务目录下生成 `analysis/`：

| 文件 | 用途 |
| --- | --- |
| `trajectory.md` | 可读的逐步案例索引，含决策、错误和统计预览，以及完整 JSON 的链接 |
| `requests/<step_id>.json` | 单次模型的完整输入、响应、解析决策、校验与耗时 |
| `calls/<observation_id>/request.json`、`response.json` | 单次工具的完整参数、输出与诊断 |
| `manifest.json` | 原始轨迹路径和 SHA256，便于确认导出来源 |

可用 `--output /path/to/analysis` 指定独立导出目录。导出不改写原始轨迹，不运行模型、工具或评分器，不计入任务时间。Markdown 中的长内容仅作有标识的预览，JSON 保留完整内容。历史轨迹未记录的字段不会推测补齐。

新增元数据复用既有检查点，主要增加少量字段的编码开销；不声称记录完全没有成本。`wall_runtime_seconds` 保留真实墙钟时间，`runtime_seconds` 只扣除有记录的通信故障等待；日志、正常模型响应、工具执行及科学纠错仍计时。API 故障中止的尝试设置 `runtime_reportable=false`、`runtime_seconds=null`，不作为速度统计样本。

| 模块 | 职责 |
| --- | --- |
| `knowledge.py`、`build_knowledge.py` | 独立图谱构建、校验、检索与端口查询 |
| `schema.py`、`task_graph.py`、`validation.py` | 规划语言、版本化 DAG、静态与运行时证据校验 |
| `assets.py` | 清单与内容哈希校验后的公开附件、预览和原文依据 |
| `planner.py` | 初始任务分解、检索历史与迭代建图 |
| `runtime.py` | 三角色协作、审查、修订和最终提交 |
| `executor.py` | 并发进程调度、目录隔离与取消 |
| `roles.py`、`context.py`、`prompts/` | 角色协议、稳定前缀上下文、有限格式纠正与请求记录 |
| `trajectory.py` | 轻量步骤身份与离线案例导出，运行时不生成报告副本 |
| `experience.py` | 任务内证据支持的角色经验 |
| `runner.py`、`run.py` | 独立规划命令与完整 baseline 入口 |

验收依据见 [ACCEPTANCE.md](ACCEPTANCE.md)。运行测试：

```bash
python -m pytest tests/scimas -q
```

验收中的 `tests/scimas/run_isolated_acceptance.py` 是模型请求的邮箱适配器：每次由一个新建的、信息受限的子智能体回复，实际工具仍由上述运行时调用。它不是新的生产模型后端；子智能体不读取参考答案或评分规则，未公开的 token 用量记录为未知。
