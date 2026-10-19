# ReAct baseline

生成支持 `--backend api|vllm|local`、`--model`。API 使用 `SCITOOLFLOW_API_BASE/KEY/MODEL`，不读取 embedding 密钥；本地推荐常驻 vLLM，直接 Qwen worker 也可用但并发为 1。API JSON Schema 需要供应商支持并显式开启，普通 JSON 模式仍经相同本地协议和答案校验。安装、配置与完整命令统一见[交付 README](../../README.md)。

本目录是 baseline 的公开使用入口：

| 文件 | 用途 |
| --- | --- |
| [run.py](run.py) | 从项目根目录运行 baseline |
| [system_prompt.md](system_prompt.md) | 唯一的 system prompt |
| [config.json](config.json) | CLI 直接读取的默认决策/时间/token 预算 |

本目录包含实际实现：runner.py 管理批次与续跑，runtime.py 实现决策循环，context.py 管理上下文，trajectory.py 处理轨迹。公共模型客户端位于 scitoolflow/models/；项目 CLI 复用本目录代码。

```bash
python baselines/react/run.py --tasks FLOW-0285,FLOW-0481 --concurrency 2 --output results/demo/predictions.json
python baselines/react/run.py --tasks FLOW-0285,FLOW-0481 --concurrency 2 --output results/demo/predictions.json --resume
```

新轨迹位于 `results/<experiment>/trajectories/<task-run>/trajectory.json`。历史实验的原路径字符串保留；当前浏览路径以 `results/index.json` 为准。此次路径重组会改变 checkpoint 指纹，旧实验应保留，新实验使用新的输出目录。

## 协议

ReAct 是本项目测试 harness，也是 baseline。运行器不读取 references.jsonl；只加载公开
tasks/questions.jsonl、公开工具契约和调用预算。其他 baseline 可复用工具执行器并输出同一预测格式。

初始 system 消息包含按学科分类的工具名、DescribeTools 的输入形式、五种决策格式与限制。
它不包含科学工具的描述、实参类型或参考路径。DescribeTools 按需查询；合法的直接调用无需查询历史。批量查询可一次获得多个工具契约，后续无需重复查询。参数错误会指出问题并返回该工具的公开输入 schema；不会伪造成功 observation。

- 调用：`{"actions":[{"tool":"DescribeTools","arguments":{"tools":["ParseJSONDocument"]}}]}`
- 思考：`{"think":"需要先确认输入格式，再读取结果。"}`
- 检视：`{"inspect":{"observation_id":"o001","field":["document"],"offset":0}}`
- 结束：`{"finish":{"value":7}}`，内部字段必须符合该题公开答案 schema。
- 无法完成：`{"stop":{"reason":"必需证据不可用"}}`，记录为失败，不计完成。

DescribeTools 可接单个字符串或 1–20 个名字。未知名返回建议，不自动执行相似名字。
aliases 只按已登记映射解析。科学 observation 使用 o001 等标识，查询使用 d001，
错误保持 error/blocked/skipped，不把失败内容当科学结果。批量动作默认串行执行；单项校验错误写入 action_errors，合法独立动作仍执行，结果用 action_index 对应原始动作；
它们的输入必须在该轮前准备好，不能引用同一批中新产生的结果。

思考步是可选的独立决策，仅写简短工作状态；不要求导出模型内部 reasoning。
它使用一次模型请求，消耗时间和 token，无 observation、无科学调用。总量和连续量
均有限制，剩余额度回给模型。原生模型 reasoning 由 client 的独立开关控制。

每个 trajectory.json 包含 initial_messages、limits、steps、stats、status、最终答案/失败。
step.type 有 tools、think、inspect、finish、stop、error；一个响应只有一个 step。
tools step 自带实际 calls/output/error/duration，不再拆出大量 event 或重复消息。
观察预览受限时可 inspect；完整输出保留。DescribeTools 的文档完整回给模型。

运行中逐步原子保存轨迹；batch 也逐题原子保存预测。resume 绑定公开输入、工具实现、
prompt、client 和采样设置，失败任务不会暗中重跑；只有 --retry-failed 才重试。
采样使用 SCITOOLFLOW_VLLM_TEMPERATURE/TOP_P/TOP_K/REPETITION_PENALTY 等配置。
API 后端可以独立设置 SCITOOLFLOW_API_BASE/API_KEY/MODEL；评分不使用这些凭据。

## 默认预算与本轮审查

默认 80 轮、每批 8 动作、20 次查询、8 次显式思考（连续最多 2 次）、连续协议错误最多 5 次、每次输出 4096 tokens；科学调用仍使用公开题目的 32/34/35 次额度。每轮显示所有剩余预算，用户可以用 CLI 调整。Ctrl-C 保留中断轨迹并终止本次生成，不触发后续 judge。

