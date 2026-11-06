# 运行资源策略

当前策略为 **`task-resources.v1`**，ReAct、SciToolAgent 与 SciMas 使用相同默认额度。它控制实验的计算资源；题目中的科学约束及 `workflow.v1` 科学评分规则独立保留。

## 默认额度

| 项目 | 每题默认值 | 计算方式 |
| --- | --- | --- |
| 生成请求 | **400 次** | 所有角色合计，包含请求失败、协议纠错、think、inspect 及最终提交 |
| 安全截止时间 | **7,200 秒墙钟** | 包含检索、模型等待、工具执行和纠错；不以扣除网络等待后的速度指标替代截止保护 |
| 科学工具调用 | 无独立次数上限 | 每次实际执行仍记录，失败也计成本 |
| DescribeTools | 无独立次数上限 | 单独记录发现成本，排除于科学路径与科学覆盖率 |
| 显式 think | 无独立总次数或连续次数上限 | 每次消耗一次生成请求及时间 |
| 累计 token | 不设上限 | 记录实际返回用量，未返回时标记未知 |

批量响应中的多个工具动作只对应一次生成请求，各次工具执行仍分别记录。SciToolAgent 的规划、执行、总结及重规划，以及 SciMas 的规划、执行、审查和修复，均在各自题目内共用同一个请求和时间账本，不能在角色切换时重新获得额度。embedding 请求单独统计费用，不占生成请求额度，其等待与重试仍受墙钟安全截止约束。速度统计采用独立的 `task-metrics.v2`：通信失败请求、失败建连与重连退避按实际时间区间合并去重，去掉真实并行工作覆盖的部分后，才从墙钟耗时扣除，正常成功响应仍计时；API 故障中止的尝试不提供可报告的运行时间。完整墙钟、扣除区间和部分工作耗时保留，详见[逐题运行成本](../results/README.md#逐题运行成本)。

第 400 次请求返回的合法完成可以接受；模型若还想继续，不发送第 401 次请求，任务以 `ModelRequestBudget` 结束。最终答案必须在时间截止前通过格式与完成校验，超时返回不计完成。模型调用及 vLLM 模型信息／token 预检的等待均受剩余时间约束。初始化或预检失败也保存失败轨迹，尚未发起生成时请求数为零。资源耗尽的题目仍保留在实验与评分分母中。

## 运行保护与算法边界

- 公共 CLI 默认每次最多输出 4,096 tokens，并限制上下文字符数；实际输入还受所选模型容量约束。ReAct 与 SciToolAgent 使用历史压缩；SciMas 使用角色上下文、带截断标识的输出预览和字段／文本分页查看，超出上下文时明确失败。完整请求与原始输出保存在轨迹中。
- 每批最多 8 个动作，单次工具调用最多 180 秒；临近任务截止时按剩余时间缩短等待。
- 连续协议错误达到 5 次终止；合法科学失败保留明确反馈。
- ReAct 与 SciToolAgent 在**连续十个决策步**实际调用同一规范工具、且展开后的实参完全相同，执行第十步后以 `RepeatedToolLoop` 终止。换工具、换参数或非工具决策会打断连续计数。

SciMas 的 DAG 还限制单题最多 4 个并行工具进程、每节点 1 次暂时故障重试、总计 2 次局部修复，并防止连续提交超过 10 次同工具同参数调用。这些是其算法配置，不等同于 ReAct 的连续决策步规则。未知并发安全性的工具在本题内独占执行；结构检查、角色审查和有限修复共同防止重复工作。具体边界见 [SciMas](../baselines/scimas/README.md)。

这些保护限制失控运行，科学判据继续要求完整证据、科学数值正确、必要能力与依赖成立。题文要求“最多测量三次”等研究约束仍须遵守，不能因取消执行调用额度而忽略。

## 命令与实验比较

```bash
python cli.py run --baseline react --backend vllm --tasks all \
  --max-model-requests 400 --task-timeout 7200 \
  --output results/react_full/predictions.json

python cli.py run --baseline scitoolagent --backend vllm --tasks all \
  --max-model-requests 400 --task-timeout 7200 \
  --output results/kg_full/predictions.json
```

上述参数均为默认值。`--max-calls`、`--max-steps`、`--max-discovery-calls`、`--max-think-steps` 和 `--max-consecutive-thinks` 保留为实验可选限制，默认均为空。它们不是题目字段；若显式设置，应报告为不同的实验配置，并对参与比较的 baseline 采用一致设置。SciToolAgent 的最多三轮规划，以及 SciMas 的初始规划和局部修复限制，仍是各自算法定义，不因资源额度放宽而移除。

同一题库／工具／代码／prompt／模型／采样／资源策略才能 `--resume`。改变设置须新建输出目录，不能修改旧 checkpoint 指纹强行续跑。

连续通信失败会触发批次派发熔断（默认 3 次），但不取消已经运行的任务。故障恢复后使用同配置 `--resume --retry-infrastructure`，旧尝试保留；生成请求的读写中断与 HTTP 错误不自动重放可能已计费的请求。暂停不改变题库及评分分母，未完成题仍需在正式实验中处理。

## 轨迹与评分

每题轨迹中的 `limits` 保存配置，`resource_usage` 保存实际生成请求列表、角色、返回状态、耗时及提供商返回的原始 usage。`prompt_tokens`／`completion_tokens` 缺失时为 null，`observed_prompt_tokens`／`observed_completion_tokens` 是已知小计，`token_usage_complete` 表示是否完整。输入或输出 token 只有一项已知时保留该项，另一项为 null。缺失用量不能按零成本报告；客户端无法得知的提供商内部计费也不能凭空补齐。

评分先认证轨迹哈希及其与预测的一致性，再从轨迹核对资源账本与实验配置。当前评分协议标记为 **`workflow.v1+task-resources.v1`**：

| 输出 | 含义 |
| --- | --- |
| 逐题 `resource_usage` | 经核验的请求数、耗时和可观测 token 用量 |
| `resource_limit_exceeded`（逐题） | 认证记录是否达到时间截止或超过请求／显式可选额度 |
| `resource_exhausted_tasks` | 因运行额度或时间耗尽、或认证记录显示超限的题数 |
| `resource_integrity_failures` | 资源账本缺失或与实验不一致的题数 |
| `known_prompt_tokens`／`known_completion_tokens` | 全批已知 token 小计，可能不完整 |
| `tasks_with_complete_token_usage` | 提供了全部请求用量的题数 |

资源耗尽或核验失败不能获得 Completion／Joint；科学正确性与编排诊断仍独立计算。取消旧科学调用额度不会把科学错误判为正确，也不取消选择效率的调用成本。

## 任务与参考的边界

公开任务及参考不保存逐题工具调用额度。运行和评分只使用实验中的 `task-resources.v1`，缺少该资源策略的实验会被明确拒绝。

参考的生成信息、独立审核和任务身份哈希均内联存储，真实轨迹无损压缩保存。执行额度不参与科学参考身份的重建。评分仍要求必要科学能力、证据依赖、答案和公开格式成立。参考数据结构见 [evaluation/data](../evaluation/data/README.md)。

任务、工具、代码、模型或资源设置改变后，不能修改旧 checkpoint 指纹强行续跑或拼接结果。
