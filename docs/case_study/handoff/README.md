# SMAS-0070 案例展示交接资料

本文写给接手案例绘图、论文插图和案例分析的同事。**现有图稿尚未获得认可，可以重新设计布局；需要保留的是事实、数据和因果关系，而不是当前版式。**

建议先读第 1、3、5、10 节，再使用 `mode_vectors.csv`、`task_graphs.json` 和 `case_data.json` 绘图。完整原始证据也包含在交接压缩包中，无需连接模型服务或访问原服务器。

## 1. 交付目标与案例主线

用户希望得到类似 `SciToolFlow/SciMas/case.png` 的学术案例图：看图就能理解科学问题、方法执行流程和结果，文字少，信息具体；不希望用多个说明框堆出一张“文字海报”。参考图来自 SciToolAgent，只参考其视觉表达，不能照搬其顺序工具链作为 SciMas 的实际执行结构。

本例推荐的叙事是：

> 从一份水分子振动计算记录出发，SciMas 分解读取与矩阵分析任务；运行时发现模式张量与计划矩阵的形状冲突，通过局部修复建立正确的数据绑定，继续完成两种度量下的分析，并得到正确答案。

读者最好能在图中直接看到三件事：

1. **科学对象是什么：**同一个水分子的三个振动模式，不是三种不同的分子。
2. **SciMas 做了什么：**构造有依赖关系的任务图；Reviewer 指出具体冲突；Repairer 改动相关节点，而不是让整题重新开始。
3. **结果是什么：**普通与加权 Gram 矩阵及其谱、频率、IR 强度占比；最终答案正确。

本例的主要展示价值是“图编排 + 具体评审 + 局部修复”。并行有实际证据，但这里只能展示发生过并行，不能用它估算完整方法的加速比。候选早停没有发生。

## 2. 案例身份、运行背景与文件入口

| 项目 | 内容 |
| --- | --- |
| 任务 ID | `SMAS-0070` |
| 数据集／变体 | 正式 Full 运行的 Mini-100；SciMas `full` |
| 基础模型 | `deepseek-flash`，API 后端 |
| 数据集学科标签 | `Material`；具体内容是分子振动计算记录分析 |
| 开始／结束时间 | 2026-11-07 13:04:16.979895 至 13:13:00.754792，北京时间 |
| 工具并发配置上限 | 4；实际观察到的同时执行峰值为 2 |
| 原始轨迹 | `exp/main_scimas/trajectories/SMAS-0070/trajectory.json` |
| 原始源文件 | `tasks/mini-100/assets/SMAS-0070_water_source.qout` |
| 题目状态 | 运行完成，最终答案正确，编排检查通过 |
| 选择方式 | 从正式结果中按科学可视化与机制可展示性挑选；不是随机抽样 |

压缩包解压后的内容：

| 文件 | 用途 |
| --- | --- |
| `README.md` | 本交接文档 |
| `case_data.json` | 全部科学数值、原题、评分、原文评审、修复记录、检索与契约信息 |
| `tool_calls.json` | 12 次真实调用的参数、完整输出、观测 ID、工具运行起止时间 |
| `task_graphs.json` | 修复前后两版图、节点定义、数据依赖边、每条边引用的输出路径 |
| `event_timeline.csv` | 56 条日志事件，含角色、步骤 ID、记录时刻、动作类型 |
| `mode_vectors.csv` | 9 行：3 个模式 × 3 个原子；坐标、位移、频率、强度均可直接导入绘图软件 |
| `source/trajectory.json` | 未改写的完整运行轨迹，约 5.7 MB |
| `source/water.qout` | 未改写的固定 Q-Chem 输出；含分子几何与振动数据 |
| `reference/SciToolAgent_case.png` | 用户认可的参考图 |
| `draft/SMAS-0070.png/.svg/.pdf` | 当前未获认可的图稿，可取用素材，不必沿用布局 |
| `draft/build_case.py` | 当前绘图与数值复核源码；在原仓库环境中运行，脱离仓库需改输入路径 |
| `manifest.json` | 包内各文件的大小和 SHA-256，便于校验 |
| `verify.py` | 解压后独立校验文件哈希、原始数据、七个答案字段与绘图数据；需要 NumPy |

