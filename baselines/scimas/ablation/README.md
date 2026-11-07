# SciMas 消融实验

五种消融变体共用工具库、任务、模型客户端、轨迹与评分入口。当前定义为 **`scimas.ablation.v2`**：`w/o Local-repair` 同时关闭执行前图完善；`w/o All` 在四项机制及图完善之外，再关闭科学 Reviewer。这些是公开的扩展消融边界，不能与旧版同名实验直接混合。

## 变体定义

| 变体 / CLI 值 | 角色经验 | 任务内并行 | 候选早停 | 运行期局部修复 | 执行前图完善 | 科学 Reviewer |
| --- | --- | --- | --- | --- | --- | --- |
| SciMas / `full` | 开启 | 开启 | 开启 | 开启 | 开启 | 开启 |
| w/o EXP / `wo-exp` | 关闭 | 开启 | 开启 | 开启 | 开启 | 开启 |
| w/o Parallel / `wo-parallel` | 开启 | 关闭 | 开启 | 开启 | 开启 | 开启 |
| w/o Early-stop / `wo-early-stop` | 开启 | 开启 | 关闭 | 开启 | 开启 | 开启 |
| w/o Local-repair / `wo-local-repair` | 开启 | 开启 | 开启 | 关闭 | 关闭 | 开启 |
| w/o All / `wo-all` | 关闭 | 关闭 | 关闭 | 关闭 | 关闭 | 关闭 |

### w/o EXP

关闭成功调用后的接口模式提取、去重存储、失效处理和角色匹配注入。经验生命周期是单个 task，本组不代表跨题知识迁移的消融。原始 observations、工具契约和依赖数据仍可用；模型仍可从当前观测自行推理。

### w/o Parallel

执行层将单题工具并发上限强制设为 1，按稳定拓扑顺序派发。单个任务的角色决策和评审保留。`--concurrency` 的任务级并发、API 请求并发和工具内部数值库线程不受影响。

派发记录的 `parallel=false` 与该策略一致；full 的 `parallel=true` 只代表获准重叠，实际并发需核对调用时间区间。

### w/o Early-stop

保留科学 Reviewer 以及 `when` 条件记录，但不因已解析为 false 的科学条件剪掉候选及其后继；动态模板展开后的节点同样执行。已计算不代表科学上合格，最终答案仍须按原条件报告。

未经审核或无法解析的条件仍不能直接执行，错误输入与无效输出仍会失败。这一消融针对框架的显式门控，不能确保模型初始规划列出所有可筛选对象，也不改写工具内部的条件逻辑；无门控的任务不能证明早停效果。

### w/o Local-repair

`local_repairs=0`、`graph_refinements=0`：初始图提交后，无论科学执行是否开始，都不调用修复角色。保留科学 Reviewer；它若认为初始图需要修改，任务以 `GraphRefinementDisabled` 终止。执行期的工具异常、绑定阻塞或任一角色的修复请求以 `LocalRepairDisabled` 终止，不进行整图重跑。

Planner 构造第一份合法图时的 schema、契约反馈和协议格式纠正仍可用。这里关闭的“执行前图完善”指合法图提交之后，由评审／执行角色触发的 Planner 修图；它与初始 Planner 的协议解析不是同一阶段。已声明模板按真实输入机械展开、有限瞬时与传输重试、已有 observation 查看、答案格式纠正也保留。

### w/o All

关闭经验、并行、早停、运行期修复、执行前图完善以及科学 Reviewer。Planner 仍生成初始任务图，Executor 按依赖串行调用，Summary 根据实际观测提交答案。图、工具结果与最终答案三个阶段均不会调用 Reviewer 模型或加载其角色提示。

程序仍执行图结构、工具契约、来源绑定、已有确定性数值证书以及答案格式／引用检查；它不会补充 LLM 科学判断，也不会自动推断 Reviewer 的科学语义元数据。轨迹 `reviews` 中的这些程序记录标记为 `mode=deterministic_only`、`scientific_review=false`，不能当成科学评审通过。确定性数值证书只覆盖已实现的检查（目前为对称特征系统），不能验证所有工具的科学结果；没有对应证书时，程序不会凭空增加检查或判定正确。科学答案是否正确仍由统一的外部评分器判定；正常结束不等于答案正确。

## 比较与版本边界

所有额外关闭项均出现在上表、轨迹 `ablation` 和实验配置中。各组保持同一任务、工具、基模、公共资源上限和评分规则，不添加未披露的限制。`w/o Local-repair` 是包含执行前修图的扩展消融；`w/o All` 是包括科学 Reviewer 的组合消融，不能将其差异仅归因于原来的四项机制。

