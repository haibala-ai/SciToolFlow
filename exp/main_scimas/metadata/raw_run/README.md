# SciMas Mini-200 · DeepSeek 官方直连

本次运行全部 200 题，最多同时运行 2 个任务；全部记录后自动离线评分。

## 实时查看

- [monitor.md](monitor.md)：每 10 秒刷新，可读进度、活动任务阶段、失败原因和已知成本小计。
- [monitor.json](monitor.json)：同一监控的机器可读数据，含刷新序号与时间。
- [progress.json](progress.json)：原始批次调度状态，任务开始和结束时更新。
- [task_metrics.json](task_metrics.json)：已结束任务的逐题时间、工具调用数、输入及输出 token。
- [experiment.json](experiment.json)：生成／评分阶段、进程和实际启动参数。
- [generating.log](generating.log)、[scoring.log](scoring.log)：生成与离线评分日志。
- [predictions.json](predictions.json)、[scores.json](scores.json)：正式预测与结束后的统一评分。

监控只读取紧凑统计和最新活动轨迹，按文件修改时间缓存，最多保留活动任务的原始轨迹缓存。不调用模型，不改写轨迹或正式任务计时；活动任务的 token 仅为最后检查点的已知小计，未知用量不会当作零总量。

## 配置

| 参数 | 设置 |
| --- | --- |
| 数据集／题量 | mini／200，全部任务 |
| Baseline | SciMas |
| 模型／接口 | deepseek-flash／https://api.deepseek.com |
| 生成网络 | 官方直连，忽略代理环境；embedding 独立配置 |
| 同时运行任务数 | 2 |
| 单题工具并行 | 4 |
| 上下文字符保护 | 1,500,000 字符 |
| 单次输出上限 | 65,536 token |
| 每题共享模型请求额度 | 400 |
| 每题时间上限 | 7,200 秒 |
| 连接／响应等待 | 10／600 秒 |

不另设 32 步硬门槛。运行失败会保留原因、已知用量及已有轨迹；不自动重跑失败题。最终评分分母固定为 200，不把失败题删出统计。

## tmux

```bash
tmux attach -t scimas-mini-20261105_212725
```

`run` 窗口运行生成和评分；`monitor` 窗口显示 10 秒监控心跳。任务与窗口均在服务器运行，不依赖当前聊天或终端连接。

## 轨迹与案例

原始记录位于 `trajectories/<任务ID>-<run_id>/trajectory.json`，活动任务在 monitor.md 中有直接链接。逐步消息、原始模型响应、决策、工具输入输出、图修复与资源账本都在其中。需要可读案例时，在任务结束后按需执行：

```bash
/data/wuchenmin/Application/anaconda3/envs/SciTool-Unified/bin/python -m baselines.scimas.trajectory /path/to/trajectory.json
```

## 中断后续跑

只在原进程已经停止、源码与配置身份一致时执行：

```bash
cd /data/wuchenmin/Project/ToolKG/SciToolFlow
/data/wuchenmin/Application/anaconda3/envs/SciTool-Unified/bin/python /data/wuchenmin/Project/ToolKG/SciToolFlow/results/deepseek_scimas_mini_20261105_212725_c2/run_experiment.py --resume
```

监督进程带互斥锁，防止重复启动同一实验。续跑保留已有成功及失败预测，只继续尚未返回预测的题目；原始轨迹不覆盖。若监控进程已退出，另在终端或 tmux 窗口执行：

```bash
/data/wuchenmin/Application/anaconda3/envs/SciTool-Unified/bin/python /data/wuchenmin/Project/ToolKG/SciToolFlow/results/deepseek_scimas_mini_20261105_212725_c2/monitor.py
```
