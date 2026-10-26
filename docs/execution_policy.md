# 运行资源策略

当前策略为 **`task-resources.v1`**，ReAct 与 SciToolAgent 使用相同默认额度。它控制实验的计算资源；题目中的科学约束及 `workflow.v1` 科学评分规则独立保留。

## 默认额度

| 项目 | 每题默认值 | 计算方式 |
| --- | --- | --- |
| 生成请求 | **400 次** | 所有角色合计，包含请求失败、协议纠错、think、inspect 及最终提交 |
| 总时间 | **7,200 秒** | 包含检索、模型等待、工具执行和纠错；接受最终答案时停止计时 |
| 科学工具调用 | 无独立次数上限 | 每次实际执行仍记录，失败也计成本 |
| DescribeTools | 无独立次数上限 | 单独记录发现成本，排除于科学路径与科学覆盖率 |
| 显式 think | 无独立总次数或连续次数上限 | 每次消耗一次生成请求及时间 |
| 累计 token | 不设上限 | 记录实际返回用量，未返回时标记未知 |

批量响应中的多个工具动作只对应一次生成请求，各次工具执行仍分别记录。SciToolAgent 的 planner、executor、summarizer 与重规划共用同一个请求和时间账本，不能在角色切换时重新获得额度。embedding 请求单独统计费用，不占生成请求额度，但其等待与重试计入总时间。

第 400 次请求返回的合法完成可以接受；模型若还想继续，不发送第 401 次请求，任务以 `ModelRequestBudget` 结束。最终答案必须在时间截止前通过格式与完成校验，超时返回不计完成。模型调用及 vLLM 模型信息／token 预检的等待均受剩余时间约束。初始化或预检失败也保存失败轨迹，尚未发起生成时请求数为零。资源耗尽的题目仍保留在实验与评分分母中。

## 保留的运行保护

- 每次模型输出最多 4,096 tokens，输入预算 40,960 tokens，另有 200,000 字符上下文限制。长历史通过现有上下文管理处理，完整轨迹仍保存。
- 每批最多 8 个动作，单次工具调用最多 180 秒；临近任务截止时按剩余时间缩短等待。
- 连续协议错误达到 5 次终止；合法科学失败保留明确反馈。
- **连续十个决策步**实际调用同一规范工具、且展开后的实参完全相同，执行第十步后以 `RepeatedToolLoop` 终止。换工具、换参数或非工具决策会打断连续计数。

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

上述参数均为默认值。`--max-calls`、`--max-steps`、`--max-discovery-calls`、`--max-think-steps` 和 `--max-consecutive-thinks` 保留为实验可选限制，默认均为空。它们不是题目字段；若显式设置，应报告为不同的实验配置，并对参与比较的 baseline 采用一致设置。SciToolAgent 的最多三轮规划仍是其算法定义，不因资源额度放宽而移除。

同一题库／工具／代码／prompt／模型／采样／资源策略才能 `--resume`。改变设置须新建输出目录，不能修改旧 checkpoint 指纹强行续跑。

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