保留能力包括原始证据与正常依赖传递、工具输入输出校验、确定性数值检查、正常模板展开、有限通信／瞬时重试、协议和答案格式纠正、计时计费及正式评分。它们不承担被移除角色的 LLM 科学判断。

v2 写入新的变体标记和实际配置，源文件指纹也随实现改变。旧版结果保留，不能在同一个结果目录拼接 v1／v2；正式对照应使用新代码版本重新运行。

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
| `trajectory.json → graph_refinement_attempts / graph_refinements` | 仅启用图完善时记录，单独计数 |
| `trajectory.json → repair_attempts` | 运行期局部修复的请求用量、最后错误与终止原因 |
| `trajectory.json → steps` | 完整角色请求、决策、工具参数与输出；每次实际调用的起止时间 |
| `task_metrics.json` | 逐题运行时间、工具调用数、输入和输出 token；当前共享任务计时口径 |
| `progress.json` | 实时完成数量、在途任务与通信熔断状态 |
| `monitor/monitor.md`、`monitor/monitor.json` | 每10秒自动刷新的实时监控，显示变体、任务阶段、输入／输出token、调用及失败记录 |

Mini-100 与 Mini-200 共用当前三项主指标：**运行完成率、综合工具规划分、答案准确率**。运行完成率判断正常结束；工具规划分 `tool_planning_accuracy` 是逐题 `S=3CE/(2E+C)` 的宏平均；答案准确率按科学判据独立判断。答案格式单列诊断，严格规划通过率保留为辅助字段。消融变体使用相同的任务集合与[评分细则](../../../evaluation/README.md)。

效率分析使用 `runtime_seconds`、`scientific_tool_calls`、`input_tokens`、`output_tokens`。`DescribeTools` 单独计为 discovery。通信失败终止的任务会保留墙钟时间和实际消耗，但 `runtime_reportable=false`，不能当作正常完成的耗时。计时按通信失败区间与并行工作区间的集合关系扣除，不按分支重复相减。

并行加速比应在相同任务、相同模型设置的配对样本上计算，并同时报告各组完成率；更快的失败不能解释为加速。早停节省应结合实际 false 门控、后续调用数与耗时判断；局部修复收益应结合真实异常、修复记录和保留结果判断。没有触发相应机制的任务不能证明其效果。

正式对照应在**同一源码版本**重新运行 `full` 和五种变体，固定模型、公开题目、工具资源、请求预算、采样设置与任务并发数。当前正式主实验位于 `exp/main_scimas/`，Mini-50 配对结果位于 `exp/main_scimas/mini50/`。比较时应核对各题的实际源码、执行开关与并发配置；主实验的精确来源见 `metadata/sources.json`，不能仅凭共同的基础提交号认定运行条件完全相同。

## 实现与验证

- [policy.py](policy.py)：不可变的机制组合、禁用经验、变体提示与异常类型。
- [run.py](run.py)：共享运行接口的模块入口。
- [../runtime.py](../runtime.py)：执行层落实串行、门控和修复边界。
- [../../react/runner.py](../../react/runner.py)：共享批量运行器中的参数传递、实验记录与续跑隔离。
- [../../../tests/scimas/test_ablation.py](../../../tests/scimas/test_ablation.py)：固定角色决策的配对测试和真实矩阵工具调用；不读取标准答案，不调用生成 API。
- [../../../tests/scimas/test_ablation_extended.py](../../../tests/scimas/test_ablation_extended.py)：v2 的图完善禁用、Reviewer 零调用及确定性检查。
- [../../../tests/scimas/test_ablation_isolation.py](../../../tests/scimas/test_ablation_isolation.py)：经验路径哨兵、配置覆盖、各修复入口与动态展开后的开关隔离。

```bash
python -m pytest tests/scimas/test_ablation.py tests/scimas/test_ablation_isolation.py tests/scimas/test_ablation_extended.py tests/scimas/test_ablation_recording.py -q
python -m pytest tests/scimas -q
```

v2 固定源码回归 **317 项通过**，包括 7 项新增扩展边界测试。当前验收统计、实际配置和源文件哈希见 [acceptance.json](acceptance.json)；旧版隔离核查结果保留在对应审查报告中。

记录链路验收使用受控角色响应与真实科学工具执行，核对当前评分、墙钟和通信重叠计时、工具调用数，以及输入／输出 token 的落盘一致性。通信失败中的未知 usage 保持 null。测试数据不作为模型消融成绩。