仓库中的交接目录不重复存放 5.7 MB 原始轨迹；上述 `source/`、`reference/`、`draft/` 在 ZIP 中齐全。ZIP 是完整可移交版本，不能只发送仓库里的交接子目录后声称已包含原始文件。

`tool_calls.json` 中的调用参数保留了运行时绝对路径，这是历史记录。移交后的同一源文件是 `source/water.qout`，按 SHA-256 确认相同即可，不需要创建那些原机器路径。原始轨迹没有被改写成可迁移路径。

## 3. 科学问题：输入、要求和物理含义

### 3.1 本题实际输入

输入是一份**已经完成**的水分子 Q-Chem 输出。题目要求读取其中打印的三个模式及其频率、IR 强度，保留文件原始顺序，不能另做量子化学计算或替换为其他水分子数据。

核心题意中文转述：

- 读取三个模式的位移张量、三个频率、三个 IR 强度。
- 每个模式按 `[O_x,O_y,O_z,H1_x,H1_y,H1_z,H2_x,H2_y,H2_z]` 展开为一行，组成 `M(3×9)`。
- 报告普通 Gram 矩阵 `M Mᵀ`。
- 使用题目指定的 `D=diag(4,4,4,1,1,1,1,1,1)`，报告加权 Gram 矩阵 `(MD)(MD)ᵀ`。
- 报告这两个矩阵各自的升序特征值。
- 报告每个模式的 IR 强度占总强度的比例。
- 不得先假定打印的、经过舍入的模式向量在任何一种度量下已经标准正交。

完整英文原题、输入与答案 schema 保存在 `case_data.json → public_task_as_logged`。用于图中的 Query 可以压缩，但不能把上述任务改成“预测振动频率”或“重新计算水分子 IR 光谱”。

### 3.2 分子几何与位移张量

源文件的 `Standard Nuclear Orientation (Angstroms)`：

| 原子索引 | 元素 | x / Å | y / Å | z / Å |
| --- | --- | ---: | ---: | ---: |
| 0 | O | 0.1825093492 | 1.9982356762 | 0.3462438878 |
| 1 | H | 1.0251599245 | 1.7199646670 | −0.0243739112 |
| 2 | H | −0.4433491748 | 1.9155221064 | −0.3791616702 |

模式位移按 `[mode][atom][x,y,z]` 保存，形状为 `3×3×3`：

| 模式 | 原子 | dx | dy | dz |
| --- | --- | ---: | ---: | ---: |
| 1 | O | 0.013 | −0.022 | −0.066 |
| 1 | H1 | 0.313 | 0.116 | 0.621 |
| 1 | H2 | −0.519 | 0.227 | 0.420 |
| 2 | O | −0.010 | 0.016 | 0.047 |
| 2 | H1 | 0.641 | −0.200 | −0.240 |
| 2 | H2 | −0.483 | −0.048 | −0.504 |
| 3 | O | −0.068 | 0.009 | −0.017 |
| 3 | H1 | 0.612 | −0.202 | −0.270 |
| 3 | H2 | 0.464 | 0.061 | 0.537 |

位移数值应保持源文件的归一化约定，不应直接当作以 Å 为单位的实际振幅。坐标用于画分子形状；位移用于画运动方向。两者的显示比例可以调整，但必须对整张图统一处理。

绘图建议：把坐标与位移用**相同的旋转／投影矩阵**转到分子平面，不能只旋转几何而不旋转箭头。可采用球棍模型、投影箭头、淡色正负位移轮廓，或短动画。对单个模式整体反转所有箭头是相位选择，不改变模式；只反转某一个原子的箭头会改变其含义，不可随意操作。若给模式添加弯曲／伸缩等命名，应作为对位移的物理解读另行确认；数据中的正式标识只是 Mode 1、2、3。

### 3.3 为什么需要两个 Gram 矩阵

