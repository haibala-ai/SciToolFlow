# SciToolFlow 任务集

这里是 benchmark 的公开入口，共 **500 道多工具任务**。Agent 只能读取本目录的公开输入和工具契约；参考答案与参考轨迹位于 `../evaluation/`，不提供给 Agent。

| 学科 | 任务数 |
| --- | ---: |
| Chemical | 159 |
| Material | 154 |
| Biology | 140 |
| MachineLearning | 47 |

| 文件 | 用途 |
| --- | --- |
| [questions.jsonl](questions.jsonl) | 唯一正式题库，一行一个任务 |
| [index.json](index.json) | 轻量浏览索引：ID、学科、题目预览、所在行、预算和附件标记 |
| [schema.json](schema.json) | 公开任务记录的字段结构 |
| [assets/](assets/) | 公开输入附件；不混入工具生成结果 |
| [asset_manifest.json](asset_manifest.json) | `asset://` 附件 URI、字节数和 SHA256 |
| [metadata.json](metadata.json) | 学科统计、工作流组、覆盖和数据集说明 |

一个任务的结构为：

```json
{
  "id": "FLOW-xxxx",
  "domain": "MachineLearning",
  "question": "任务要求",
  "question_language": "en",
  "inputs": {},
  "files": [],
  "answer_schema": {},
  "unit_annotations": [],
  "max_tool_calls": 32,
  "Parameter": "兼容旧执行器的 inputs JSON 字符串"
}
```

`inputs` 是正式结构化输入；`Parameter` 是保留的兼容字段。`answer_schema` 仅规定答案结构和类型，不含正确值。`max_tool_calls` 是任务工具预算；DescribeTools、think 和 inspect 不占此预算，但分别受 harness 限制。附件由公开加载器校验哈希后解析，不依赖父项目目录。

在 SciToolFlow 根目录查看题目：

```bash
python cli.py task FLOW-0285
python cli.py task --domain MachineLearning
python scripts/index_tasks.py
```

任务的对应关系为：`questions.jsonl[id]` → `evaluation/references.jsonl[id]` → 参考记录的 `reference_trace`。参考记录同时包含金标准、字段评分规则、必要工具路径和证据依赖；新模型轨迹另存 `results/`。

当前没有 dev/test 划分。数据版本为 `20261018-scientific-contract-audit`：500 条逐项审查的修订范围、理由与限制见 [报告](../results/reports/full_run_audit_20261018/README.md)。原始必要路径与工具输出未重生成；部分题意、输入来源/常量、答案契约、参考解释和评分规则已修订，不能沿用旧版本分数。

运行 observation 标签属于可选证据元数据；它们不是必填科学量。题目中的科学单位、对象、数组次序、训练/验证边界和推理比较仍需满足。公开包交给 Agent 时，只提供本目录、工具目录及公开运行配置。
