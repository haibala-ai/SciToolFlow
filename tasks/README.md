# SciToolFlow公开任务

默认公开题库为[Mini-200](mini/README.md)，**四学科各50题**。保留的Full-500源库版本为`20261026`，化学143、材料144、生物／生态111、机器学习／数理102题。当前不划分dev/test；重复使用研究队列不应被解释为独立测试样本。

| 文件 | 内容 |
| --- | --- |
| [questions.jsonl](full/questions.jsonl) | Full-500源题库，一行一题，按FLOW-0001至0500排列 |
| [index.json](full/index.json) | ID、学科、任务类别、行号、题目预览与附件标记 |
| [schema.json](full/schema.json) | 公开任务记录结构 |
| [assets](full/assets/)与[asset_manifest.json](full/asset_manifest.json) | 836 份已登记附件（当前 500 题使用其中 676 份）及SHA256、字节数和来源 |
| [metadata.json](full/metadata.json) | 当前版本、学科数与统一评分政策 |
| [mini/](mini/README.md) | 原Special-100与Full精选100题组成的200题，四学科各50题，使用统一运行与三指标评分 |
| [mini-100/](mini-100/README.md) | 从Mini-200固定随机抽取的100题，用于消融实验，使用`--dataset mini-100` |

每题包含`id`、`domain`、`question`、`inputs`、`files`和`answer_schema`。`Parameter`是inputs的兼容JSON字符串，`unit_annotations`补充必要单位与整题范围说明。仅含非空 `description` 的对象说明整题约定；字段级单位标注必须含可解析的 `path`。加载器将asset://URI解析为经过内容哈希校验的本地文件。

answer_schema规定字段、类型、已公开的维度和比较语义，不含正确值。标识符和科学数组的次序由题文与契约规定；无序集合和数值容差通过x-scoring-semantics明确。不要从展示模板的示例数组长度推断正确答案。

```bash
python cli.py task SMAS-0103
python cli.py task --domain MachineLearning
python -m scripts.benchmark.index_tasks
```

运行资源由统一实验配置管理：默认每题 400 次生成请求、7,200 秒，不在题目中保存逐题执行额度。科学调用、DescribeTools 与 think 无独立次数上限；各次执行仍记录并参与相应的成本统计。题文规定的实验次数、采样次数、样本量等科学约束仍须遵守。详见[运行资源策略](../docs/execution_policy.md)。

Agent只读取公开题目、附件、工具契约及运行配置。Full的私有评分数据位于`evaluation/data/`，Mini的参考副本位于`tasks/mini/evaluation/`；两者均不提供给Agent。[评分说明](../evaluation/README.md)解释证据边界，[题库分析](../docs/benchmark_analysis/README.md)分别展示Mini与Full的学科、工具覆盖和参考分布。旧任务版本的预测不能套用新评分器。

## 加载与格式校验接口

`assets.py` 负责解析公开 `asset://` 附件并核对内容哈希，`schema.py` 提供公开答案格式的构建和校验函数，`datasets.py` 统一选择 mini／mini-100／full 并校验编号映射。这些公开加载器只处理公开任务，不读取参考答案。`mini/schema.json` 与 `full/schema.json` 是任务记录格式，`schema.py` 是 Python 校验实现，职责不同。

Full任务按设计目标分为高难度题、工具组合题和正常题，完整题号与摘要统一见 [CATEGORIES.md](full/CATEGORIES.md)。`full/index.json`的category字段便于程序分组；Mini的独立编排题保留自身难度层级，不将两种标签直接混用。

## Mini-200 科学编排集

[Mini-200](mini/README.md) 保留现有100题，再从Full逐题选出100题，合计四学科各50题。公开编号为SMAS-0001～SMAS-0200；[ids.tsv](mini/ids.tsv)保留来源映射，原始参考轨迹不重编号。查询、运行、规划与评分默认用`--dataset mini`，Full-500使用`--dataset full`显式选择；主指标为运行完成率、工具规划准确率与答案准确率。

200条Mini主参考共2242次科学调用，每题均值11.21次、中位数9次，成功覆盖154／472个科学工具。166题的评分能力图有多层依赖；这些是参考与结构统计，不是模型性能或实测并行加速比。[Mini画像与测试](mini/README.md#题库画像)提供分学科统计、运行说明和映射评分机制。
