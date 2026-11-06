"""Render the delivered Special-100 overview from accepted release statistics."""
from pathlib import Path
import json
BASE=Path(__file__).resolve().parents[1]


def generate():
    m=json.loads((BASE/'metadata.json').read_text());assert m['task_count']==100
    review=json.loads((BASE/'evaluation/task_review.json').read_text())
    multistage=review['graph_fit_counts']['multistage_dependency_graph']
    panels=review['graph_fit_counts']['parallel_evidence_panel']
    narrower=len(review['complex_graph_strengthening_candidates'])
    text=f'''# SciMas Special-100

**100 道面向图式科学工具编排的分层题目**：四个学科各 25 道，包含 28 道较难题、52 道中等题、20 道基础题。题集独立于 Full-500 与 Mini-200，版本为 `scimas-special-100-v2`。

题目围绕共享前提、独立子任务、方法分叉和科学结果汇合设计。SciMas 可以利用任务图复用共同状态并调度就绪分支；串行执行仍需保持相同的对象身份、参数和跨分支证据。基础题缩小科学问题的范围，仍保留实际的分解与核验工作。难度标签来自逐题设计审查，尚未通过多模型表现校准。

![学科、难度与真实参考工作量](overview.svg)

这是有意面向 SciMas 机制的独立研究题集，用于研究图式执行的适用条件。**适配性证据不等于已测得的性能优势**；端到端成功率、耗时及相对基线收益需要另外运行实验。各方法使用相同的公开输入与评分规则。

## 学科与难度

| 学科 | 较难 | 中等 | 基础 | 合计 |
| --- | ---: | ---: | ---: | ---: |
| 化学 | 7 | 13 | 5 | 25 |
| 材料 | 7 | 13 | 5 | 25 |
| 生物／生态 | 7 | 13 | 5 | 25 |
| 机器学习／数理 | 7 | 13 | 5 | 25 |
| **合计** | **28** | **52** | **20** | **100** |

每题均记录科学目标、共享前提、独立子任务、汇合判断和解释边界，见 [分层与适配说明](strata.json) 与 [逐题目录](catalog.md)。题目不是通过替换数据批量生成的同一算分模板；部分题目共享方法族，但比较对象、科学判断或方法边界不同。

按当前评分能力图，**{multistage} 题有多层工具依赖，{panels} 题主要是单层并行证据面板**。科学结果的汇合可能由模型完成，因此能力图层数不等于完整任务图层数；单层面板也有实际并行工作，但不能统一称为复杂多阶段编排。其中 {narrower} 道中等／较难题的优势论证主要限于并行证据组织，已在[逐题复核](review.md)中单独标记，未宣称所有 100 题都能产生很大的相对性能收益。

| 代表题 | 科学问题 | 可利用的任务图结构 |
| --- | --- | --- |
| SMAS-0008 | 指纹邻域如何改变化合物空间的传播结果 | 每种指纹矩阵共享给邻域判断、谱分析与传播链；两种表示独立 |
| SMAS-0054 | 距离和形状不变是否意味着镜像可由正旋转重合 | 同一固定对应，分叉检查原子库存、距离、形状和刚体拟合后联合判断 |
| SMAS-0060 | 元素约束下的最优混合与非唯一配料见证 | 分子式与质量分数共享给优化器及独立元素平衡核验 |
| SMAS-0063 | 如何区分混合物的质量分数与体积分数 | 各纯组分并行解析，反演后以元素守恒和比体积两路核验 |
| SMAS-0072 | 仪器响应校准后能否可靠拆分合成混合谱 | 多响应拟合并行，共同设计矩阵接秩检验、反演及独立正向验证 |
| SMAS-0075 | 目标生境权重、plot 和 quadrat 为什么给出不同结论 | 多端点与不同估计量并行，保留独立采样单位和共同目标权重 |
| SMAS-0083 | 缺失非核心残基是否能证明共同核心变形 | 质量检查、共同核心提取、全记录质心与刚体比较分开汇合 |
| SMAS-0090 | 系数不唯一时，哪些科学对比量仍可识别 | 最小二乘与 SVD 证据独立，投影器共享给多个对比的适用域判断 |
| SMAS-0094 | 名义最优模型在部署群体不确定时是否仍最优 | 多模型／群体损失并行，同一可行权重集合支持各路最坏风险与核验 |
| SMAS-0097 | 高轮廓系数是否只是排除了更多样本 | 并行密度分区；按簇数门控质量计算，再联合检查样本覆盖率 |

合成控制、静态结构和固定计算输出均明确其科学范围，不据此声称实验效果、热力学稳定性、因果关系或真实生物功能。固定 Q-Chem／NBO 输出保留原始来源说明；任务不会把已有输出说成新执行的量子计算。

## 参考与验收

全部 100 道题都有真实 ReAct 参考及独立科学复核。本轮相对于 Special-100 v1 重写了 43 道公开题面，全部使用新上下文参考；其余 57 题复用通过当前题目身份、科学判据和来源检查的参考。参考由 **GPT-6.1 Sol** 在新上下文中经生产工具 broker 逐步生成，未调用模型 API。解题者只接触公开问题、当前请求与工具反馈，不读取评分器、参考答案或其他题的轨迹。这里的隔离是信息边界与工具进程隔离，不是独立操作系统账号。

逐题检查覆盖标题、正文、输入、答案格式及公开附件。删除了 SMAS-0033 直接写出的布尔答案、少数题目的具体工具接口名和提前暗示结论的标题；必要的科学定义、实验条件、单位、容差与输出字段保留。SMAS-0073 原先只需一次源读取，现改为三份独立转录记录的账目审计；这些质量控制数据明确标为合成转录控制，不冒充新量子计算。评分器同时修复了重复要求原子计数／SELFIES 解码、拒绝合法批处理或等价线性代数求值顺序的问题；科学阈值与拒绝错误结果的边界保持明确。

不接受一次通用代码调用包办主要科学分析的参考；领域计算需要真实工具证据。合法的批量调用、同输入复用和普通算术整理可以保留。原始轨迹按字节身份压缩保存，重试不会被拼接或改写成一次成功轨迹。

验收参考共记录 **{m['reference_scientific_calls']} 次科学工具调用**，涉及 **{m['covered_scientific_tools']} 种实际成功调用的工具**。每题均在实际适用节点中具备至少两个独立就绪、对应不同观测且已审查执行隔离条件的调用；统计排除不适用分支和重复观测。能力图宽是结构量，不能直接解释为实际并发度或加速比。

工具层对 **{m['paired_verified_tool_count']} 种本地工具完成 {m['paired_verified_calls']} 次成对成功调用**，检查生产 worker 的独立目录、重叠调度窗口、输出一致性及当前源码身份，见 [执行隔离证据](../../../tools/graph/scimas/parallel_review.json)。SciMas 图谱补充的是通用契约与执行知识，包含 {m['source_reviewed_tool_annotations']} 份来源绑定注释，不含本题答案、评分阈值或专属参考路径。功能文本未变化，既有 embedding 经身份校验复用，新增 embedding API 请求为 0。未审查的并发安全性和未测量成本继续保持未知。

参考自检通过只说明题目与评分器一致，**不是 SciMas 实验成绩**。逐题验收与错误答案变异检查见 [acceptance.json](evaluation/acceptance.json)。

## 运行与评分

从项目根目录执行，先按[部署说明](../../../docs/setup.md)准备环境、工具资源和生成模型。生成模型支持 API、本地 vLLM 服务及 local worker；使用哪种本地模型由实验者决定。SciToolAgent 和 SciMas 的检索 embedding 配置独立于生成模型。

```bash
# 单题：baseline 支持 react、scitoolagent、scimas
python evaluation/authoring/special100/run.py --baseline react --backend vllm --model YOUR_MODEL \\
  --tasks SMAS-0090 --output results/special_react/predictions.json

# 全部 100 题；API 与本地模型共用题集和评分入口
python evaluation/authoring/special100/run.py --baseline scimas --backend api --model YOUR_MODEL \\
  --tasks all --output results/special_scimas/predictions.json

python evaluation/authoring/special100/evaluate.py \\
  --predictions results/special_scimas/predictions.json \\
  --output results/special_scimas/scores.json

# 不调用 LLM：验证公开输入、真实参考、评分与拒绝错误答案的边界
python evaluation/authoring/special100/validate.py
```

默认每题最多 400 次生成请求、7,200 秒。可通过 `--max-model-requests` 和 `--task-timeout` 为所有方法设置相同资源。预测持续保存，轨迹与产物随实验输出保存；新实验使用新输出目录。这一独立入口不改变 full／mini 的运行选择器。

只报告以下三项指标，分母为所选题目数；未提交预测的题目记为失败。评分不调用 LLM。

| 指标 | 单题通过标准 | 含义与边界 |
| --- | --- | --- |
| `runtime_completion_rate` 运行完成率 | 真实运行正常结束 | 独立于答案格式、科学正确性和工具路径 |
| `tool_planning_accuracy` 工具规划准确率 | 实际轨迹满足所有必要能力、适用分支、科学输入约束和数据依赖，且无待审查项 | 必要科学规划的通过率，不按参考串行顺序逐项比对，也不充当耗时或冗余调用指标 |
| `answer_accuracy` 答案准确率 | 所有适用的科学判据通过 | 用已验收参考中的真实证据评价答案，支持数值容差、并列、分区标签等价及可行最优解；不强求逐字 JSON 相同 |

三项分别计算：答案正确不补造工具证据；实际工具规划正确也不能掩盖错误答案。`DescribeTools` 可以正常调用，但不计科学能力与路径。题目所需顺序、单位、方法、门控、空值及容差在公开题面和答案契约中说明。

## 文件入口

| 文件 | 用途 |
| --- | --- |
| [questions.jsonl](questions.jsonl)、`assets/`、[asset_manifest.json](asset_manifest.json) | 100 条公开问题、固定输入与内容哈希 |
| `data.py` | 只加载公开题目并校验附件 |
| `run.py`、`evaluate.py` | 统一调用现有三个 baseline，并计算三项指标 |
| [catalog.md](catalog.md)、[strata.json](strata.json)、`design.json` | 逐题设计与适配审查；不进入 Agent 输入 |
| [review.md](review.md)、[逐题复核 JSON](evaluation/task_review.json) | 每题科学判断、图结构适配、信息泄露检查及保留边界 |
| `evaluation/criteria.jsonl` | 隐藏的 `workflow.v1` 科学和能力判据 |
| `evaluation/references.jsonl`、`evaluation/trajectories/` | 实际参考答案、来源、审查记录与原始压缩轨迹 |
| `evaluation/acceptance.json`、`progress.json` | 最终验收与当前状态 |
| `authoring/` | 设计、构建、独立参考审查与统计；baseline 运行时不加载 |
'''
    (BASE/'README.md').write_text(text)

if __name__=='__main__':generate()
