# SciMas 主实验

本目录保存 Full 方法的正式实验结果：Mini-100 共 100 题，以及按固定清单提取的 Mini-50 对照。模型为 DeepSeek 官方 `deepseek-flash`，检索使用本地 `Qwen3-Embedding-4B`。

[汇总指标](summary.json) · [运行配置](configuration.json) · [完整性校验](metadata/verification.json) · [逐题索引](task_results.jsonl)

## 实验结果

| 数据集 | 运行完成率/% | 编排完成程度/% | 工具选择效率/% | 综合规划分/% | 答案准确率/% | 中位时间/s | 平均时间/s | Avg. Tool Call | Avg. Input Tok | Avg. Output Tok | Avg. Tok |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Mini-100 | 94.00 | 76.52 | 49.86 | 59.46 | 91.00 | 499.21 | 741.38 | 21.34 | 990,291.69 | 101,559.97 | 1,091,851.66 |
| Mini-50 | 92.00 | 69.23 | 45.59 | 53.89 | 86.00 | 439.91 | 729.22 | 20.40 | 1,013,247.86 | 100,253.86 | 1,113,501.72 |

评分分母包含全部题目及失败任务。时间和用量取每题选定的实际记录；调用数包含科学工具和 DescribeTools；输出 token 包含接口报告的推理 token。综合规划分先逐题计算再取平均，不能直接由表中的两个平均分重新计算。Mini-50 不额外生成，取相同 50 题的结果用于消融配对比较。

## 数据内容

```text
main_scimas/
├── README.md
├── configuration.json
├── summary.json
├── predictions.json          # 100 条预测及相对轨迹路径
├── scores.json               # Mini-100 逐题评分
├── task_metrics.json         # 逐题时间、调用数、输入／输出 token
├── task_results.jsonl         # 成绩、用量与轨迹的联合索引
├── progress.json
├── evaluate.py               # 离线复核
├── trajectories/SMAS-xxxx/   # 完整轨迹与工具产物
├── mini50/                   # 固定题号、评分与用量
└── metadata/                 # 执行身份、源码／索引快照和校验
```

`predictions.json` 是统一结果集合；每条 `trace_path` 相对本目录解析。轨迹正文、模型响应、工具输入输出和时间戳保持原样。原始配置与生产指纹按 `source_id` 关联到 `metadata/production/`；历史绝对路径可通过 `metadata/path_map.json` 定位到本目录的工具产物。

运行代码以 `2ade7929edfd4db5a324d7f33d230b0b16b43530` 为基础。精确源码、配置与检索索引快照保存在 `metadata/source_dependencies/`，逐文件哈希与来源索引位于 `metadata/sources.json`。快照不包含凭据或模型权重。

## 查看单题

在项目根目录执行：

```python
import json
from pathlib import Path

base = Path("exp/main_scimas")
data = json.loads((base / "predictions.json").read_text())
row = next(r for r in data["predictions"] if r["id"] == "SMAS-0001")
trajectory = json.loads((base / row["trace_path"]).read_text())
print(row["status"], row["metrics"])
print(trajectory["steps"][0])
```

## 离线复核

使用项目的 SciTool-Unified 环境，从项目根目录运行：

```bash
conda activate SciTool-Unified
python exp/main_scimas/evaluate.py --packaged-sources
```

该命令将归档的源码和检索索引恢复到 `.local/cache/scimas_result_sources/`，同时恢复归档的题库、附件和参考数据，逐题认证轨迹并与已保存评分比较。所有源码、索引与题库文件均按归档哈希校验；不会请求生成 API、embedding API 或科学工具。省略 `--packaged-sources` 时，优先使用本机已有的原始冻结源码，缺失时自动恢复快照。
