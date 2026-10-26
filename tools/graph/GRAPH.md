# 工具图谱与检索向量

图谱来自 `tools/catalog/catalog.json` 的当前契约，保存规范工具、学科、功能、签名、实现、输入输出、字段说明、失败反馈和环境的双向关系。图谱由当前契约完整派生，不从外部历史索引继承边。

当前有 **473 个公开工具、472 个图谱工具节点及472份功能向量**。`DescribeTools` 是通用工具，`indexing.graph` 和 `indexing.embedding` 均为 false；没有该工具的节点、边或检索向量。规范别名可以有图谱关系，但没有独立功能向量；退休名称只在目录中提供迁移信息。

`index_store.json` 保留原索引的存储格式。`embedding_dict` 以 `(tool, 'has the functionality that', description)` 的字符串为键，存储 `text-embedding-3-large` 的3,072维L2归一化向量。功能向量仅存储在本文件，不维护空的向量库占位文件。

`python -m scripts.tools.build_graph --embed` 使用配置的 API 增量编码，按模型／提供商身份与文本哈希复用；全部响应通过维数、有限性和归一化验证后才替换索引。`tool_foundation_manifest.json` 与 `build_report.json` 记录当前哈希、数量、API用量和排除项。查询 embedding 必须匹配索引的模型、维数和提供商。

`inputs`／`outputs` 关系来自经实现审查的 `dataflow` 端口，而非整段参数说明的字符串匹配。每个输入端口对应真实参数，每个输出端口对应 schema 可遍历的字段路径；JSON 字符串端口明确标注解码。双向关系支持候选工具链扩展，保留字段路径、条件、单位和来源说明。概念相同不等于科学兼容，实际编排仍需核对对象、单位、方法及结果完整性。
