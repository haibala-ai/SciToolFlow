# SciMas · Mini-200 实时进度

更新时间：2026-11-06T09:06:51.890189+08:00（每 10 秒刷新）

状态：**finished** · 模型：`deepseek-flash` · 任务并发：**2** · 单题工具并行：4

| 已结束 | 成功完成 | 失败／中断 | 正在运行 | 等待运行 |
| ---: | ---: | ---: | ---: | ---: |
| 200/200（100.0%） | 82 | 118 | 0 | 0 |

## 当前任务

| 任务 | 阶段 | 已运行秒数 | 模型响应／请求步骤 | 科学／查询调用 | 检查点距今秒数 |
| --- | --- | ---: | ---: | ---: | ---: |
| — | 暂无活动任务 | — | — | — | — |

## 已知运行成本

输入 token：**108,820,916**；输出 token：**13,085,665**；工具调用：**2598**（科学 2380＋查询 218）。

已结束任务中有 87 题用量不完整；当前等待模型响应 0 个。上述成本包含已结束任务和活动任务最新检查点的已知小计，不能作为最终总量。

完整逐题时间、调用数及输入／输出 token：[task_metrics.json](task_metrics.json)。机器可读实时状态：[monitor.json](monitor.json)。

## 失败记录（前 10 项）

- `SMAS-0003`：ResourceLimit: RepeatedActionFailure
- `SMAS-0007`：PlanningFailure: ValueError: No valid graph within the planning request limit
- `SMAS-0009`：ValueError: ["canonical-identities__0: Output path is not declared: [0]", "canonical-identities__1: Output path is not declared: [1]", "canonical-identities__2: Output path is not declared: [2]"]
- `SMAS-0014`：PlanningFailure: RetrievalError: Embedding transport failure: SSLError
- `SMAS-0017`：ValueError: Role protocol retry limit reached: ['Extra data: line 1 column 3 (char 2)']
- `SMAS-0022`：ValueError: ResultRejected: {'reject': 'CalculateSymmetry returned Cmmm (#65) for the reduced_basis structure, but the parsed lattice is a primitive monoclinic cell (a=4.0 Å, b=0.728 Å, c=6.0 Å, gamma=105.95°) with only 2/m symmetry. The correct space group is P2/m (#10). The observation is scientifically invalid and cannot be used downstream.'}; None
- `SMAS-0025`：ValueError: Role protocol retry limit reached: ['Extra data: line 1 column 3 (char 2)']
- `SMAS-0026`：ValueError: Unknown, retired or excluded tool: FilterTable
- `SMAS-0029`：RuntimeError: Generation API network request failed (RemoteProtocolError -> RemoteProtocolError; ); credentials and server response are not logged
- `SMAS-0031`：PlanningFailure: RuntimeError: Generation API network request failed (ConnectTimeout -> ConnectTimeout -> TimeoutError; timed out); credentials and server response are not logged

## 离线评分

```json
{
  "dataset": "mini",
  "tasks": 200,
  "runtime_completion_rate": 0.41,
  "tool_planning_accuracy": 0.35,
  "answer_accuracy": 0.395
}
```

生成全部结束后自动离线评分；成功完成表示运行协议完成，科学答案与工具规划结果以评分文件为准。监控只读取已有检查点，不调用 LLM，不改写轨迹或任务计时。