`G_ij` 是第 i 与第 j 个模式向量的普通内积。对角线反映各模式的平方范数，非对角线反映不同模式之间的内积。标准正交的向量组会给出单位阵。

题目中的 `D` 在氧的三个分量上乘 4。计算 `(MD)(MD)ᵀ` 时，氧的内积贡献乘以 16，因此实现指定的 O:H = 16:1 权重。这里的 16:1 是题目约定，不是要求读取源文件中的精确同位素质量。

三个概念必须区分：

- **振动频率**：从源文件读取，单位 cm⁻¹。
- **IR 强度**：从源文件读取，单位 km·mol⁻¹；占比是把三项强度按总和归一化。
- **Gram 特征值**：由模式位移及指定度量计算得到，不是频率，也不能逐一当作与 Mode 1／2／3 一一对应的物理频率。

`plain_spectrum` 和 `weighted_spectrum` 里的 spectrum 指矩阵特征值谱。图中建议写 “Gram eigenvalues”，避免读者理解成 IR 光谱。

## 4. 全部科学结果与独立核验

展平后的 M：

```text
[ 0.013, -0.022, -0.066,  0.313,  0.116,  0.621, -0.519,  0.227,  0.420 ]
[-0.010,  0.016,  0.047,  0.641, -0.200, -0.240, -0.483, -0.048, -0.504 ]
[-0.068,  0.009, -0.017,  0.612, -0.202, -0.270,  0.464,  0.061,  0.537 ]
```

普通 Gram 矩阵：

```text
[[ 0.999365,  0.052910, -0.000935],
 [ 0.052910,  1.000655, -0.000171],
 [-0.000935, -0.000171,  1.000628]]
```

其升序特征值：

```text
[0.9470905204117459, 1.0006219536213476, 1.0529355259669064]
```

加权 Gram 矩阵：

```text
[[ 1.074500, -0.000850, -0.000335],
 [-0.000850,  1.039130,  0.000204],
 [-0.000335,  0.000204,  1.075538]]
```

其升序特征值：

```text
[1.0391085313449258, 1.0744174698743065, 1.0756419987807677]
```

频率与强度：

| 模式 | 频率 / cm⁻¹ | IR 强度 / km·mol⁻¹ | 占比（未乘 100） | 图中可标注 |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1590.33 | 106.754 | 0.40789237394018824 | 40.79% |
| 2 | 3884.52 | 26.209 | 0.10014098983268442 | 10.01% |
| 3 | 3980.89 | 128.758 | 0.4919666362271274 | 49.20% |

总 IR 强度为 `261.721 km/mol`。两个 Gram 矩阵都不是单位阵。可以从图中强调普通 Gram 的 `(1,2)` 内积为 `0.05291`，加权后为 `−0.00085`，但不要将“非对角项较小”误写成“加权后已经标准正交”：加权矩阵的对角项依然不等于 1。

七个答案字段均已通过以下独立核验：

1. 校验原始轨迹 SHA-256 与正式评分记录一致。
2. 校验源文件 SHA-256 与工具输出中的源哈希一致。
3. 从源文件重新读取位移、频率和 IR 强度，核对轨迹。
4. 使用 NumPy 从 M 复算两种 Gram 矩阵、特征值、强度占比。
5. 与最终答案逐字段比较，本机最大绝对差为 0；脚本设定复算容差为绝对和相对各 `1e-12`。

以上是对固定数据的复核，不是重新跑一条智能体轨迹。图表可以舍入，机器可读数据保留完整精度。

## 5. SciMas 实际工作流与局部修复

### 5.1 规划与工具信息获取

本例包含需求分解、两轮规划检索、一次 `DescribeTools` 查询、图生成与图评审。检索记录位于原轨迹的 `planning.retrievals`，**顶层 `retrievals` 为空不代表没有检索**。

`DescribeTools` 查询了最终使用的七种科学工具。规划检索是选取候选能力，检索到的候选不是实际工具调用；不能把候选检索结果全部画成执行过的节点。

