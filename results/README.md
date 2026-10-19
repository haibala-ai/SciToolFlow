# 实验输出

每次实验使用独立目录保存预测、轨迹和分数。模型运行产物默认不提交到 Git；仓库仅保留本说明及工具静态预检记录。

```text
results/<experiment>/
├── predictions.json             # 每题状态、科学调用与最终答案
├── trajectories/                # 逐步模型决策及真实工具结果
├── progress.json                # 已记录、已提交和正在运行的任务
├── experiment.json              # 使用实验流水线时记录各阶段
├── scores.json                  # 规则评分
├── scores_review_requests.json  # 需要语义复核的证据
└── reviewed_scores.json         # 显式应用复核后的评分
```

运行示例与指标说明见[项目 README](../README.md)，评分协议见[测评文档](../evaluation/README.md)。提交答案的数量不等于正确答案数量；规则分与可选 LLM 复核分分别报告。

执行 `python scripts/index_results.py` 可生成本机实验索引 `results/index.json`，原始轨迹和哈希保持不变。中断实验只应在代码、题库和运行配置一致时续跑。

[工具静态预检记录](reports/tool_preflight.json) 来自记录时的开发部署，用于检查入口、资源声明、图谱和向量关联，不保证其他机器已配置资源，也不代替所有外部接口的实时调用。重新生成执行：

```bash
python scripts/check_foundation.py
```
