# ReAct baseline

ReAct 既是 SciToolFlow 的测试 harness，也是 baseline。它只读取公开任务、输入附件和工具契约，通过统一工具执行器获取证据，以结构化答案提交结果。

## 启动与输出

从项目根目录执行：

```bash
python baselines/react/run.py --backend vllm --model YOUR_MODEL \
  --tasks SMAS-0103,SMAS-0180 --concurrency 2 --output results/demo/predictions.json
python baselines/react/run.py --backend vllm --model YOUR_MODEL \
  --tasks SMAS-0103,SMAS-0180 --concurrency 2 --output results/demo/predictions.json --resume
```

生成后端支持 `api`、常驻 `vllm` 和直接加载权重的 `local`。API 使用 `SCITOOLFLOW_API_BASE/KEY/MODEL`；vLLM 使用独立的服务地址、模型名和采样配置；direct-local 仅支持并发 1，其 GPU 依次采用 `SCITOOL_LLM_GPU`、继承的 `CUDA_VISIBLE_DEVICES`、单卡 `0`。模型选择与部署见[安装说明](../../docs/setup.md)。

`predictions.json` 保存预测、运行设置和续跑指纹，`progress.json` 保存进度；实验流水线另用 `experiment.json` 记录执行阶段。完整轨迹位于 `trajectories/<task-run>/trajectory.json`，工具产物位于 `tool_artifacts/`。轨迹与预测逐步原子保存；同指纹 `--resume` 复用已记录任务，只有显式 `--retry-failed` 才重试失败任务。代码、任务、工具实现、prompt、模型、采样和并发设置改变后，应新建实验目录。

查询、规划、运行与评分默认使用`--dataset mini`，题号为SMAS-0001..0200。Full-500用`--dataset full`显式选择；旧Mini接口已移除。评分使用与运行相同的题库和任务选择，说明见[Mini-200](../../tasks/mini/README.md)。

## 模型交互

初始消息展示按学科分类的工具名、任务输入和公开答案格式，不展示科学工具的完整参数，也不读取参考答案。模型可以直接合法调用工具，或通过 `DescribeTools` 查询单个名称或最多 20 个名称的完整契约。已有契约可以复用；参数错误返回公开输入 schema 以供修正。

每次响应选择一种决策：

| 决策 | 示例与含义 |
| --- | --- |
| 调用工具 | `{"actions":[{"tool":"DescribeTools","arguments":{"tools":["ParseJSONDocument"]}}]}` |
| 简短思考 | `{"think":"先检查输入，再决定下一步。"}`，可选，不要求输出内部 reasoning |
| 检视观察 | `{"inspect":{"observation_id":"o001","field":["document"],"offset":0}}` |
| 提交答案 | `{"finish":{"value":7}}`，finish 内部必须符合当前题的 answer_schema |
| 无法完成 | `{"stop":{"reason":"必需证据不可用"}}`，记录失败并保留证据 |

独立动作可合成一批，默认顺序执行。每个动作的输入必须在这一轮开始前准备好，不能引用同批次刚生成的输出。单项校验失败记录在 `action_errors`，不阻止其余合法动作，结果以 `action_index` 对应原动作。文档查询观察使用 `d001`，科学工具观察使用 `o001`；失败保持 `error`／`blocked`／`skipped`，不充当科学结果。

## 历史、观察与答案格式

`context.py` 管理实际传给模型的消息和输入额度；上下文预览不是完整轨迹。每个科学输出完整落盘，过长预览通过 `inspect` 读取；`field` 指定对象键或数组索引路径，`offset` 是序列化 JSON 的字符偏移，`next_offset` 指示后续页。观察引用复制真实完整值，不执行计算；`decode: "json_array"` 只解码实际观察中已有的完整数组。DescribeTools 文档完整返回。

公开 `answer_schema` 生成必填字段索引、缩进结构和同级字段表。答案格式错误指出具体缺失或类型不符的路径，不填值、不重排字段、不提供参考答案。合法 null 与完成的负结果按科学契约保留，未取得必需证据时使用 stop。

在支持结构化输出的后端，`--protocol-schema-guard` 从首轮约束操作和登记工具名，只对已经展示的参数契约施加参数约束，未知契约仍允许直接调用。默认 `--answer-schema-guard` 在首次答案格式错误后启用答案结构约束：仅取公开字段、类型与必填层级，不复制科学枚举、常量、默认值、示例、范围或数组长度，仍允许取证、思考和停止。当前 vLLM 支持此机制；API 须由提供商支持且显式启用结构化输出；direct-local 使用文本格式说明与本地校验。两项 guard 均有 `--no-...` 对照开关，轨迹记录约束来源与 SHA256。

## 资源与终止

默认配置来自 [config.json](config.json)：

| 项目 | 默认值 |
| --- | ---: |
| 每题生成请求 | 400 次 |
| 每题墙钟时间 | 7,200 秒 |
| 单次工具超时 | 180 秒 |
| 单批动作 | 最多 8 个 |
| 连续协议错误 | 最多 5 次 |
| 单次模型输出 | 最多 4,096 tokens |
| 连续相同工具及实参 | 10 个决策步后终止 |

科学调用、DescribeTools 与 think 没有独立的默认总次数上限；所有模型请求共用生成与时间额度。token 记录缺失时为未知，不设置累计 token 上限。第 400 次请求可合法完成，不发送第 401 次；答案必须在截止时间前通过格式校验。完整资源含义见[执行策略](../../docs/execution_policy.md)。

若连续 10 个决策步实际调用同一规范工具、实参完全相同，且每步内所有调用均相同，则以 `RepeatedToolLoop` 结束当前题；成功和失败调用均计入。别名与观察引用先展开，字典键顺序无关；参数值、数组顺序、工具或决策类型改变都会中断连续计数，分散复用不累计。单批重复多次只计一个步。默认不按历史累计失败次数禁用实参；实验可通过 `max_failures_per_action` 指定累计失败阈值，与连续循环规则独立。

## 轨迹与并发

每份轨迹包含 `initial_messages`、`limits`、`steps`、`stats`、`status` 及答案／失败。每个模型响应对应一个 step，类型为 tools、think、inspect、finish、stop 或 error；工具步内保留实参、输出、错误与耗时。think 消耗一次生成请求与时间，没有科学 observation。原生模型 reasoning 由客户端的独立配置控制。

`--concurrency` 默认 1，控制不同任务的并行数，单题内工具仍按顺序执行。每题有独立进程和模型客户端，可写工作区隔离到 `.local/work/batches/<batch>/<task>/tools`。主进程唯一写入预测；`progress.json` 的已记录数包含失败任务。Ctrl-C 终止本次生成并保留中断轨迹，尚未写入预测的题可在同指纹续跑时重新执行。

## 代码入口

| 文件 | 职责 |
| --- | --- |
| run.py / runner.py | 独立 CLI、批次、续跑和预测保存 |
| runtime.py | 模型决策循环与反馈 |
| context.py | 消息历史、输入额度与观察预览 |
| trajectory.py | 实际执行轨迹与统计 |
| system_prompt.md | 唯一 system prompt |
| config.json | CLI 默认策略与资源参数 |

[SciToolAgent](../scitoolagent/README.md) 复用公共协议、格式说明、资源与重复循环检测。科学评分位于独立的 [evaluation](../../evaluation/README.md)，不会把 DescribeTools 计入科学工具路径。
