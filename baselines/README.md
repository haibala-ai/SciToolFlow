# Baseline

三个 baseline 读取相同的公开任务，使用同一工具执行器、资源策略、答案格式校验和预测协议，由独立评分器处理；它们不读取金标准。

| 目录 | 职责 |
| --- | --- |
| [react/](react/README.md) | 按学科工具名发现、按需 DescribeTools、ReAct 决策循环 |
| [scitoolagent/](scitoolagent/README.md) | 原论文策略对应的工具图谱检索、候选规划与执行 |
| [scimas/](scimas/README.md) | SciMas：独立端口图谱、三角色协作、并行 DAG 执行、科学审查与局部修复 |
| common/ | 批处理、任务会话、资源计数、重复调用检测与答案格式辅助 |

从项目根目录启动：

```bash
python cli.py run --dataset full --baseline react --backend api --model YOUR_MODEL \
  --tasks FLOW-0285 --output results/react_demo/predictions.json
python cli.py run --dataset mini --baseline scitoolagent --backend vllm --model YOUR_MODEL \
  --tasks SMAS-0103 --output results/scitoolagent_demo/predictions.json
```

`--output` 指向预测 JSON 文件，其所在目录容纳实验配置、进度、轨迹和工具产物。API 和本地服务均可自由选择模型，账号与部署步骤见[安装与部署](../docs/setup.md)。SciToolAgent 的检索 embedding 独立于生成模型，必须与工具索引身份一致。

各策略的 `run.py` 提供独立命令入口，`runtime.py` 实现策略循环。公共模型客户端位于 `src/models/`；工具通过 `tools.execute` 统一执行；任务加载和评分分别位于 `tasks/` 与 `evaluation/`。相同实验的续跑要求代码、公开输入、模型和采样配置指纹一致。

查询、规划、运行与评分默认使用`--dataset mini`，题号为SMAS-0001..0200。Full-500用`--dataset full`显式选择；旧Mini接口已移除。评分使用与运行相同的题库和任务选择，说明见[Mini-200](../tasks/mini/README.md)。

SciMas 与其他baseline共用Mini-200默认入口、Full-500显式入口、模型后端和资源策略；`python cli.py plan`可以单独检查规划。

Mini-200 使用同一运行接口：`python cli.py run --dataset mini --baseline react --backend vllm --model YOUR_MODEL --tasks all --output results/react_mini/predictions.json`。评分用相同题库选择：`python cli.py score --dataset mini --predictions results/react_mini/predictions.json --output results/react_mini/scores.json`；三项指标及来源说明见[Mini-200](../tasks/mini/README.md)。
