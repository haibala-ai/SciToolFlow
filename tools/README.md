# 工具接口与实现

当前目录提供 **473 个规范工具**。每个工具有唯一公开契约和执行绑定；同一核心计算的输入格式、批量形式和算法选项通过明确参数表达。输入不兼容的旧名称已退休，调用时返回原因、替代工具和迁移说明。

| 学科 | 公开工具 | 图谱／功能向量 |
| --- | ---: | ---: |
| 化学 | 134 | 134 |
| 生物 | 86 | 86 |
| 材料 | 162 | 162 |
| 机器学习／数理计算 | 65 | 65 |
| 通用 | 26 | 25 |
| **合计** | **473** | **472** |

`DescribeTools` 是通用工具，与其他工具使用相同的注册和契约机制。它可以直接调用，但不进入图谱，也不参与 embedding 检索。文档查询消耗运行时间与生成请求，但不计入科学工具调用路径。

## 查询与调用

```python
from tools import execute

contracts = execute("DescribeTools", {
    "tools": ["SMILESToInChI", "MolecularFingerprint"]
})
result = execute("SMILESToInChI", {"smiles": "CCO"})
```

`DescribeTools` 接受一个精确名称或最多 20 个名称，返回描述、签名、输入参数及类型／默认值、输出字段及类型、限制和错误反馈。真正的别名解析到同一个规范工具；退休名返回迁移信息，不执行替代工具。查询不读取答案、参考轨迹或私有执行配置。

输出的 `status` 为 `success`、`error`、`blocked` 或受显式执行范围限制的 `skipped`。输入不符合契约返回 `InvalidInput`；成功结果违反输出契约返回 `InvalidOutput`。缺少环境、权重、密钥、科学数据，以及上游排队、限流、连接失败均明确报告，不生成替代数值。有效的“未找到匹配”“未发现相互作用”会按具体工具的契约保留为负结果。

输入和输出执行完整 JSON Schema 校验，并拒绝非有限 JSON 数值。声明为 JSON 字符串的输出还会检查解码后的类型和字段，拒绝重复键。独立 worker、进程内工具和 host 后端遵循相同的输出验证策略；JSON 字符串仍保留其公开 wire 形态。

## 科学能力边界

| 能力 | 当前接口与边界 |
| --- | --- |
| 分子标识 | `SMILESToInChI` 是唯一 SMILES→InChI 原语。数据库标识解析与本地结构编码分开，保留盐、同位素和已给定立体信息，不自动选择片段。 |
| 分子指纹 | `MolecularFingerprint` 显式选择算法及参数，通过互斥参数支持 SMILES 或具名列 CSV。相同规则用于 `MolecularElectronicDescriptors`，CSV 形式保留流式处理、行身份、来源哈希及错误策略。比较与聚类是独立能力，计数与存在性指纹保持区别。 |
| 化学描述符 | 环计数与电子描述符使用明确的计算后端。GETAWAY 未定义分量返回 null 和索引，不补零。TPSA 明确为拓扑原子片段面积，不代表三维溶剂可及面积。Crippen 两量通过电子描述符的显式字段选择取得，不再另设同核入口；Coulomb 后端数组不宣称有未经验证的原子轴对应。 |
| 材料数据库 | 同一物理量的 formula／ID 查询归为一个接口；保留多晶型、规范 ID、分页与缺失状态。不同物理量继续独立。规范 ID 批量查询可以一次请求完成，不按记录顺序猜 ID。 |
| 分子量化学字段 | MP 没有提供的分量不再伪装为在线 ID 查询；相应本地 Q-Chem 原语要求真实计算文件。频率查询明确区分 MP 与文件来源。 |
| 晶体／MOF | 结构读取、密度、孔隙／吸附、稳定性预测保持不同物理对象和单位；显式披露晶胞、原子范围、源码／模型／引擎哈希。短程模拟不代表平衡已验证。 |
| 蛋白／肽 | 序列构造与分子公式／质量分开。肽构造使用本地 RDKit 无修饰线性肽约定，质量计算采用其原子质量表。pI 用明确方法参数选择，GRAVY 单独计算；宽泛的肽／ProtParam 总报告退休。原报告的独有内容分别保留为 instability、aliphatic 和显式模型体系的 N-end-rule 半衰期原语；半衰期下界及未知值不转成确定测量。 |
| 寡核苷酸 | Tm 与光学性质分成两个窄接口，不重复返回 GC 和未知端基质量。保留提供商未披露的温度条件／方法限制，不把 Tm 当作已验证的 PCR 退火条件。 |
| 结构模型 | ESMFold 的 pLDDT 是预测置信度，不是实测精度。ForceGPT 只保留有依据的归一化无量纲前向目标，不称为 SI 力／能量，不保留未确认的逆向能力。 |
| 记录／文件 | 列提取统一为 `ExtractNumericColumns`；文件元数据检查与记录查询分开。CSV／JSON 可显式输入文本或文件；连接区分布尔与数值 ID，保留稀疏字段及源顺序。CSV 导出使用当前任务独立文件，不覆盖共享 `_temp.csv`。 |
| 统计与配准 | inline／file 统计适配共享完整假设族计算；多重校正、富集及科学判断分开。`RigidSuperposition` 统一双点集／全对刚体拟合，保留对应关系、单位和禁止反射约定。 |
| 分类／数值执行 | `TrainAndPredictClassifier` 明确训练／预测数组、算法和随机种子，不猜文件名、分箱或填零。`ExecuteNumericalCode` 只执行调用者提交的受限代码，不再用内部 LLM 代写代码解题。 |

