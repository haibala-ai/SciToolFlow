# 参考答案与执行证据

本目录是评分器的数据入口。Agent 只读取公开任务、附件和工具契约，不读取这里的参考答案或科学判据。

| 文件／目录 | 内容 |
| --- | --- |
| [references.jsonl.gz](references.jsonl.gz) | 500 条主参考：科学判据、答案、主轨迹位置及其生成／独立审核记录 |
| [reference_runs.jsonl.gz](reference_runs.jsonl.gz) | 281 条不重复的额外参考运行；按题号关联主参考的科学判据 |
| [trajectories/](trajectories/) | 按题号组织的 781 条完整真实轨迹，无损 gzip 存储 |
| [file_identities.json](file_identities.json) | 公开输入文件的内容身份与明确登记的路径别名 |
| [artifacts.tar.gz](artifacts.tar.gz) | 工具输出附件包 |

每个题号目录包含 `primary.json.gz` 和可选的 `variant_01.json.gz` 等额外执行。主参考与额外参考使用同一科学判据；额外运行数量不等于不同科学算法的数量。生成信息和批准审核内联存储在相应参考记录中，保留审核者、检查项、科学说明及任务／轨迹／判据哈希，不依赖过程目录或旧输入快照。

```bash
# 查看答案、科学判据、独立审核或完整主轨迹
python -m evaluation.authoring.inspect --task FLOW-0001 --section expected_answer
python -m evaluation.authoring.inspect --task FLOW-0001 --section evaluation
python -m evaluation.authoring.inspect --task FLOW-0001 --section review
python -m evaluation.authoring.inspect --task FLOW-0001 --section trace

# 核验数据包；进一步核验所有额外参考
python cli.py validate
python -m scripts.references.validate_release
```

压缩不删除或截断任何观测、参数、程序或答案。参考题目、答案与科学判据保持独立：改变题文、输入、答案结构或判据后，应重新执行与独立审核，不能只修改哈希声称参考仍然有效。任务分类统一见 [CATEGORIES.md](../../tasks/CATEGORIES.md)。
