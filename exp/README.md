# 实验数据

| 实验 | 模型 | 题库 | SciMas 代码 | 说明 |
| --- | --- | --- | --- | --- |
| [main_scimas](main_scimas/README.md) | DeepSeek 官方 `deepseek-flash` | Mini-100；含固定 Mini-50 对照 | 以 `2ade7929` 为基础；精确源码见归档快照 | 正式主实验结果、100 条轨迹、评分与资源指标 |
| [ablation](ablation/README.md) | DeepSeek 官方 `deepseek-flash` | 固定 Mini-50 × 5 组 | 本轮 `2ade7929edfd4db5a324d7f33d230b0b16b43530`；逐批次 commit 见实验配置 | 五组消融结果、250 份完整轨迹、评分、资源指标与复核资料 |

具体分数、计时口径、基础设施失败和完整性说明均以各实验目录为准。归档数据不覆盖当前运行代码，不把历史实验与后续框架版本混用。
