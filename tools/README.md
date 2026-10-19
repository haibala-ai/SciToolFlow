# 工具代码与契约

本目录直接包含 546 个任务工具与 DescribeTools 的实际代码，不再嵌套旧项目。

| 入口 | 职责 |
| --- | --- |
| [catalog.json](catalog.json) | 唯一持久化清单：公开契约、execution 绑定、source 文件/函数/哈希 |
| catalog.py | 读取清单、名称/别名、学科分组；在内存中提供评分器需要的注册视图 |
| discovery.py | 批量 DescribeTools，仅返回公开描述/签名/输入输出类型与限制 |
| executor.py | Agent 的调用入口；查询直接响应，任务工具走隔离调度 |
| runtime/ | dispatch、worker、超时/错误、环境路由、资源配置和执行上下文 |
| implementations/ | chemistry、materials、machine_learning、general、biology、shared |
| graph/ | 工具语义图谱与功能向量 |

不再保留独立 registry.json、source_hashes.json、tool_contracts.json；生成报告位于 results/reports/，没有重复的可执行注册层。公开 DescribeTools 不返回内部 execution/source 字段，也不导入科学工具或读取答案/参考。

契约包含描述、调用形式、参数说明/类型/默认值、输入 schema、返回说明/类型、输出 schema 与编码形态。观察到的历史输出字段明确可选；33 个无法确认更窄类型的参数保留 Any。工具名、参数与已有科学计算逻辑保留；旧显示元组原字节保存在本地历史归档中。

worker 根据 configs/environments/routing.json 路由至四个物理环境：

| 环境 | 启动 | 用途 |
| --- | --- | --- |
| SciTool-Unified | conda activate SciTool-Unified | 主入口、大部分工具 |
| SciTool-LLM | conda activate SciTool-LLM | 模型/vLLM 及相应工具 |
| SciTool-RXN-Local | conda activate SciTool-RXN-Local | 反应模型依赖 |
| SciTool-Chroma | conda activate SciTool-Chroma | 既有 Chroma 依赖 |

worker 显式把当前项目根目录加入子进程 PYTHONPATH，不再注入旧 ToolsAgent/ToolsFuns 路径。工作目录在 .local/work/tools，模型/外部程序分别在 .local/models、.local/external_sources，生成附件位于 results/tool_artifacts。资源通过 scitoolflow.paths 定位，不用固定 parents[4] 猜目录。

账号位于 .local/credentials/services.env，本机 Conda 路径位于 runtime.env；文件不公开。环境快照在 configs/environments/。少数旧文件工具共享默认输出名，因此串行执行；这轮整理不宣称它们支持并发写同一目录。

维护命令（从项目根目录执行）：

```bash
python scripts/build_catalog.py
python scripts/build_graph.py
python scripts/check_foundation.py
```

build_catalog 只检查静态实现/参数并刷新源码哈希，不调用科学工具；改变契约需同时更新说明和 schema。预检检查函数、资源、解释器、图链接和向量，但不替代所有外部服务的现场调用。报告位于 results/reports/tool_preflight.json。