完整旧名处理见 [catalog.json 的 retired_tools 和 aliases](catalog/catalog.json)。退休指向多个工具时，调用者需要明确编排，执行器不会自动完成整条流程。当前执行与检索均以本目录为准。

## 实现与索引

| 文件／目录 | 职责 |
| --- | --- |
| [catalog/catalog.json](catalog/catalog.json) | 唯一持久化契约：公开文档、执行绑定、源码身份、索引标记、别名与退休原因 |
| [catalog/](catalog/) | loader.py读取目录，discovery.py实现批量DescribeTools，ports.py校验数据端口 |
| [runtime/](runtime/) | executor.py提供统一执行入口；dispatch.py路由到worker，统一验证、超时和失败反馈 |
| [implementations/](implementations/README.md) | 按学科保存科学实现与共享内核；[逐模块实现索引](implementations/INDEX.md)定位具体工具 |
| [graph/](graph/README.md) | 从契约派生的双向图谱、功能向量及索引身份 |

使用`from tools import ToolCatalog, execute`访问公开接口。目录内实现模块通过catalog中的source字段定位，运行配置放在configs与.local/credentials。

图谱同步签名、参数／输出 schema、字段说明、失败反馈、源码绑定与环境。`dataflow` 为输入参数和真实输出字段声明可传递的数据概念，输出路径逐条对照原生或显式解码 schema 检查；图谱的 `inputs`／`outputs` 关系由这些端口生成。相同概念只提示候选衔接，不能替代单位、对象、科学方法与分页完整性检查。源码变化后须重新核查端口来源，过期的源码证据会使验收失败。每个参与检索的规范工具只保存一份功能描述向量，3,072 维并做 L2 归一化；别名没有独立向量，退休工具不参与检索。模型、提供商、文本与目录哈希记录在 [索引清单](graph/tool_foundation_manifest.json)。

## 运行环境与维护

安装和账号／权重下载见[项目 README](../README.md)。日常激活 `SciTool-Unified`，执行器按 [routing.json](../configs/environments/routing.json) 自动使用其余三个环境：`SciTool-LLM`、`SciTool-RXN-Local`、`SciTool-Chroma`。无需手工为每个工具切换环境。

账号配置放在 `.local/credentials/services.env`，本机路径放在 `runtime.env`。所需配置键和对应工具由 [tool_resources.json](../configs/tool_resources.json) 从当前目录派生。`PaperQA` 自身使用配置的本地生成／embedding worker；即使 baseline 使用生成 API，也仍需准备该工具的模型和解释器。

```bash
python -m scripts.tools.build_catalog
python -m scripts.tools.build_graph --embed
python -m scripts.tools.check_foundation
```

如需运行工具回归，在科学工具环境安装测试依赖：`python -m pip install -e ".[test]"`。例如 `python -m pytest -q tests/tools/test_chemical_consolidation.py tests/tools/test_chemical_transport_consolidation.py`，以及 `python -m unittest tests.runtime.test_tool_contract_runtime tests.tools.test_general_ml_consolidation tests.tools.test_biology_consolidation tests.tools.test_material_consolidation`。这些测试读取当前目录契约，不依赖本机审计归档。

第一步检查当前实现并同步源码／资源清单；第二步重建图谱，使用已配置的 embedding API 编码变化的功能描述并复用身份、文本匹配的向量；第三步验证注册、契约、图谱链接、向量及静态资源。静态预检不执行所有外部工具，实时服务可用性需按实际输入验证。

## 实现效率与可用性

共享计算、按需导入与规范 ID 批量查询减少重复工作；模型／分词器缓存仅在同一进程内生效，默认独立 worker 不共享模型。缓存不会替代真实预测，也不改变科学方法、单位或结果含义。

静态预检、离线工具回归和真实服务调用代表不同验证范围。`check_foundation` 验证注册、契约、资源与索引的一致性，不证明所有远端服务此刻可用。完整参考中的实际成功覆盖见[500 题分析](../docs/benchmark_analysis/README.md)。实时调用仍可能因凭据、网络、排队、限流或模型资源失败，应保留原始反馈。工具版本改变后，既有实验成绩不能直接解释为新版本成绩。
