# SciMas 消融实验

五种消融变体共用 SciMas 的模型客户端、工具库、任务输入、输出契约和评分器，只改变指定的运行机制。完整方法使用 `full`；默认运行方式不变。

## 变体定义

| 论文名称 | `--scimas-ablation` | 角色经验 | 任务内并行 | 候选早停 | 局部修复 |
|---|---|---|---|---|---|
| SciMas | `full` | 开启 | 开启 | 开启 | 开启 |
| w/o EXP | `wo-exp` | **关闭** | 开启 | 开启 | 开启 |
| w/o Parallel | `wo-parallel` | 开启 | **关闭** | 开启 | 开启 |
| w/o Early-stop | `wo-early-stop` | 开启 | 开启 | **关闭** | 开启 |
| w/o Local-repair | `wo-local-repair` | 开启 | 开启 | 开启 | **关闭** |
| w/o All | `wo-all` | **关闭** | **关闭** | **关闭** | **关闭** |

`w/o All` 同时关闭角色经验、任务内并行、候选早停和局部修复四项机制，作为基础对照。

### w/o EXP

不保存成功调用形成的程序性经验，也不向后续角色提供经验匹配结果。当前实现的经验生命周期是**单个 task 内**，没有跨 task 的持久经验库；这个实验不能解释为跨题知识迁移的消融。任务图、真实 observations、工具契约以及当前任务的结果依赖均保留，否则会同时损伤上下文记忆和正常数据传递。

### w/o Parallel

任务内工具并发上限固定为 1。调度器按已批准图中的节点顺序，在依赖满足的节点间稳定选择下一个节点；列表中的后继即使写在前驱前面，也不能提前执行。Executor 仍进行调度决策，Reviewer 仍审查结果，避免通过额外删除角色请求来改变对照条件。

这是任务内工具调度的消融。`--concurrency 2` 仍表示同时运行两个独立 task；API 请求并发策略也不会被这个变体改成 1。

### w/o Early-stop

保留图中 `when` 条件和 Reviewer 的校验记录。已解析为 false 的科学筛选条件不再剪掉该候选分支，其后继仍执行；Summary 必须区分“已经计算”与“满足筛选条件”。

尚未获得证据的条件、未经审核的条件、失效的绑定、缺失的数据、工具错误和非法输入仍不能执行或作为有效结果传递。关闭候选筛选不等于放行错误计算。Reviewer 仍检查科学正确性；它不应仅因候选筛选失败而删除分支或请求修复。

消融对象是图中显式表达的候选门控。若 Planner 一开始只列出筛选后的候选，没有构造其余候选分支，框架不会虚构缺失候选；若某题没有条件节点，早停机制在该题不会生效。分析时应报告实际出现门控的题数，不能仅凭变体名称断言发生了早停。

### w/o Local-repair

采用实验定义中的**直接失败**策略，不进行整图重跑。工具异常在允许的瞬时重试次数耗尽后，或出现不可重试的无效输出时，任务失败并保留已发生的调用。任何运行期图修复请求也会产生 `LocalRepairDisabled`，不会调用修复角色或重写图。

初始规划及执行前的图完善、结构校验、有限的传输重试、输出格式纠错和已有 observation 的查看保持一致。执行前的 Reviewer 异议会反馈给 Planner，并记录在 `graph_refinement_attempts`／`graph_refinements`；此时还没有已执行的科学结果，各变体均可完善图。这与执行异常驱动的局部重规划是不同机制；只有后者受 `local_repair` 开关控制，记录在 `repair_attempts`／`repairs`。科学错误不会因禁用修复而自动通过。

### w/o All

初始规划后，按依赖关系串行执行全部候选分支，不积累或检索角色经验，不进行门控剪枝或自适应图修复。已声明 `for_each` 模板仍可按真实输入数组机械展开，这是实例化原计划，不是异常后的重新规划。输入输出校验、科学评审和最终答案汇总继续保留。

## 运行与测评

当前主实验使用 [Mini-100](../../../tasks/mini-100/README.md) 全部 100 题，五组消融使用其中的 [Mini-50 固定选题](../../../tasks/mini-50/README.md)。50 题包含六组已启动的 8 题，其余 42 题随机无放回抽取；完整方法的 50 题对照直接从主实验结果评分，不重新生成。底层数据集统一为 `mini-100`，消融通过显式题号限制为 50 题。以下命令在项目根目录执行，生成 API 与 embedding 服务沿用[部署配置](../../../docs/setup.md)。每个变体使用独立输出目录和同一组固定题目。

```bash
conda activate SciTool-Unified
TASK_IDS=$(python -m scripts.benchmark.mini50 --print-tasks) || exit 1

python cli.py run --baseline scimas --scimas-ablation wo-parallel \
  --dataset mini-100 --tasks "$TASK_IDS" --backend api --model deepseek-flash \
  --concurrency 2 --max-context-chars 1500000 --max-output-tokens 65536 \
  --max-model-requests 400 --task-timeout 7200 \
  --output results/scimas_ablation/wo-parallel/predictions.json

python cli.py score --dataset mini-100 --tasks "$TASK_IDS" \
  --predictions results/scimas_ablation/wo-parallel/predictions.json \
  --output results/scimas_ablation/wo-parallel/scores.json
```

