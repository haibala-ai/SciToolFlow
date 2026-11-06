# SciMas 消融用 Mini-50

本轮主实验使用现有 **Mini-100 全部 100 题**；五组消融使用这里固定的 **50 题**。完整方法的 50 题对照从主实验结果中提取，无需再次调用模型。六组对照使用相同的 50 个题号，共涉及 350 个“方法 × 题目”位置，而非原计划的 700 个。

## 选题

已启动的六组实验涉及 8 个不同题号，全部纳入：`SMAS-0001`、`0002`、`0003`、`0004`、`0006`、`0007`、`0009`、`0012`。从 Mini-100 剩余 92 题中无放回随机抽取 42 题，种子为 `2026110602`，不按学科或结果重抽。失败与未完成的题同样保留，不按成功率挑选。

这是**保留已启动题目的条件随机样本**，不是无条件抽取的 50 题。学科数量为化学 17、材料 10、生物 11、机器学习／数理计算 12。

- [ids.txt](ids.txt)：50 个题号，一行一个。
- [ids.tsv](ids.tsv)：对应的原始科学任务映射。
- [sampling.json](sampling.json)：必选题、随机抽样顺序、固定题号、种子与父题库摘要。
- [inclusion_evidence.json](inclusion_evidence.json)：六组已启动记录的题号及检查点摘要，用于核实必选范围。

这里保存选题清单，题文、附件、参考与评分器共用 `tasks/mini-100/`，避免复制并改变已付费轨迹的 dataset 身份。运行和评分均使用 **`--dataset mini-100` 加相同的 50 个显式题号**；没有新增 `--dataset mini-50`。

## 运行与评分

在项目根目录执行。`--print-tasks` 会先验证抽样文件与父题库摘要，验证失败时必须停止执行。

```bash
conda activate SciTool-Unified
TASK_IDS=$(python -m scripts.benchmark.mini50 --print-tasks) || exit 1

# 主实验：Mini-100 全部 100 题。
python cli.py run --baseline scimas --scimas-ablation full \
  --dataset mini-100 --tasks all --backend api --model deepseek-flash \
  --embedding-backend local --concurrency 2 \
  --output results/scimas_mini100/full/predictions.json

python cli.py score --dataset mini-100 --tasks all \
  --predictions results/scimas_mini100/full/predictions.json \
  --output results/scimas_mini100/full/scores.json

# 从主实验原始检查点直接评分同一份 50 题对照，不重新生成。
python cli.py score --dataset mini-100 --tasks "$TASK_IDS" \
  --predictions results/scimas_mini100/full/predictions.json \
  --output results/scimas_mini100/full/scores_mini50.json

# 消融：将 wo-exp 替换为其余四种变体，分别使用独立目录。
python cli.py run --baseline scimas --scimas-ablation wo-exp \
  --dataset mini-100 --tasks "$TASK_IDS" --backend api --model deepseek-flash \
  --embedding-backend local --concurrency 2 \
  --output results/scimas_mini100/wo-exp/predictions.json

python cli.py score --dataset mini-100 --tasks "$TASK_IDS" \
  --predictions results/scimas_mini100/wo-exp/predictions.json \
  --output results/scimas_mini100/wo-exp/scores.json
```

上述命令展示选题与评分入口。正式实验还需固定相同的代码、模型、请求限制和工具资源；变体定义见[消融说明](../../baselines/scimas/ablation/README.md)。统计分母分别为主实验 100、配对消融 50；不传 50 题清单而使用 `--tasks all` 会按 100 题评分，缺失预测计失败。

## 其他 baseline

ReAct 和 SciToolAgent 使用相同的题目选择、轨迹记录与评分接口，将 `--baseline` 改为 `react` 或 `scitoolagent` 即可，无需 SciMas 的消融参数。以下以 50 题为例；运行 100 题时，将运行和评分命令中的 `--tasks "$TASK_IDS"` 同时改为 `--tasks all`。

```bash
TASK_IDS=$(python -m scripts.benchmark.mini50 --print-tasks) || exit 1
BASELINE=react  # 或 scitoolagent

python cli.py run --baseline "$BASELINE" \
  --dataset mini-100 --tasks "$TASK_IDS" --backend api --model deepseek-flash \
  --embedding-backend local --concurrency 2 \
  --output "results/baselines_mini50/$BASELINE/predictions.json"

python cli.py score --dataset mini-100 --tasks "$TASK_IDS" \
  --predictions "results/baselines_mini50/$BASELINE/predictions.json" \
  --output "results/baselines_mini50/$BASELINE/scores.json"
```

SciToolAgent 使用自身的工具图谱与向量检索；ReAct 不执行向量检索。生成后端同样支持 `api`、`vllm` 和 `local`，配置方式见[部署说明](../../docs/setup.md)。

## 已有结果的保留

旧六组的 17 条完整结果及 12 个暂停中的尝试均保留，所涉及的 8 个题号都在本选题内。保留题号不代表可直接将不同框架版本的成绩混合：已有完整结果需要核对代码与配置是否可比；暂停中的尝试不能直接恢复后当作连续计时，因为其中包含长时间人为暂停。原始 trace、dataset 与摘要不得改写。

验证选题，不会调用模型：

```bash
python -m scripts.benchmark.mini50 --verify
```
