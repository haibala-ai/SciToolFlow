# 配置

配置分为环境、生成服务、科研资源和实验策略四类。基准任务与评分标准分别由 `tasks/` 和 `evaluation/` 管理，配置文件不覆盖金标准。

| 文件／目录 | 用途 |
| --- | --- |
| [environments/](environments/README.md) | 四个 Conda 环境的安装快照、依赖约束与工具环境路由 |
| [services/qwen_vllm.json](services/qwen_vllm.json) | 可选的 Qwen 本地服务部署示例；GPU、解释器和模型路径可由启动参数覆盖 |
| [services/dpsk_api.json](services/dpsk_api.json) | AIHubMix DPSK 生成 API 配置，不含密钥 |
| [services.env.example](services.env.example) | 生成 API、vLLM、检索 embedding 与科研服务账号模板 |
| [runtime.env.example](runtime.env.example) | 科研文件、模型与解释器的本机路径模板 |
| [tool_resources.json](tool_resources.json) | 从工具契约派生的资源配置项及依赖它们的工具 |
| [ReAct 配置](../baselines/react/config.json) | ReAct 默认实验策略与资源限制 |
| [SciToolAgent 配置](../baselines/scitoolagent/config.json) | SciToolAgent 规划、检索与执行策略 |

将需要的配置填写到 `.local/credentials/services.env` 与 `.local/credentials/runtime.env`。环境变量优先于这两个文件；不要将账号值提交到版本控制。各 baseline 的生成模型由 CLI 的 `--backend`、`--model` 及服务环境变量选择，embedding 服务单独配置。当前正式评分不调用 LLM。

从项目根目录运行 `python -m scripts.services.model_service status` 查看本地模型服务；使用 `start`／`stop` 管理该服务。部署时通过 `--gpus`、`--python`、`--model-path` 指定本机资源。安装步骤、账号申请和下载地址见[安装与部署](../docs/setup.md)。
