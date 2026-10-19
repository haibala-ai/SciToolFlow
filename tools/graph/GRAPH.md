# 工具图谱与向量

当前 547 个工具入口，4342 个节点、19260 条有向边、42 类关系和 17 个别名。实现链接直接指向 tools/implementations 或 tools/discovery.py 的文件与函数；文档链接指向唯一 catalog.json。

graph_store.json 保存带反向关系的邻接图；index_store.json 保留已构建向量的原索引存储格式，546 条功能描述向量为 text-embedding-3-large、3072 维，L2 归一化。DescribeTools 固定可见，不加入任务向量。空 docstore/默认/图像 store 是原索引格式的兼容组成，不另存第二份向量。

ReAct 通过 DescribeTools 查询 catalog，并不以图谱边代替调用契约。图谱适用于检索/其他 baseline；这轮功能描述和向量值未改，没有新增 embedding API 请求。构建和模型/文本身份见 build_report.json 与 tool_foundation_manifest.json。
