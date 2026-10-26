# 共享运行代码

`src/` 只保存工具和 baseline 共用的模型连接与基础函数。任务、科学工具、baseline 策略和评分器仍分别位于 tasks、tools、baselines 和 evaluation，避免混在一起。

| 目录 | 职责 |
| --- | --- |
| [models/](models/README.md) | 统一生成客户端、API／vLLM 接入、本地 worker 与模型执行记录 |
| [utils/](utils/README.md) | 文件读写、项目路径和本机环境加载 |

项目命令在根目录 `cli.py`；安装后的 `scitoolflow` 命令指向同一个入口。`src/__init__.py` 声明供构建脚本使用的发布版本。
