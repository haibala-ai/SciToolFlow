# SciToolFlow Mini-100

当前主实验使用本题库全部 100 题；五组消融改用其中固定的 [Mini-50 选题](../mini-50/README.md)。完整方法的 50 题配对结果从这 100 题中提取，不额外生成。下文的 `--tasks all` 表示 100 题；50 题消融的运行和评分都应传入 Mini-50 的相同题号清单。

**从当前 Mini-200 中随机无放回抽取的固定 100 题，用于 SciMas 主实验与配对子集评估。** 题文、科学输入、附件内容和评分规则与抽样时的对应源题相同，使用统一的任务加载、运行和评分接口。

## 抽样与题号

抽样种子为 `20261106`，执行一次 `random.Random(20261106).sample(population_ids, 100)`，不按学科分层。随机抽取的次序记录在 [sampling.json](sampling.json)，存储时按原题号排序。[ids.txt](ids.txt) 列出 100 个题号，[ids.tsv](ids.tsv) 保留原科学来源映射。

| 学科 | 题数 |
|---|---:|
| 化学 | 32 |
| 材料科学 | 27 |
| 生物／生态 | 21 |
| 机器学习／数理计算 | 20 |
| **合计** | **100** |

保留原有 `SMAS-xxxx` 编号，编号不连续。主实验固定为这 100 题，消融变体共用从中选定的 50 题；不要为不同变体重新抽题。Mini-100 是抽样时的冻结快照，后续 Mini-200 更新不会自动覆盖它。

## 文件与数据边界

| 文件 | 内容 |
|---|---|
| [questions.jsonl](questions.jsonl) | 100 道公开题目，一行一题 |
| [assets/](assets/) 与 [asset_manifest.json](asset_manifest.json) | 所选任务的附件及内容哈希 |
| [metadata.json](metadata.json) | 数据集身份、选定题号、学科分布及文件哈希 |
| [sampling.json](sampling.json) | 完整抽样总体、种子、抽取次序和 Mini-200 来源版本哈希 |
| [ids.tsv](ids.tsv) | Mini 题号与原始科学源题号的映射 |
| [evaluation/](evaluation/) | 仅供评分器使用的参考、原始轨迹副本及验收记录 |

公开加载器只读取任务与附件，不读取参考答案。评分使用本目录的独立副本，不会临时改用 Mini-200 的题目或参考。原始参考的任务号、生成记录和轨迹字节保留其真实来源；只有参考文件路径随副本位置调整。

## 查询、运行与评分

在项目根目录执行。接口名称为 **`mini-100`**；默认数据集仍是 `mini`（200 题），因此本轮主实验与消融均应显式指定 `--dataset mini-100`。

```bash
conda activate SciTool-Unified

# 列出100题，或查看其中一题
python cli.py task --dataset mini-100
python cli.py task SMAS-0103 --dataset mini-100

# SciMas主实验：完整执行100题
python cli.py run --baseline scimas --scimas-ablation full \
  --dataset mini-100 --tasks all --backend api --model deepseek-flash \
  --concurrency 2 --max-context-chars 1500000 --max-output-tokens 65536 \
  --output results/scimas_mini100/full/predictions.json

python cli.py score --dataset mini-100 --tasks all \
  --predictions results/scimas_mini100/full/predictions.json \
  --output results/scimas_mini100/full/scores.json
```

`--scimas-ablation` 可选 `full`、`wo-exp`、`wo-parallel`、`wo-early-stop`、`wo-local-repair`、`wo-all`，每个变体使用独立输出目录。`wo-all` 关闭经验、并行、早停和局部修复四项机制，完整定义见[消融说明](../../baselines/scimas/ablation/README.md)。

单题抽测时，在运行和评分命令中同时指定相同的 `--tasks SMAS-0103`。全量评分分母为 100，单题抽测分母为 1；缺失预测计失败。ReAct 和 SciToolAgent 同样使用 `--dataset mini-100`，将 `--baseline` 改为相应名称即可。API、本地 vLLM 服务和本地权重沿用现有 `--backend api|vllm|local` 接口。模型及 embedding 配置见[安装与部署](../../docs/setup.md)。

只有规划、不执行科学工具时：

```bash
python cli.py plan --dataset mini-100 --tasks SMAS-0103 \
  --backend api --model deepseek-flash --output results/mini100_plan
```

在代码中加载公开输入：

```python
from tasks.datasets import load_dataset
from tasks.assets import load_agent_input

dataset = load_dataset("mini-100")
task = dataset.select("SMAS-0103")[0]
public = load_agent_input(task, dataset.asset_root)
```

## 评分与实验记录

与当前 Mini-200 共用[新版评分细则](../../evaluation/README.md)：

| 主指标 | 含义 |
|---|---|
| `runtime_completion_rate` | 真实运行正常结束的比例，独立于科学答案正确性 |
| `tool_planning_accuracy` | 逐题 `S=3CE/(2E+C)` 的宏平均；C 为编排完成程度，E 为有效选择效率 |
| `answer_accuracy` | 按原科学判据独立判断答案正确的比例 |

答案格式单列诊断，严格规划通过率作为辅助字段保留。结果带 `dataset="mini-100"` 和独立实验指纹，不能与 Mini-200 的预测文件混用或续跑；即使两套题库含相同题号，也必须按各自数据集运行和评分。

时间、科学工具调用数、DescribeTools 次数、输入与输出 token 保存于 `task_metrics.json` 和每题轨迹，评分结果保存于 `scores.json`。通信失败时保留墙钟耗时及已知 token，`runtime_reportable=false`，不把未知用量记成零。

## 完整性验收

[evaluation/acceptance.json](evaluation/acceptance.json) 包含全部100题的附件／参考身份检查与当前规则自检。参考运行完成、严格规划和答案检查均通过；综合规划分保留参考原有的效率扣分。**参考自检与受控接口测试不代表 baseline 模型成绩。**

```bash
python -m pytest tests/integration/test_mini100_dataset.py -q
```

抽样生成程序为 `python -m scripts.benchmark.mini100`，已有 `tasks/mini-100/` 时会拒绝覆盖，防止实验过程中样本漂移。
