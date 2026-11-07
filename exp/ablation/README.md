# SciMas 消融实验

本目录保存五组消融在固定 Mini-50 上的正式实验数据：每组 50 题，共 250 次任务结果。保留正常提交、执行失败、完整轨迹与原始评分，不按结果筛选题目。Full 的正式结果保存在 `exp/main_scimas/`；表中配对比较使用其相同 Mini-50 子集。

[实验配置](configuration.json) · [机器可读结果](summary.json) · [完整性校验](verification.json) · [文件清单](manifest.json)

## 实验结果

| 方法 | 运行完成率/% | 编排完成程度/% | 工具选择效率/% | 综合规划分/% | 答案准确率/% | 中位时间/s | 平均时间/s | Avg. Tool Call | Avg. Input Tok | Avg. Output Tok | Avg. Tok |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [Full](../main_scimas/mini50/scores.json) | 92.00 | 69.23 | 45.59 | 53.89 | 86.00 | 439.91 | 729.22 | 20.40 | 1,013,247.86 | 100,253.86 | 1,113,501.72 |
| [w/o EXP](wo-exp/summary.json) | 82.00 | 70.57 | 47.69 | 56.32 | 80.00 | 487.35 | 589.80 | 16.86 | 665,201.24 | 84,433.62 | 749,634.86 |
| [w/o Parallel](wo-parallel/summary.json) | 84.00 | 63.18 | 40.99 | 50.51 | 82.00 | 495.13 | 562.72 | 16.18 | 578,709.40 | 77,990.32 | 656,699.72 |
| [w/o Early-stop](wo-early-stop/summary.json) | 78.00 | 69.28 | 47.93 | 56.00 | 76.00 | 510.68 | 608.42 | 16.56 | ≥631,604.80 | ≥86,677.42 | ≥718,282.22 |
| [w/o Local-repair](wo-local-repair/summary.json) | 70.00 | 61.39 | 40.64 | 49.10 | 66.00 | 379.80 | 526.43 | 15.82 | 622,214.16 | 76,429.96 | 698,644.12 |
| [w/o All](wo-all/summary.json) | 72.00 | 63.60 | 39.35 | 47.85 | 66.00 | 265.10 | 315.37 | 15.48 | 301,242.74 | 42,485.58 | 343,728.32 |

各组分母固定为 50，包含失败任务。时间采用 `task-metrics.v2` 的可报告任务运行时间；调用数包括科学工具和 `DescribeTools`。输入、输出 token 来自 API usage，输出包括服务端报告的 reasoning token；`≥` 表示已记录用量的下界，未知用量不填成零。逐题用量完整性保存在 `task_metrics.json` 中。

编排完成程度是必要能力与依赖满足程度 C；工具选择效率是科学调用的有效性 E；综合规划分先逐题计算 `S = 3CE / (2E + C)`，再对 50 题取平均，C 或 E 为零时 S 为零。运行完成表示正常提交；答案准确率按科学判据独立评分。评分不调用 LLM，具体规则见 [评分细则](../../docs/scoring.md)。

## 代码版本与配置

