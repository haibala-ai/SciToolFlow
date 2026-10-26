# 工具执行运行时

公开入口为`from tools import execute`。运行时负责执行与验证，科学算法由implementations提供。

| 模块 | 职责 |
| --- | --- |
| executor.py | Agent调用入口；统一名称解析、host工具与科学执行 |
| dispatch.py | 参数和输出验证、环境路由、进程调度、超时及结构化错误 |
| worker.py | 在指定科学环境执行单次工具调用 |
| contracts.py | JSON Schema与有限JSON值校验 |
| environments.py | 逻辑工具环境到四个Conda环境及解释器的映射 |
| config.py | 科学资源、服务参数与附件上下文 |
| context.py | 当前任务的执行期限与调用上下文 |
| scope.py | 显式工具执行范围 |
| audit.py | 执行证据记录辅助 |

密钥和本机路径从.local/credentials加载，不写入公开工具文档。工具返回真实成功、错误、阻塞或显式跳过状态；缺少数据或模型时不生成替代结果。
