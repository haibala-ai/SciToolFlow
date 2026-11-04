# SciToolFlow公开任务

正式版本为`20261026`：**500题，化学143、材料144、生物／生态111、机器学习／数理102**。当前不划分dev/test；重复使用研究队列不应被解释为独立测试样本。

| 文件 | 内容 |
| --- | --- |
| [questions.jsonl](questions.jsonl) | 唯一正式题库，一行一题，按FLOW-0001至0500排列 |
| [index.json](index.json) | ID、学科、任务类别、行号、题目预览与附件标记 |
| [schema.json](schema.json) | 公开任务记录结构 |
| [assets](assets/)与[asset_manifest.json](asset_manifest.json) | 836 份已登记附件（当前 500 题使用其中 676 份）及SHA256、字节数和来源 |
| [metadata.json](metadata.json) | 当前版本、学科数与统一评分政策 |
| [mini/](mini/README.md) | 面向子任务拆分与并行编排的200题均衡子集，四学科各50题，排除高难度类别 |

每题包含`id`、`domain`、`question`、`inputs`、`files`和`answer_schema`。`Parameter`是inputs的兼容JSON字符串，`unit_annotations`补充必要单位与整题范围说明。仅含非空 `description` 的对象说明整题约定；字段级单位标注必须含可解析的 `path`。加载器将asset://URI解析为经过内容哈希校验的本地文件。

answer_schema规定字段、类型、已公开的维度和比较语义，不含正确值。标识符和科学数组的次序由题文与契约规定；无序集合和数值容差通过x-scoring-semantics明确。不要从展示模板的示例数组长度推断正确答案。

```bash
python cli.py task FLOW-0285
python cli.py task --domain MachineLearning
python -m scripts.benchmark.index_tasks
```

运行资源由统一实验配置管理：默认每题 400 次生成请求、7,200 秒，不在题目中保存逐题执行额度。科学调用、DescribeTools 与 think 无独立次数上限；各次执行仍记录并参与相应的成本统计。题文规定的实验次数、采样次数、样本量等科学约束仍须遵守。详见[运行资源策略](../docs/execution_policy.md)。

Agent只读取公开题目、附件、工具契约及运行配置。金标准、能力依赖、参考与独立审核位于[evaluation](../evaluation/README.md)，不提供给Agent。[500题分析](../docs/benchmark_analysis/README.md)解释学科、工具覆盖、参考来源与限制。旧任务版本的预测不能套用新评分器。

## 加载与格式校验接口

`assets.py` 负责解析公开 `asset://` 附件并核对内容哈希，`schema.py` 提供公开答案格式的构建和校验函数，`datasets.py` 统一选择 full／mini 并校验编号映射。两者只处理公开任务，不读取参考答案。`schema.json` 是任务记录格式，`schema.py` 是 Python 校验实现，职责不同。

任务按设计目标分为高难度题、工具组合题和正常题，完整题号与摘要统一见 [CATEGORIES.md](CATEGORIES.md)。`index.json` 的 category 字段便于程序分组；这些标签不改变评分标准。

## Mini-200 精简集

[Mini-200](mini/README.md) 从非高难度题中选取 200 题，化学、材料、生物／生态和机器学习／数理各 50 题。题文、输入、附件引用、答案格式及原评分保持一致；仅顶层题号重新编号，评分通过映射复用全集金标准。附件继续从本目录解析，Mini 独立编号为 FLOW-0001～FLOW-0200，[ids.tsv](mini/ids.tsv) 保存与全集的映射；查询、运行与评分均使用 `--dataset full|mini`，未指定时为全集。逐题科学目标、共享前提与并行子任务见 [selection.json](mini/selection.json)。