**SciMas 项目版本（代码与实验数据发布）**：[395e670cb205076efe555a60963a1759d96b9686](https://github.com/haibala-ai/SciToolFlow/commit/395e670cb205076efe555a60963a1759d96b9686)。每条结果对应的实际 GitHub commit、执行开关、源文件哈希和运行指纹记录在各组 `task_results.jsonl` 与 `segments/*/configuration.json`；逐批次版本索引见 [configuration.json](configuration.json)。

| 配置 | 取值 |
| :--- | :--- |
| 基模 | DeepSeek 官方 `deepseek-flash` |
| API | `https://api.deepseek.com`，profile=`official`；服务器直连，`httpx`，`trust_env=false` |
| 检索 embedding | 本地 `Qwen3-Embedding-4B`，2560 维，客户端 L2 归一化 |
| 题库 | `mini-100` 接口执行固定 Mini-50 清单；题目 ID 不重新编号 |
| 选题 | seed=`2026110602`，包含 8 个既定题位，再随机抽取 42 题；见 `dataset/sampling.json` |
| 并发 | 每组同时 2 个 task；执行时六组同时启动，最多 12 个活动 task |
| 单题工具并发 | 默认 4；串行变体为 1，以实际执行配置为准 |
| 单题请求上限 | 400 |
| 单次输出上限 | 65,536 token |
| 上下文配置 | `max_input_tokens=40960`，`max_context_chars=1500000`；为运行时配置值，不等同于提供商上下文硬限制 |
| 超时 | task=7,200 s；工具=180 s；API=600 s；连接=10 s |
| 请求协议 | JSON mode 开启；structured output 关闭；采样参数未显式设置，遵循提供商默认行为 |
| 通信保护 | 连续通信失败阈值 3；不自动反复重放可能已计费的生成请求 |
| 环境 | `SciTool-Unified` |

本轮 v2 的组件开关如下；每条轨迹也保存实际执行开关。

| 变体 | 经验 | 工具并行 | 候选早停 | 执行中局部修复 | 执行前图纠错 | 科学 Reviewer |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| w/o EXP | 关 | 开 | 开 | 开 | 开 | 开 |
| w/o Parallel | 开 | 关 | 开 | 开 | 开 | 开 |
| w/o Early-stop | 开 | 开 | 关 | 开 | 开 | 开 |
| w/o Local-repair | 开 | 开 | 开 | 关 | 关 | 开 |
| w/o All | 关 | 关 | 关 | 关 | 关 | 关 |

## 数据组织

```text
ablation/
├── README.md                  # 结果、配置和读取方法
├── configuration.json         # 公共配置与逐批次 GitHub 提交版本
├── summary.json               # 五组最终评分和效率统计
├── manifest.json              # 原始文件映射、压缩方式与 SHA256
├── verification.json          # 250 条轨迹的认证结果
├── dataset/                   # 固定选题清单、映射和输入快照
├── source_dependencies/       # 对应提交版本的本地检索索引快照
└── wo-*/
    ├── summary.json
    ├── scores.json            # 50 题评分；可直接分析的相对路径
    ├── scores.original.json   # 原始汇总评分，不改写
    ├── task_metrics.json      # 50 题时间、调用数及输入/输出 token
    ├── task_results.jsonl     # 逐题成绩、版本和轨迹索引
    └── segments/
        ├── current/
        └── retained/
            ├── configuration.json
            ├── actor_file_hashes.json
            ├── predictions.original.json.gz
            ├── predictions.portable.json
            ├── scores.original.json
            ├── configuration_snapshot/
            ├── logs/
            └── trajectories/ # 完整轨迹和产生的工具文件
```

原始预测与轨迹采用 gzip 无损压缩，内部历史路径和模型输出保持原样。`predictions.portable.json` 仅调整轨迹路径及压缩文件哈希，方便在归档目录认证；任务、答案、调用与运行指纹不变。原始运行目录保持不动。API 密钥、账号文件和模型权重不进入归档。

## 查看单题

从项目根目录执行：

```python
import gzip, json
from pathlib import Path

group = Path("exp/ablation/wo-parallel")
rows = [json.loads(line) for line in (group / "task_results.jsonl").read_text().splitlines()]
row = next(r for r in rows if r["id"] == "SMAS-0001")
with gzip.open(group / row["trajectory_file"], "rt") as f:
    trajectory = json.load(f)
print(row["status"], row["scores"], row["metrics"])
print(trajectory["steps"][0])
```

轨迹包含逐步角色请求与响应、工具参数和输出、图版本、评审与修复记录、实际调用时间和资源账本。读取不发起模型请求。

## 离线复核评分

按待复核 segment 的 `configuration.json.actor_commit` 检出独立工作区，在该工作区解压对应的 `source_dependencies/<commit>/retrieval_indexes.tar.gz`，恢复评分指纹依赖的 `.local/indexes/` 文件。代码和本地索引都必须匹配，不能只改预测文件指纹。离线评分不需要启动 embedding 服务或调用生成 API。

例如，在匹配代码版本且恢复了索引的工作区中运行：

```python
import json, os, subprocess, sys
from pathlib import Path

source = Path.cwd()  # 已检出对应 commit 的独立工作区
segment = Path("/absolute/path/to/SciToolFlow/exp/ablation/wo-exp/segments/current")
config = json.loads((segment / "configuration.json").read_text())
env = dict(os.environ, SCITOOLFLOW_ROOT=str(source), PYTHONPATH=str(source))
subprocess.run([
    sys.executable, str(source / "cli.py"), "score",
    "--dataset", "mini-100", "--tasks", ",".join(config["selected_ids"]),
    "--predictions", str(segment / "predictions.portable.json"),
    "--output", "/tmp/wo-exp-current-scores.json",
], env=env, check=True)
```

每组各 segment 的题号集合互斥，合并后恰为固定 50 题。合并时按逐题评分重算均值，不能直接对不同题数 segment 的平均分取平均。归档没有新增任务生成或重跑失败题。