初始计划有 9 个科学节点。第一次生成图时还发生过一次协议校验错误，Planner 随后形成了可运行的图。图级 Reviewer 最初批准该图，但运行阶段实际数据暴露了形状假设错误。因此本例体现的是**运行期发现并修正问题**，不是规划阶段已经消除了全部问题。

### 5.2 问题具体在哪里

初始节点 `modes` 使用 `ReadQChemFrequencyModes` 读取位移，但其 `checks` 误声明输出 `value` 为 `3×9`；`weighted_modes` 和 `plain_gram` 也直接把 `modes.value` 当成矩阵引用。

工具第一次读取成功，实际返回正确的 `3×3×3` 张量：

```text
计划：modes.value[mode][component]                 → 3×9
实际：modes.value[mode][atom][cartesian_component] → 3×3×3
```

这不是 API 故障，不是解析器崩溃，也不是输出被截断。错误来自计划对工具输出结构的假设。直接用 `3×3×3` 张量参与普通二维矩阵乘法不符合题意。

### 5.3 Reviewer 与 Repairer 的具体动作

Reviewer 在结果阶段明确指出三个问题：`modes` 的输出检查形状错误；`weighted_modes` 的输入绑定错误；`plain_gram` 的输入绑定错误。它建议保留原始张量形状，再按原子顺序显式展平。

Repairer 提交了新图，实际改动为：

| 节点 | 修复前 | 修复后 |
| --- | --- | --- |
| `modes` | 检查 `3×9` | 检查真实 `3×3×3`，更新语义描述 |
| `mode_matrix` | 不存在 | 新增节点，以嵌套索引绑定 27 个分量，构造 `3×9` 的 M |
| `weighted_modes` | 直接读 `modes.value` | 读 `mode_matrix.values`，再乘列权重 |
| `plain_gram` | 直接读 `modes.value` | 读 `mode_matrix.values` 及其通过索引构造的转置 |

重要实现细节：`ScaleNumericMatrix` **没有隐式把张量展平成矩阵**。展平是 SciMas 图中的显式输入绑定完成的；新增节点调用 `ScaleNumericMatrix` 时没有设置缩放因子，因此返回同一个矩阵。这一点可在 `tool_calls.json` 的 `o0006.arguments.values` 和输出的缩放标志中核验。图上可以把该操作简写为 “Flatten”，但图例或交接数据必须保留它对应的是显式绑定加不缩放的 `ScaleNumericMatrix`，不是一个叫 `Flatten` 的真实工具。

修复后图有 10 个科学节点，新图经过 Reviewer 评审。`ReadQChemFrequencyModes` 又执行了一次，后继计算继续完成。

### 5.4 哪些结果保留了，哪些没有

修复记录中的：

```text
added_nodes = [mode_matrix]
changed_nodes = [modes, plain_gram, weighted_modes]
retained = []
```

需要失效的范围是 `mode_matrix`、`modes`、`plain_gram`、`plain_spectrum`、`weighted_gram`、`weighted_modes`、`weighted_spectrum`。这个列表包含当时尚未运行的后继节点，**不代表已经执行并丢弃了七次工具结果**。

IR 读取在修复前已经发出，实际于约 206.929 秒完成，但工具结果事件到 `s000018` 才被处理、随后在新图下接受。它只调用了一次；`retained=[]` 表示没有此前已验收节点被登记为缓存保留。因此准确说法是“局部修复没有重启全任务，独立的在途 IR 调用无需重复”，而不是“复用了大量已验收缓存”。

## 6. 修复后任务图：节点、边与角色

### 6.1 十个最终科学节点

