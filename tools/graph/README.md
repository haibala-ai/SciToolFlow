# 检索图谱与向量存储

本目录是[工具契约](../catalog/catalog.json)的派生索引。473个公开工具中，472个进入图谱与功能向量；DescribeTools通过通用契约查询入口直接使用。

| 文件 | 用途 |
| --- | --- |
| graph_store.json | 工具、学科、功能、输入输出与执行绑定的双向关系 |
| index_store.json | 472份text-embedding-3-large功能向量；3072维、L2归一化 |
| tool_foundation_manifest.json | 模型、提供商、文本、目录身份及索引规模 |
| build_report.json | 最近一次构建校验与增量编码用量 |
| [GRAPH.md](GRAPH.md) | 图谱关系和检索约定 |

重建使用`python -m scripts.tools.build_graph`。功能文本变化时加`--embed`，只为变化且缓存身份不匹配的文本调用已配置的embedding API；不变向量复用。维护检查使用`python -m scripts.tools.check_foundation`。图谱端口提供候选连接，具体对象、单位、方法和科学适用性由调用者核对。
