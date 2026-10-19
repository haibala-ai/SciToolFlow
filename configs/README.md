# 运行配置

- [project.json](project.json)：工具运行时位置、模型/embedding 服务和评分约定。
- [environments/](environments/)：现有四个 Conda 环境的实际快照。
- [services/qwen_vllm.json](services/qwen_vllm.json)：本地 Qwen 服务参数。
- [services.env.example](services.env.example) / [runtime.env.example](runtime.env.example)：无密钥的服务与路径配置模板。
- [tool_resources.json](tool_resources.json)：声明的资源／账号配置项与依赖工具。
- ReAct 的实验限制单独放在 [baselines/react/config.json](../baselines/react/config.json)，CLI 默认值直接读取该文件。

从 SciToolFlow 根目录执行 `python scripts/model_service.py status` 查看模型服务；`start` 启动、`stop` 停止。支持 `--gpus`、`--python`、`--model-path` 等部署覆盖项，无需修改跟踪文件中的机器路径。2026-10-19 的现有服务仍位于物理 GPU **6、7**、显存预算 0.95、TP=2；ReAct 全量任务随后已按用户要求暂停。

本机密钥位于 `.local/credentials/services.env`，本机路径配置位于 `.local/credentials/runtime.env`；均不进入公开文件清单。换机器后需要配置账号、模型、系统/GPU 依赖及 Conda 路径，工具部署说明见 [tools/README.md](../tools/README.md)。