| 节点 ID | 真实工具名 | 输入来源与操作 | 核心输出 | 最终观测 |
| --- | --- | --- | --- | --- |
| `modes` | `ReadQChemFrequencyModes` | 同一 `qchem_file` | `value`: 3×3×3 | `o0004` |
| `frequencies` | `GetMolecularFrequencies` | 同一 `qchem_file` | `value`: 3 个频率 | `o0007` |
| `ir` | `ReadQChemIRIntensities` | 同一 `qchem_file` | `value`: 3 个强度 | `o0003` |
| `mode_matrix` | `ScaleNumericMatrix` | 显式展开 `modes.value`，不施加缩放因子 | `values`: M，3×9 | `o0006` |
| `weighted_modes` | `ScaleNumericMatrix` | M；`column_factors=[4,4,4,1,1,1,1,1,1]` | `values`: MD，3×9 | `o0008` |
| `plain_gram` | `MatrixMultiply` | `left=M, right=Mᵀ`；转置通过索引绑定构造 | `product`: G，3×3 | `o0009` |
| `weighted_gram` | `MatrixMultiply` | `left=MD, right=(MD)ᵀ` | `product`: G_D，3×3 | `o0010` |
| `plain_spectrum` | `SymmetricEigenDecomposition` | G | `eigenvalues`: 3 个升序值 | `o0011` |
| `weighted_spectrum` | `SymmetricEigenDecomposition` | G_D | `eigenvalues`: 3 个升序值 | `o0012` |
| `intensity_fractions` | `NormalizeNumericRows` | 把 3 个强度放成 1×3 的一行 | `proportions[0]`: 3 个占比 | `o0005` |

### 6.2 完整的节点依赖边

```text
source ──► frequencies ─────────────────────────────► final answer
       ├─► ir ──► intensity_fractions ───────────────► final answer
       └─► modes ──► mode_matrix ─┬─► plain_gram ─► plain_spectrum
                                 └─► weighted_modes ─► weighted_gram ─► weighted_spectrum
```

上述 source 和 final answer 是解释性的输入／汇总位置，不是新增科学工具。G、G_D 本身也需要写入最终答案，而不是仅提交它们的谱。严格的工具节点间依赖边共 7 条，详细引用路径在 `task_graphs.json`。

Reviewer／Repairer 属于控制与反馈层，应采用与数据依赖不同的线型或颜色。原始数据流箭头不应被画成 Reviewer 产生科学数值；Reviewer 是验证，Repairer 是修正计划，数值由工具产生。

### 6.3 各角色在本例中的实据

| 角色／模块 | 本例中的记录 |
| --- | --- |
| Planner | 5 次模型决策，含需求分解、工具信息查询／检索、图生成和协议纠正 |
| Executor | 10 次模型决策，负责提出可运行节点的调度动作 |
| Reviewer | 15 次模型决策，含初图／修复图评审、科学结果审核及最终答案审核 |
| Repairer | 1 次模型决策，应用 1 次局部修复 |
| Summary | 1 次模型决策，通过引用已验收观测组装最终答案 |
| 经验记录 | 轨迹尾部保存了 20 条角色接口经验；不能仅凭这些记录断言其带来了收益或跨任务迁移 |
| 早停 | 无候选门控／剪枝事件 |

角色调用总计 32 次。这个数量可以帮助分析开销，通常不必全部塞进主图。

## 7. 实际调用时间线与并行证据

下表时间是距任务开始的秒数，取自实际工具执行区间，不是模型产生调度文本的时刻。

| 观测 | 节点 | 工具 | 开始 / s | 结束 / s |
| --- | --- | --- | ---: | ---: |
| o0001 | discovery | DescribeTools | 43.783 | 43.829 |
| o0002 | modes，第 1 次 | ReadQChemFrequencyModes | 202.023 | 206.093 |
| o0003 | ir | ReadQChemIRIntensities | 204.301 | 206.929 |
| o0004 | modes，第 2 次 | ReadQChemFrequencyModes | 314.503 | 317.687 |
| o0005 | intensity_fractions | NormalizeNumericRows | 331.113 | 332.584 |
| o0006 | mode_matrix | ScaleNumericMatrix | 355.588 | 356.978 |
| o0007 | frequencies | GetMolecularFrequencies | 371.882 | 375.096 |
| o0008 | weighted_modes | ScaleNumericMatrix | 406.457 | 407.992 |
| o0009 | plain_gram | MatrixMultiply | 406.595 | 408.367 |
| o0010 | weighted_gram | MatrixMultiply | 419.257 | 420.926 |
| o0011 | plain_spectrum | SymmetricEigenDecomposition | 432.391 | 434.091 |
| o0012 | weighted_spectrum | SymmetricEigenDecomposition | 456.826 | 458.842 |