前 251 条历史轨迹的审查、预算依据与限制见 [2026-10-17 报告](../../results/reports/react_review_20261017/README.md)。旧协议预测和新协议预测必须使用独立实验目录，不能直接 resume 或拼接。

公开输入附带由 answer_schema 生成的 required_answer_fields 索引，仅列必填路径和类型。答案校验指出缺失字段的完整路径及同名字段已出现的位置；不会重排模型答案或补充科学值。

## 连续同参循环终止

默认 `--max-identical-tool-steps 10`。一个模型决策对应一个 step；若连续 10 步都有实际执行的工具调用、且每步全部调用都为同一规范工具名和同一组实参，则第 10 步执行后结束当前任务，返回 `RepeatedToolLoop`。成功/失败结果不影响此规则；时间及调用预算仍可能更早生效；默认不再按历史累计失败次数禁用某组参数。所有实际调用和费用保留，任务不计完成；批次继续其他任务。

工具别名先规范化，观察引用先展开；参数字典键顺序不影响判断，参数值和数组顺序不同会清零。换工具、换实参、混合批次、think、inspect、finish、stop、拒绝/无效步骤均中断连续计数，不累计分散复用。单步批量重复多次只算一个决策步。DescribeTools 也适用。轨迹记录 consecutive_identical_tool_steps、loop_termination 及 error；stats 记录 max_consecutive_identical_tool_steps。

## 可读的答案格式与纠错约束

初始提示和 AnswerFormatError 反馈给出公开 answer_schema 的缩进 finish 结构及对象同级字段表。占位符不是答案；数组示例不暗示长度，模型自行填写真实证据。

默认启用 `--answer-schema-guard`。在 vLLM 后端首次答案格式错误后，后续决策使用由公开字段、类型和必填层级生成的 schema 约束；不复制科学枚举/常量/默认值/示例/说明/范围或数组长度，不读取参考答案。它仍允许全部五种决策及观察引用，模型可以继续取证或 stop，不会被强制 finish。从首轮起另有公开协议约束，限制操作语法与登记工具名；已查询/反馈展示的参数契约才用于参数约束，未知契约仍允许合法直接调用。观察引用先验证并展开，再按原始答案 schema 校验；harness 不填值、不搬字段。

用 `--no-answer-schema-guard` 可关闭约束用于对照。当前只有经过验证的 vLLM 后端声明支持结构化约束；API/direct-local 使用同级字段表、具体错误路径及本地校验。格式错误仍计入协议/轮次预算，每次纠错模型请求都有成本；stats.answer_schema_guard_requests 和 step.model.response_schema_sha256/source 记录约束使用情况。

与 [SciToolAgent](../scitoolagent/README.md) 共用此机制；SciToolAgent 跨角色追踪连续决策，RepeatedToolLoop 为终止失败，不触发重规划。科学调用预算和评分规则未改。新代码/prompt 改变续跑指纹，应新建实验，不能直接续跑旧 500 题。实际验收见 [本轮报告](../../results/reports/react_loop_format_20261017/README.md)。

## 任务并发

`--concurrency` 默认 1，本地常驻 vLLM 推荐先用 2，与服务 max_num_seqs 匹配。并发作用于不同任务，单题内的动作仍顺序执行。每题独立进程和模型客户端；可写工具目录隔离到 `.local/work/batches/<batch>/<task>/tools`，产物保存到本次结果的 `tool_artifacts/<task>/<batch>/`。模型和只读资源复用，工具环境路由不变。直接加载权重的 `--backend local` 仅支持并发 1。

主进程是 predictions.json 的唯一写入者，逐题原子保存、按选择顺序排列。progress.json 给出已记录数、已提交数和活动任务；失败也计入已记录数。并发数进入续跑指纹，不同代码/设置不能混用旧结果。中断后停止活动进程并保留其轨迹，未写入预测的任务可在同指纹 resume 时重新运行。

## 2026-10-18 的协议与数据版本

默认 `max_failures_per_action=0`（不累计禁用）。正数保留为旧策略对照开关，连续同参 10 步终止规则独立保留。`--protocol-schema-guard` 在支持的 vLLM 后端首轮生效，约束操作、工具名、预算允许的操作与已展示参数类型；`--no-protocol-schema-guard` 关闭该约束。它不读取私有参考或计算科学参数。worker 的环境/缺资源/错误诊断保留在轨迹中。

inspect、观察引用与短数组预览机制仍可使用；`decode: "json_array"` 只能解码实际观察中完整的数组，不执行计算。输出摘要哈希不是源文件哈希。当前数据契约已修订，必须新建实验目录。完整审查见 [报告](../../results/reports/full_run_audit_20261018/README.md)。
