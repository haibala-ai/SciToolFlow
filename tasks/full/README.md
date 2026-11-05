# SciToolFlow Full-500

完整500题源题库，编号 `FLOW-0001..FLOW-0500`。题文、科学输入与原始参考保持不变；本目录集中存放公开任务、附件、格式、分类索引和元数据。默认公开入口是 [Mini-200](../mini/README.md)，选择本题库需指定 `--dataset full`。

```bash
python cli.py task FLOW-0001 --dataset full
python cli.py run --dataset full --baseline react --backend api \
  --model YOUR_MODEL --tasks all --output results/react_full/predictions.json
python cli.py score --dataset full \
  --predictions results/react_full/predictions.json --output results/react_full/scores.json
```

规划、运行、评分支持相同的题库选择与题号；抽测时为运行与评分指定相同的 `--tasks`。模型配置见[安装与部署](../../docs/setup.md)，Full 的完整 `workflow.v1` 科学与编排评分见[评分细则](../../evaluation/README.md)。

Mini中有100题直接选自本题库，科学内容、金标准与判据保持一致。它们使用Mini题号运行，并由Mini统一报告三项独立指标；这与直接选择Full时的完整报告不同。[映射评分机制](../../evaluation/README.md#mini与full的映射评分)说明固定参考副本、身份校验与指标计算方式。

实际任务输入使用 `asset://`，加载器按登记哈希解析到本目录的 `assets/`。原始来源说明和历史轨迹可能保留采集时的路径；这些记录保持原貌，不作为当前文件入口。

[题目分类](CATEGORIES.md) · [公开记录](questions.jsonl) · [索引](index.json) · [附件登记](asset_manifest.json)