只有两组实际执行重叠：

- `o0002` 与 `o0003`：204.300714–206.092718 秒，重叠约 **1.792 秒**。
- `o0008` 与 `o0009`：406.595314–407.992395 秒，重叠约 **1.397 秒**。

三个解析节点在依赖图上独立，但频率解析并未与其他两个同时运行；两个特征分解也没有实际重叠。绘制 DAG 时可以并列，绘制时间线时必须遵循实际区间。不要给本例标“3 路同时解析”或“两个谱并行求解”。

模型提出的 `dispatch` 列表不是实际执行承诺。例如它曾同时提出 `modes, frequencies, ir`，实际启动与处理受框架调度影响。展示实际并行应以工具的 `started_seconds` 和 `finished_seconds` 为准。

`event_timeline.csv` 记录完整 56 个日志事件。它的 `recorded_seconds` 是日志事件的记录时刻，不一定等于模型返回完成时刻。工具调用也可能先完成，后进入 `tools` 事件；IR 分支就是例子。

若要写一个简明执行叙事，可以使用这些锚点：

| 步骤 ID | 含义 |
| --- | --- |
| `s000003` | 完成 DescribeTools 查询 |
| `s000005` | Planner 一次协议校验错误 |
| `s000007` | 初始图评审 |
| `s000012` | 首次模式读取返回 |
| `s000013` | Reviewer 要求修复张量／矩阵绑定 |
| `s000014` | Repairer 提交新图 |
| `s000015` | 新图评审 |
| `s000018` | 先前在途的 IR 结果被处理 |
| `s000022` | 模式重新读取完成 |
| `s000028` | 显式展平的 M 返回 |
| `s000054` | Summary 引用观测组成答案 |
| `s000055` | 最终答案评审 |
| `s000056` | 正式提交最终答案 |

另一个容易误读的字段是 `review_state`：一些调用事件仍保存 `pending_review`，因为那是事件写入时的状态。应结合后续 `reviews` 和最终 `results[node].status=valid` 判断是否通过，不能把旧事件快照当成最终未审核。

## 8. 完成情况与指标

| 指标 | 本例结果 |
| --- | ---: |
| 运行完成 | 是 |
| 答案正确 | 是 |
| 编排完成程度 C | 1.000000 |
| 工具选择效率 E | 0.7272727273 |
| 综合规划分 S | 0.8888888889 |
| 科学调用匹配数／计入评分分母数 | 8／11 |
| 总工具调用次数 | 12 |
| 科学工具调用次数 | 11 |
| DescribeTools 调用次数 | 1 |
| 科学工具种类数 | 7 |
| 最终图科学节点数 | 10 |
| 模型请求数 | 32 |
| 输入 token | 570,176 |
| 输出 token | 84,957 |
| 合计 token | 655,133 |
| 实际运行时间 | 523.775080636 秒 |
| 通信故障扣除时间 | 0 秒 |
| 协议错误／局部修复次数 | 1／1 |

11 次科学调用与 10 个最终科学节点的差别来自模式解析器重跑一次。科学调用次数不等于工具种类数，也不等于模型请求数。DescribeTools 计入资源统计，但不计入本例科学规划分的分母。

本例 `C=1, E=8/11`，所以 `S=3CE/(2E+C)=8/9`。评分器匹配 8 次调用，不意味着其他 3 次都没有作用，也不宜把该例画成“零冗余、规划满分”。答案正确是单例布尔结果，不代表整个 Mini-100 的答案准确率为 100%。

输出 token 沿用正式结果中的供应商统计口径。累计输入 token 是 32 次模型请求的总和，不是一次上下文长度。实际工具执行时间很短，523.78 秒还包括模型规划、评审、修复、汇总及框架开销，不能用几个工具条的重叠量直接推出整个任务的加速比。

