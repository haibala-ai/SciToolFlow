# 实时监控

ReAct、SciToolAgent、SciMas 及其消融实验通过统一运行入口自动启动监控。`cli.py plan` 的建图阶段也使用同一监控。无需额外配置模型、账号或 tmux 窗口。

每个实验的监控位于对应结果目录下。例如输出为 `results/my_run/predictions.json`，则查看：

```text
results/my_run/
├── predictions.json
├── task_metrics.json
├── progress.json
├── trajectories/
└── monitor/
    ├── monitor.md       # 可直接打开的实时监控文档
    ├── monitor.json     # 机器可读状态
    └── monitor.log      # 监控进程日志
```

打开 `monitor/monitor.md` 即可查看。文件默认每 **10秒**原子刷新，更新时不会暴露半写入内容。编辑器需允许外部文件变更刷新。

## 显示的信息

- 当前 baseline、消融变体、模型、题库及任务／工具并发设置。
- 已结束、正常完成、失败／中断、活动及排队任务数。
- 活动任务的最后阶段、模型请求是否等待响应、墙钟已运行秒数及检查点更新时间。
- 输入和输出 token 分开统计；科学工具、DescribeTools 和模型请求数分别显示。
- 失败原因及已有的评分摘要。早于最新任务记录的评分会标记为过期，避免把上一次结果当作本次成绩。

正常完成不表示答案正确。科学得分以正式评分文件为准。活动任务的成本是最新检查点中的已知部分；缺失 token 用量明确标记为不完整，不能把已知小计当作最终总量。重试历史仍保存在 `predictions.json` 的 `attempt_history` 中。

token 统计沿用任务账本中的生成模型用量，embedding 的调用与用量仍由原检索账本单独记录。

建图阶段展示已完成的建图数、活动题目与已记录请求数；未保存到检查点的模型用量保持未知，不估算 token。

## 生命周期与计时

监控在独立进程中只读检查点，不调用 LLM、embedding 或科学工具，不修改预测、原始轨迹和任务资源账本。它主要读取紧凑的 `progress.json`、`task_metrics.json`，只读取活动任务有变化的轨迹，并限制单份轨迹读取大小为64 MiB。较大或暂不可读的活动轨迹会明确提示，仍可查看其原始文件。

监控不加入任务耗时统计，也不重算通信等待时间。界面中的墙钟已运行时间仅用于观察进展；正式运行时间、通信扣除及 token 数据沿用原任务账本。监控进程仍有少量限频文件读取开销。

同一结果目录只允许一个监控写入进程。直接运行 baseline 时，生成结束、异常退出或通信熔断收尾后保存最后快照并退出。使用 `python -m scripts.benchmark.run_benchmark` 时，监控覆盖等待模型、生成和评分阶段，直到实验结束。监控故障不会改变模型决策或中止任务；日志保存在 `monitor/monitor.log`。

## 已有运行与手动刷新

为已有结果生成一次快照，或在分步执行评分后刷新评分摘要：

```bash
python -m baselines.common.monitor --directory results/my_run --once
```

持续观察已有实验，可指定刷新间隔；新版运行会自动提供运行进程PID：

```bash
python -m baselines.common.monitor --directory results/my_run --interval 10
```

旧版运行缺少进程PID时，可显式提供实际运行器PID：

```bash
python -m baselines.common.monitor --directory results/my_run --owner-pid 12345
```

若已有监控正在写入，上述命令不会启动第二个写入者。监控不修改旧运行指纹，因此可以旁路观察旧实验；代码更新后的模型续跑仍遵循原有的严格版本检查。
