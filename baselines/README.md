# Baseline

两个 baseline 读取相同的公开任务，使用同一工具执行器、资源策略、答案格式校验和预测协议，由独立评分器处理；它们不读取金标准。

| 目录 | 职责 |
| --- | --- |
| [react/](react/README.md) | 按学科工具名发现、按需 DescribeTools、ReAct 决策循环 |
| [scitoolagent/](scitoolagent/README.md) | 原论文策略对应的工具图谱检索、候选规划与执行 |
| common/ | 批处理、任务会话、资源计数、重复调用检测与答案格式辅助 |

从项目根目录启动：

```bash
python cli.py run --baseline react --backend api --model YOUR_MODEL \
  --tasks FLOW-0285 --output results/react_demo/predictions.json
python cli.py run --baseline scitoolagent --backend vllm --model YOUR_MODEL \
  --tasks FLOW-0285 --output results/scitoolagent_demo/predictions.json
```

`--output` 指向预测 JSON 文件，其所在目录容纳实验配置、进度、轨迹和工具产物。API 和本地服务均可自由选择模型，账号与部署步骤见[安装与部署](../docs/setup.md)。SciToolAgent 的检索 embedding 独立于生成模型，必须与工具索引身份一致。

各策略的 `run.py` 提供独立命令入口，`runtime.py` 实现策略循环。公共模型客户端位于 `src/models/`；工具通过 `tools.execute` 统一执行；任务加载和评分分别位于 `tasks/` 与 `evaluation/`。相同实验的续跑要求代码、公开输入、模型和采样配置指纹一致。