## 9. 可以展示的论点与边界

| 可以据此展示 | 不应据此宣称 |
| --- | --- |
| 工具知识查询、图规划与运行期校验组成了完整工作流 | 检索出的每个候选工具都实际执行了 |
| 实际数据暴露了计划中的形状假设错误 | 工具实现坏了／外部 API 出错了 |
| Reviewer 给出了具体且可执行的反馈 | Reviewer 从最初规划开始就没有遗漏问题 |
| Repairer 更改相关节点及绑定后继续求解 | 一次修复替换了整个方法或重新解了一遍题 |
| 两组调用确实存在执行时间重叠 | 所有独立节点都达到最充分并行或有某个确定加速倍数 |
| 独立的 IR 调用没有被重复执行 | 修复复用了多项已验收缓存，或节省了某个未经测量的成本 |
| 最终七个字段正确，可从固定源文件重算 | 进行了新的量子化学模拟或实验验证 |
| 普通／加权度量给出不同的 Gram 矩阵 | 加权后一定已经正交或标准正交 |
| 本例记录了角色经验 | 已证明经验迁移带来性能提升 |
| 本例支持评审与局部修复的过程展示 | 本例同时证明了候选早停机制 |

这些边界放在图注或附属案例文字即可，不需要把整张表画进图里。

## 10. 交给绘图同事的具体设计建议

### 10.1 可以重新安排的视觉结构

推荐尝试 3–4 个面板，但不要求沿用当前草图：

- **科学问题入口**：一份 `.qout` 文件／水分子图标，配一句问题。
- **SciMas 主过程**：精简的依赖图，读出分支与普通／加权计算分支要清楚；把 Reviewer—Repairer 画成返回任务图的反馈回路。
- **局部修复放大框**：3 个 `3×3` 小网格叠层，变成一个 `3×9` 矩阵。形状冲突用符号表示，修复后绑定用高亮边表示。最好能看出修复前与修复后的区别。
- **科学结果**：三个水分子模式、IR 条形／棒状图，以及 Gram 对比。结果可以不全塞进主图，完整数字已在交接文件中。

参考图值得借鉴的是视觉层次：顶部任务与规划，中间工具过程，底部真实科学图形和结果。不是必须使用相同颜色或一模一样的框数。

### 10.2 内容优先级

主图应优先保留：水分子三个模式、任务图分叉、真实形状冲突、具体修复、关键科学输出。其次是工具名和少数关键数值。运行配置、32 次请求、完整轨迹日志、长公式推导、所有性能指标不必出现在主图。

如果工具名过长，可以换行或使用能力短名，但必须在图例映射回真实名称，例如：

| 图中短名 | 实际名称／含义 |
| --- | --- |
| Mode parser | ReadQChemFrequencyModes |
| IR parser | ReadQChemIRIntensities |
| Frequency parser | GetMolecularFrequencies |
| Flatten | 显式索引绑定 + 不缩放的 ScaleNumericMatrix |
| Column scaling | ScaleNumericMatrix |
| Gram product | MatrixMultiply |
| Eigensolver | SymmetricEigenDecomposition |
| IR normalization | NormalizeNumericRows |

### 10.3 科学结果的可选画法

- **分子振动图**：优先提升球棍模型质感、运动箭头与构图；这是最接近参考图“科学对象可视化”的部分。
- **IR 图**：可以横轴用 Mode 1／2／3、纵轴用占比；也可以横轴用真实频率、纵轴用原始强度，画三根离散谱线。后一种画法频率位置必须真实，不能把 1590.33、3884.52、3980.89 当作等间距。
- **Gram 图**：可用矩阵排版、统一色标的热图、或者只标出关键非对角项并将完整矩阵放补充材料。热图不能暗中独立缩放使两个矩阵看起来相同。
- **谱对比**：可以画特征值点图，并以 1 为参考线，直观显示不等于单位阵；三点代表排序后的特征值，不应标成三个分子的振动频率。
- **修复图**：初始错误连线用虚线或断线，修复插入的展平操作用高亮。不要把错误输出伪造为工具抛出的异常文本。

