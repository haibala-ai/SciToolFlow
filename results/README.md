# 实验输出

每个实验使用独立目录，包含以下文件：

| 文件／目录 | 内容 |
| --- | --- |
| predictions.json | 按任务保存的提交答案、完成状态及轨迹位置 |
| experiment.json | baseline、模型、采样、资源设置与续跑指纹 |
| progress.json | 批次进度，包含失败记录和活动任务 |
| trajectories/ | 每次任务执行的完整轨迹 |
| tool_artifacts/ | 本次执行生成的工具输出文件 |
| scores.json | 总体指标与逐题判定；评分输出文件名可自定义 |
| scores_review_requests.json | 与评分文件配套的待审方法／证据记录 |

`--output results/<experiment>/predictions.json` 指定实验位置。原始轨迹与预测是评分证据，不要只保留汇总分数。续跑使用 `--resume`，要求代码、任务、工具及模型设置的指纹一致；修改后创建新目录。

本机结果默认不提交到版本控制。`python -m scripts.benchmark.index_results` 可生成本机浏览索引；`reports/tool_preflight.json` 是静态工具预检结果，不代表所有外部服务实时可用。正式参考与金标准位于 [evaluation/data](../evaluation/data/README.md)，评分含义见[评分细则](../evaluation/README.md)。
