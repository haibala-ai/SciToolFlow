# SciToolAgent baseline（SciToolFlow 适配版）

本实现参照 [HICAI-ZJU/SciToolAgent](https://github.com/HICAI-ZJU/SciToolAgent) 的提交 `ac1cf19fcef84e69f149db6da424afe4e9b2f11f`，保留工具图谱检索、预先规划、逐工具执行、总结与重规划。来源及改动见 [upstream.json](upstream.json)，授权见 [LICENSE.upstream](LICENSE.upstream)。它是使用本项目公共 harness 的适配 baseline，不声称逐字复现原论文结果。

所有角色支持 `--backend api|vllm|local` 和 `--model`。生成模型与检索 embedding 分开配置；即使生成使用本地模型，检索仍需要与工具索引同源的 embedding 服务。安装与模型配置见[项目 README](../../README.md)。

```bash
conda activate SciTool-Unified
python cli.py run --baseline scitoolagent --backend vllm --tasks FLOW-0285,FLOW-0481 \
  --output results/scitoolagent_demo/predictions.json
python cli.py score --tasks FLOW-0285,FLOW-0481 \
  --predictions results/scitoolagent_demo/predictions.json \
  --output results/scitoolagent_demo/scores.json
```

同一运行和评分命令均支持 `--dataset full|mini`，默认 full；`--tasks` 使用所选题库的编号。Mini 的独立编号与映射见 [Mini-200](../../tasks/mini/README.md)。

## 检索与执行

| 文件 | 职责 |
| --- | --- |
| [retrieval.py](retrieval.py) | 语义种子检索、图谱展开、上下文加权排序和 embedding 缓存 |
| [runtime.py](runtime.py) | 规划、执行、总结和重规划的阶段控制 |
| [system_prompt.md](system_prompt.md) | 各角色共用的决策协议；运行时补充角色权限 |
| [config.json](config.json) | 检索规模、候选数量和最多三轮规划；默认无单独规划步数上限 |

检索先找 5 个语义种子，沿输入／输出／功能关系展开至深度 3，过滤只共享输入或输出的同类路径。候选功能与种子上下文一起编码，以相似度乘积累加权重，最多保留 10 个工具。DescribeTools 不进入图谱或向量检索。

planner 输出有序工具链，executor 对链中的每次工具出现生成参数、执行并交回控制，summarizer 根据实际结果提交答案或请求重规划。同一工具处理多个实体时允许在计划中重复。最多三轮规划是此 baseline 的算法设置，与共享运行资源上限分别记录。

executor 只可执行当前计划工具；planner 和 summarizer 不可执行科学工具。契约由 harness 在执行前自动取得并计入 discovery 成本，各角色不自行调用 DescribeTools。planner 的 `answer_schema` 表示计划结构，`task_answer_schema` 才是最终任务的提交结构。每次执行交接携带完整 `ordered_plan`、`plan_position` 和真实历史参数／输出，摘要不足时可以 inspect。

## 公共 harness 与资源

两个 baseline 共用模型客户端、公开任务、工具执行器、答案格式与参数错误反馈、连续同参循环检查、运行指纹及独立评分器。SciToolAgent 各角色通过 ReAct 的执行循环完成决策，其顶层策略由检索和计划链控制。原版自由文本协议、无限工具重试和 LlamaIndex 存储替换为统一 JSON 协议、隔离 worker、超时、现有 JSON 图谱与向量存储；重规划仍能看到真实历史结果。

默认每题 **400 次生成请求、7,200 秒**，规划、执行、总结及重规划共用一个账本。规划阶段共用上述生成额度；科学调用、自动契约读取与显式 think 均无独立次数上限。embedding 不是生成请求，其网络等待计入本题时间，调用与 token 成本单独记录。第 400 次合法完成可以接受；达到额度后不发送下一次请求。完整定义见[运行资源策略](../../docs/execution_policy.md)。

连续同工具同参十个决策步终止，计数跨 executor 会话保留，其他角色决策会打断连续性；`RepeatedToolLoop` 不触发重规划。公开答案格式约束不填充科学值，使用方式见 [ReAct](../react/README.md)。工具执行器继续校验输入、资源与执行范围，本适配版不增加额外的 baseline 专有安全检查层。

## 轨迹与依赖

每题只保存一个 `trajectory.json`：`steps` 为每个模型响应，带 `phase`／`cycle`；`phases` 保存角色上下文，`retrievals` 保存检索依据，`preparations` 保存自动契约读取。观察 ID 跨阶段连续，可引用真实先前结果。`resource_usage` 保存共享生成请求、耗时和实际返回的 token 用量。自动 DescribeTools 不进入科学路径；检索和发现策略差异属于 baseline 算法差异，其成本分别报告。

复用当前四个 Conda 环境。查询 embedding 使用索引声明的提供商、`text-embedding-3-large`、3072 维及 L2 归一化，配置读取 `.local/credentials/services.env`，缓存位于 `.local/cache/scitoolagent_embeddings/`。缺少授权或模型／提供商不匹配会明确失败，不替换成其他向量或词法检索。缓存采用独立临时文件后原子替换，避免并发写入冲突。

embedding 网络异常及 HTTP 408/429/500/502/503/504 最多尝试三次，间隔 1、2 秒，受总超时约束；401 等授权错误不重试。实际请求与重试分别记录。

当前题库版本为 `20261026`，资源策略为 `task-resources.v1`。任务、工具、代码、prompt 或运行设置变化须新建实验目录，禁止混合旧指纹续跑。当前参考见 [evaluation/data](../../evaluation/data/README.md)，科学评分方法见[评分指南](../../docs/scoring.md)。
