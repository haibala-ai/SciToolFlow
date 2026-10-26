# 工具契约目录

catalog.json是工具文档与执行绑定的唯一持久化来源，不另存第二份registry。

| 文件 | 职责 |
| --- | --- |
| catalog.json | 473个规范工具的功能、签名、输入输出schema、源码与运行绑定、数据端口、别名和退休说明 |
| loader.py | ToolCatalog加载、规范名称解析、学科分组与内存运行时视图 |
| discovery.py | DescribeTools批量查询，返回公开契约和迁移说明 |
| counts.py | 从规范契约计算公开、评分、图谱与向量工具数，供发布构建和验证共用 |
| ports.py | 根据输入输出schema验证数据流端口的字段与类型 |
| __init__.py | 导出ToolCatalog、DISCOVERY_TOOL和当前调用上下文 |

调用方使用`from tools import ToolCatalog, execute`。DescribeTools不返回内部执行配置，不进入图谱或功能检索。修改契约后执行`python -m scripts.tools.build_catalog`、`python -m scripts.tools.build_graph`及`python -m scripts.tools.check_foundation`；来源更新和功能文本变化分别按文档要求复核。
