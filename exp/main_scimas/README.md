# SciMas 主实验：DeepSeek · Mini-200

本目录保存本次 **SciMas × DeepSeek 官方 API × Mini-200** 的全部实际运行结果：200 份主轨迹、原始预测与评分、逐题资源消耗、目录内 46 份工具产物、启动配置、日志及事后诊断。主实验中的失败题全部保留。

**SciMas 代码版本：[`d6246dc18bf73f696e6d7551e8c0fb52705b9572`](https://github.com/haibala-ai/SciToolFlow/commit/d6246dc18bf73f696e6d7551e8c0fb52705b9572)。** 本次记录的 216 个 actor 代码、配置和数据文件哈希均已与该提交核对一致。它是通信与框架可靠性修复之前的实验，不能标注成后续修复版的模型成绩。

## 实验配置

| 配置 | 本次实际设置 |
| --- | --- |
| Baseline／代码 | SciMas／`d6246dc18bf73f696e6d7551e8c0fb52705b9572` |
| 题库 | Mini-200，全量 200 题，四个学科各 50 题 |
| 模型 | `deepseek-flash` |
| 后端／接口 | API／`https://api.deepseek.com` |
| 启动环境 | `SciTool-Unified`，Python 路径与完整命令保存在 configuration.json |
| 生成网络 | `httpx`，`trust_env=false`，官方直连 |
| 连接／请求超时 | 10 秒／600 秒 |
| 建连重试 | 至多两次额外重试；原客户端不重放可能已计费的读写中断 |
| 同时运行任务 | 2 |
| 单题工具并行 | 4；CLI `max_actions=8`，实际仍受工具并行槽数约束 |
| 上下文保护 | 单角色请求最多 1,500,000 字符 |
| 单次输出上限 | 65,536 token |
| 每题共享生成请求上限 | 400 次，覆盖全部角色 |
| 每题墙钟安全截止／单工具超时 | 7,200 秒／180 秒 |
| 初始规划／协议纠错／局部修复 | 10／3／2 |
| 瞬时工具重试／最大 map 展开 | 1／128 |
| 连续相同工具同参数限制 | 10 步 |
| 格式保护 | `answer_schema_guard=true`、`protocol_schema_guard=true` |
| 采样 | 未显式指定 temperature、top_p、seed 等；不能推断服务端默认值 |
| 实验开始／结束（北京时间） | 2026-11-05 21:33:02／2026-11-06 09:06:47 |

完整配置见 [configuration.json](configuration.json)，原始设置另保留在压缩预测的 `settings` 及 [历史启动元数据](metadata/raw_run/experiment.json) 中。

`max_input_tokens=40960` 是原始 CLI 记录字段，不能将它误写为本轮 API 请求被硬限制为 40,960 token；本轮角色实际按字符保护上下文。`enable_model_thinking=false` 也不表示 DeepSeek 没有 reasoning：该开关主要针对本地／vLLM，本轮 API 响应中的 reasoning 字段及用量仍照实保存。

## 原始结果

| 指标 | 通过题数／总题数 | 比例 |
| --- | ---: | ---: |
| 运行完成率 | 82／200 | 41.0% |
| 工具规划准确率 | 70／200 | 35.0% |
| 答案准确率 | 79／200 | 39.5% |

| 学科 | 题数 | 运行完成 | 工具规划通过 | 答案通过 |
| --- | ---: | ---: | ---: | ---: |
| 化学 | 50 | 28 | 23 | 26 |
| 材料 | 50 | 18 | 17 | 18 |
| 生物 | 50 | 19 | 16 | 18 |
| 机器学习／数理 | 50 | 17 | 14 | 17 |

评分分母固定为 200。工具规划与运行完成独立判断，本轮有 5 道未完成任务的已有执行证据通过规划判定。[scores.json](scores.json) 保持本次原始评分；[summary.json](summary.json) 提供配置身份、统计和数据完整性信息。

本轮记录 5,308 次生成请求、2,380 次科学工具调用和 218 次 DescribeTools 调用。已知输入为 108,820,916 token，已知输出为 13,085,665 token；87 次失败请求缺少 usage，不能按零用量或零费用处理。

## 数据目录

```text
main_scimas/
├── README.md
├── configuration.json          实验代码版本与完整配置
├── summary.json                原始成绩、学科统计、资源小计及局限
├── task_results.jsonl          200 题索引：成绩、失败原因、资源和轨迹位置
├── predictions.json.gz        原始预测文件，解压后逐字节不变
├── predictions.portable.json  便携预测：仅调整轨迹路径和压缩文件校验值
├── scores.json                原始评分，逐字节不变
├── task_metrics.json          原始逐题资源统计，逐字节不变
├── trajectories/              200 份无损压缩轨迹及 46 份目录内工具产物
├── logs/                      原始生成与评分日志
├── metadata/
│   ├── actor_file_hashes.json 原运行记录的 216 个依赖文件哈希
│   ├── config_snapshot/       实验版本的公开 API profile 与环境路由
│   ├── dataset_snapshot/      本轮公开题目及题库元数据快照
│   ├── raw_run/               历史实验、启动、进度、监控与脚本快照
│   └── empty_directories.json 原目录中的空工作目录清单
├── diagnostics/               本轮失败与评分诊断及离线核验记录
├── verification.json          归档完整性核验结果
└── manifest.json              原文件与归档文件的大小、映射和 SHA256
```

原始运行结果约 908.5 MB，采用逐轨迹 gzip 无损存储。每份主轨迹解压后的 SHA256 均与原始预测中的 `trace_sha256` 一致，200 份轨迹的任务身份、状态、答案及工具 observation 也已核验。不会将失败轨迹补成成功轨迹。

原始文件中的绝对路径作为历史证据保留；定位归档数据使用 `task_results.jsonl` 的 `trajectory_file` 相对路径。`predictions.portable.json` 仅将 `trace_path` 改为归档相对路径，将 `trace_sha256` 改为实际 gzip 文件哈希；其余字段不变，并且已经过 200 题证据认证。原始预测另有完整保留。

`metadata/raw_run` 中脚本与进度是历史快照，不是当前正在运行的服务或启动入口。Python 缓存和进程锁不属于运行结果，排除项明确记录在 manifest；空目录不含科学数据，其路径另行保存。原 `results/deepseek_scimas_mini_20261105_212725_c2` 仍保留。

## 查看单题轨迹

从项目根目录执行，不调用模型或科学工具：

```python
import json
from pathlib import Path
from evaluation.integrity.traces import read_trajectory

root = Path("exp/main_scimas")
rows = [json.loads(line) for line in (root / "task_results.jsonl").read_text().splitlines()]
row = next(item for item in rows if item["id"] == "SMAS-0001")
trace = read_trajectory(root / row["trajectory_file"])
print(row["status"], row["tool_plan_correct"], row["answer_correct"])
print(trace["steps"][0])
```

`trace` 内保留每步角色请求、原始模型响应、实际工具输入输出、任务图版本、审查、修复和资源账本。`.gz` 只改变存储方式，不裁剪内容。

## 复核评分与解释边界

便携预测支持原评分入口，但完整复现应使用上述 **d6246dc** 代码和对应数据版本。在当前修复后的代码上，旧实验的 actor 指纹不一致会被拒绝；不要修改指纹来强行通过。建议在独立 worktree 中检出实验版本，并用归档文件的绝对路径调用 `cli.py score --dataset mini --predictions .../predictions.portable.json --output /tmp/main_scimas_scores.json`。

本轮采用历史 **task-metrics.v1 墙钟计时**，包含通信故障等待，未按后来的 v2 口径追溯扣减。逐题调用数和 token 原样保留。

118 道未完成题中有 89 道通信终止，此外存在已核验的框架误终止、Reviewer 误判和评分路径／答案契约问题。详见 [diagnostics/README.md](diagnostics/README.md)。这些局限是主实验记录的一部分；本目录未重跑模型、未剔除失败题、未改写原始分数，不能用这轮结果单独推断模型的纯科学能力。