### 10.4 可直接使用的简短文字

英文标题候选：`Auditing water vibrational modes with SciMas`

图中 Query：

> Audit three printed water vibration modes and IR intensities under ordinary and O:H = 16:1 weighted metrics.

反馈短语：`Expected 3 × 9; observed 3 × 3 × 3`

修复短语：`Explicit atom-major flattening`

结果短语：`Correct final answer` 或 `Verified against the source record`

候选中文图注：

> SciMas 对固定水分子振动记录的分析案例。任务图分解频率、IR 强度和模式位移分析；运行期校验发现三维张量与二维矩阵的形状冲突，局部修复通过显式展平更新后继绑定。分子振动示意和数值结果均来自同一份计算记录，最终答案通过验证。

候选英文图注：

> SciMas audits a fixed water vibrational calculation. Its task graph separates frequency, intensity, and displacement analysis. Runtime review identifies a tensor–matrix shape mismatch, and local repair inserts explicit atom-major flattening before downstream matrix operations. Molecular displacements and numerical results are derived from the same source record; the final answer passes verification.

这些文字是建议表述，不是从模型原始响应中逐字摘录。若需要把 Reviewer／Repairer 的对话放进图中，优先使用 `case_data.json` 的原文；压缩或翻译后应标明是摘要。

## 11. 现有图稿不足与允许调整的范围

用户对现有图稿的反馈是“效果一般”。接手时不要把现有图当作已批准的版式。当前主要待改进之处是工具框仍占较大面积、过程与结果的视觉重点还可以更集中、分子示意较简单、修复反馈尚可做得更直观。

可以自由调整版式、色彩、字体、图形质感、节点分组、输出呈现方式；不要更改真实数值、增添未执行工具、混入其他题的早停过程、或把有缺陷但被修复的轨迹改写成从未出错的完美计划。

若希望额外展示早停，可另做 SMAS-0004 的补充小案例，不能拼接为 SMAS-0070 的一部分。本文交接包只为 SMAS-0070 提供完整原始证据。

## 12. 复现、验收与查证位置

在原项目根目录：

```bash
conda activate SciTool-Unified
python docs/case_study/build_case.py
python docs/case_study/build_handoff.py
```

这两个脚本不调用模型 API，也不执行科学工具。第一个核验固定数据并重建现有草图；第二个整理交接数据并生成 ZIP。离开仓库后，直接使用包内 JSON／CSV／源文件绘图，不需要先运行这些脚本。

解压后进入 `SMAS-0070_handoff`，在安装了 NumPy 的 Python 环境运行 `python verify.py`，即可独立检查包内文件哈希和科学数据。校验程序只读文件，不会触发 API 或重新生成轨迹。

交接后的独立科学复核只需 NumPy：

```python
import json
import numpy as np

with open('case_data.json', encoding='utf-8') as f:
    d = json.load(f)
M = np.array(d['source_mode_vectors']).reshape(3, 9)
D = np.array(d['metric_diagonal'])
G = M @ M.T
GD = (M * D) @ (M * D).T
I = np.array(d['final_answer']['ir_intensities'])
assert np.allclose(G, d['final_answer']['plain_gram'], atol=1e-12, rtol=1e-12)
assert np.allclose(GD, d['final_answer']['weighted_gram'], atol=1e-12, rtol=1e-12)
assert np.allclose(np.linalg.eigvalsh(G), d['final_answer']['plain_spectrum'])
assert np.allclose(np.linalg.eigvalsh(GD), d['final_answer']['weighted_spectrum'])
assert np.allclose(I / I.sum(), d['final_answer']['intensity_fractions'])
```

建议最终交付至少包括可编辑矢量源文件、PDF、高清 PNG 和一段图注。验收时逐项确认：图中工具与边有来源；分子箭头由真实位移构造；频率、强度、Gram 特征值没有混用；并行描述与时间区间一致；修复过程没有夸大缓存复用；原始轨迹保留；图表舍入不影响科学结论。