将 `wo-parallel` 换成表中的其他值即可。也可以使用模块入口：

```bash
python -m baselines.scimas.ablation.run --scimas-ablation wo-exp \
  --dataset mini-100 --tasks SMAS-0001 --backend api --model deepseek-flash \
  --max-context-chars 1500000 --max-output-tokens 65536 \
  --output results/scimas_ablation/wo-exp-smoke/predictions.json
```

本地模型使用同一入口，将 `--backend` 改为 `vllm` 或 `local` 并指定服务模型名。`local` 后端遵循共享运行器的单任务进程限制。正式比较应固定模型配置、任务集合和代码版本；下文的框架测试不作为实际模型实验成绩。

续跑时保留同一组参数并加 `--resume`。只重试通信失败时再加 `--retry-infrastructure`。变体、实际配置及源码哈希均写入实验指纹；不同变体或不同源码版本不能混入同一份预测文件。

## 保存的证据与比较口径

| 文件或字段 | 内容 |
|---|---|
| `predictions.json → settings.scimas_execution` | 变体开关与实际生效的 SciMas 配置 |
| 每题 prediction 和 `trajectory.json → ablation` | 本题变体身份、经验范围、不可恢复异常策略 |
| `trajectory.json → gate_evaluations` | 条件及证据、true / false / unknown 状态、剪枝或继续执行决定 |
| `trajectory.json → graphs / repairs / reviews / experiences` | 实际图版本、修复与复用、评审、经验累积 |
| `trajectory.json → graph_refinement_attempts / graph_refinements` | 各变体共有的执行前建图纠错，单独计数 |
| `trajectory.json → repair_attempts` | 运行期局部修复的请求用量、最后错误与终止原因 |
| `trajectory.json → steps` | 完整角色请求、决策、工具参数与输出；每次实际调用的起止时间 |
| `task_metrics.json` | 逐题运行时间、工具调用数、输入和输出 token；当前共享任务计时口径 |
| `progress.json` | 实时完成数量、在途任务与通信熔断状态 |
| `monitor/monitor.md`、`monitor/monitor.json` | 每10秒自动刷新的实时监控，显示变体、任务阶段、输入／输出token、调用及失败记录 |

Mini-100 与 Mini-200 共用当前三项主指标：**运行完成率、综合工具规划分、答案准确率**。运行完成率判断正常结束；工具规划分 `tool_planning_accuracy` 是逐题 `S=3CE/(2E+C)` 的宏平均；答案准确率按科学判据独立判断。答案格式单列诊断，严格规划通过率保留为辅助字段。消融变体使用相同的任务集合与[评分细则](../../../evaluation/README.md)。

效率分析使用 `runtime_seconds`、`scientific_tool_calls`、`input_tokens`、`output_tokens`。`DescribeTools` 单独计为 discovery。通信失败终止的任务会保留墙钟时间和实际消耗，但 `runtime_reportable=false`，不能当作正常完成的耗时。计时按通信失败区间与并行工作区间的集合关系扣除，不按分支重复相减。

并行加速比应在相同任务、相同模型设置的配对样本上计算，并同时报告各组完成率；更快的失败不能解释为加速。早停节省应结合实际 false 门控、后续调用数与耗时判断；局部修复收益应结合真实异常、修复记录和保留结果判断。没有触发相应机制的任务不能证明其效果。

正式对照应在**同一源码版本**重新运行 `full` 和五种变体，固定模型、公开题目、工具资源、请求预算、采样设置与任务并发数。`exp/main_scimas/` 中归档的 `d6246dc` 主实验保留了旧版通信与框架问题，不应直接用作当前消融实现的配对控制组。

## 实现与验证

- [policy.py](policy.py)：不可变的机制组合、禁用经验、变体提示与异常类型。
- [run.py](run.py)：共享运行接口的模块入口。
- [../runtime.py](../runtime.py)：执行层落实串行、门控和修复边界。
- [../../react/runner.py](../../react/runner.py)：共享批量运行器中的参数传递、实验记录与续跑隔离。
- [../../../tests/scimas/test_ablation.py](../../../tests/scimas/test_ablation.py)：固定角色决策的配对测试和真实矩阵工具调用；不读取标准答案，不调用生成 API。

```bash
python -m pytest tests/scimas/test_ablation.py tests/scimas/test_ablation_recording.py -q
python -m pytest tests/scimas -q
```

记录链路验收使用受控角色响应与真实科学工具执行，核对当前评分、墙钟和通信重叠计时、工具调用数，以及输入／输出 token 的落盘一致性。通信失败中的未知 usage 保持 null。测试数据不作为模型消融成绩。
