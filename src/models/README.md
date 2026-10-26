# 模型连接与本地推理

两个 baseline 共用本目录的生成接口；部分科学工具也复用本地推理进程。模型连接不依赖任务金标准，评分器不加载这些模块。

| 模块 | 职责 |
| --- | --- |
| client.py | GenerationClient：API、vLLM 与直接本地 worker 的统一调用、结构化输出和超时 |
| config.py | 本地模型路径、解释器和日志配置 |
| local.py / local_worker.py | 独立 Python 子进程中的持久本地推理；直接 worker 为 Qwen3.5 专用 |
| trace.py | 科学工具内部模型调用的费用与执行记录 |

baseline 在显式 `generation_scope` 会话中调用生成接口，避免工具调用意外发起付费生成。通用本地模型通过兼容 OpenAI 的 vLLM 服务接入；直接 worker 为 Qwen3.5 专用，继承启动进程的 GPU 分配或使用 `SCITOOL_LLM_GPU` 覆盖。模型、账号、启动与采样配置见[项目 README](../../README.md)。需要修改 ReAct 决策循环时进入 baselines/react，而不是修改模型客户端。
