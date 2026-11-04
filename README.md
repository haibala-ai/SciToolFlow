# SciToolFlow

**面向科学工具筛选、编排与证据推理的大语言模型 Benchmark。**

SciToolFlow 提供 **500 道科学任务、472 个科学工具、781 条参考执行轨迹**，覆盖化学、材料、生物／生态、机器学习／数理计算。模型需要理解科学目标、选择工具、衔接参数与数据，并用实际执行证据支撑结论。

- **有层次的任务设计**：100 道高难度科学探究题、50 道工具组合题、350 道正常题。
- **可执行的工具基础**：科学实现、输入输出契约、环境路由、工具图谱与功能向量随项目提供；DescribeTools 支持按需批量查询用法。
- **可核验的参考与评分**：每题提供金标准、必要科学能力、数据依赖与科学判据，参考执行经独立审核。
- **统一的实验边界**：ReAct 与 SciToolAgent 共用工具执行器、模型接口和评分器，支持 API 或本地模型。

[任务分类](tasks/CATEGORIES.md) · [Mini-200](tasks/mini/README.md) · [工具接口](tools/README.md) · [评分细则](evaluation/README.md) · [安装与部署](docs/setup.md)

## 与 SciToolEval Level2 的对比

**更大的任务规模、更高的多工具编排负担，以及可以追溯到实际执行的科学评分。**

SciToolEval 是 benchmark，SciToolAgent 是其 agent 框架。以下对比使用固定上游公开版本与 SciToolFlow 当前正式 500 题。<sup><a id="comparison-cite-1" href="#comparison-note-1">[1]</a></sup>

| 对比维度 | SciToolEval Level2 | **SciToolFlow** | **主要差异** |
| :--- | ---: | ---: | :--- |
| 任务数 | 379 | **500** | **+121 题，+31.9%** |
| 每题参考科学调用均值 | 2.47 | **11.888** | **4.81× 的参考调用负担** |
| 每题参考科学调用中位数 | 2 | **7** | **3.50×** |
| 至少 4 次参考科学调用的任务占比 | 9.5%（36/379） | **89.0%（445/500）** | **+79.5 个百分点** |
| 最长参考科学调用序列 | 11 | **156** | 支持更长的多阶段工作流 |
| 参考覆盖的注册工具数<sup><a id="comparison-cite-2" href="#comparison-note-2">[2]</a></sup> | 113 | **260** | **多覆盖 147 个注册名称** |
| 各自工具池内的参考覆盖率 | 23.69% | **55.08%** | **+31.40 个百分点** |

调用长度反映执行负担，上游按公开工具路径计数，当前按真实参考执行计数；覆盖率按各自注册目录统计。它们不是同条件重跑得到的模型性能提升。<sup><a id="comparison-cite-3" href="#comparison-note-3">[3]</a></sup><sup><a id="comparison-cite-4" href="#comparison-note-4">[4]</a></sup>

![任务规模、参考长度分布与工具覆盖差异](docs/comparison/current.svg)

### 1. 从短工具链，扩展到多阶段科学工作流

原 Level2 的公开参考中，**90.5%** 只有 2–3 次工具调用；SciToolFlow 的主参考中，**89.0%** 达到至少 4 次调用，中位数为 **7 次**。每条主参考至少成功使用两种不同工具，平均成功使用 **4.322 种工具**；平均成功科学调用为 **11.18 次**。

这类工作流要求模型反复完成“选择能力 → 取得证据 → 衔接参数 → 验证结论”，将多项中间结果组织成完整证据链。100 道高难度题进一步考察模型识别、竞争解释、方法选择与证据整合；50 道工具组合题重点考察工具筛选及输入输出衔接。已审核的等价路线可以通过，独立分支可以换序，科学结论仍须满足同样的证据要求。

### 2. 扩展生物、材料与数理工具的实际使用

上游公开路径有 **378/379** 题涉及化学工具，生物与材料分别涉及 **7** 题、**15** 题。SciToolFlow 通过四学科任务设计和独立数理工具类别，扩大科学工具的使用范围。下表的任务涉及数为多标签统计，不同列按各自工具目录分类。<sup><a href="#comparison-note-2">[2]</a></sup>

| 学科／工具类别 | Level2：参考覆盖工具 | **SciToolFlow：成功覆盖工具** | Level2：涉及任务 | **SciToolFlow：涉及任务** |
| :--- | ---: | ---: | ---: | ---: |
| 生物／生态 | 2/85 | **40/86** | 7/379 | **58/500** |
| 材料 | 4/199 | **74/162** | 15/379 | **90/500** |
| 化学 | 107/187 | 67/134 | 378/379 | 64/500 |
| 机器学习／数理 | 无独立注册类别 | **58/65** | 无独立注册类别 | **287/500** |

SciToolFlow 共提供 **472 个规范科学工具＋DescribeTools**，涵盖科学查询、结构处理、统计检验、线性代数、优化与数据组织。工具实现、输入输出 schema、调用形式、失败反馈、环境路由、图谱和功能向量随项目提供，便于 baseline 在同一执行接口下比较。<sup><a href="#comparison-note-2">[2]</a></sup>

任务的**主学科**分布如下；这与上表“是否调用某类工具”的多标签口径不同：

| 主学科 | 高难度题 | 工具组合题 | 正常题 | 总计 |
| :--- | ---: | ---: | ---: | ---: |
| 化学 | 25 | 16 | 102 | **143** |
| 材料 | 25 | 17 | 102 | **144** |
| 生物／生态 | 25 | 17 | 69 | **111** |
| 机器学习／数理 | 25 | 0 | 77 | **102** |
| **合计** | **100** | **50** | **350** | **500** |

![任务类别、参考长度与各学科工具覆盖](docs/benchmark_analysis/overview.svg)

全部题号及摘要见[任务分类](tasks/CATEGORIES.md)，完整分布见[题库分析](docs/benchmark_analysis/README.md)。工具覆盖是对参考使用范围的描述，不是科学能力逐一对齐后的比较；化学工具的覆盖并未在所有口径上提高。<sup><a href="#comparison-note-4">[4]</a></sup>

### 3. 从工具名路径，扩展到可核验的科学执行证据

SciToolFlow 将答案、实际执行与科学判据一起提供：**500 条主参考＋281 条不重复的额外参考，共 781 条完整执行轨迹**。每条轨迹记录真实参数、状态和输出，并关联生成信息与独立审核；额外运行数量不等于不同科学算法的数量。

| 可核验内容 | 所比较的公开 Level2 文件／脚本 | **SciToolFlow** |
| :--- | :--- | :--- |
| 结构化参考答案 | 所比较的答案 JSONL 未提供答案值字段 | **500 份金标准、公开答案 schema 与字段规则** |
| 逐步执行证据 | 所比较的 benchmark JSONL 提供工具路径，未含逐步观测 | **781 条真实轨迹，含参数、输出与状态** |
| 编排判定 | 路径相同直接接受，其余使用 LLM 判断 | **核对必要能力、对象来源、数据依赖与完整方法路线** |
| 答案判定 | 使用 LLM 判断回答与标准答案的一致性 | **显式科学判据、容差、边界与证据支撑联合核验** |
| 评分所需模型 | 公开评分脚本调用生成模型 | **离线规则评分，无需额外 judge API** |

以上结论限定于所比较的公开文件，不推断作者内部数据。<sup><a id="comparison-cite-5" href="#comparison-note-5">[5]</a></sup>

主指标 **Joint** 要求正常完成、必要科学编排和科学答案同时成立。失败与缺交保留在分母；规则尚未识别的新方法进入独立复核。这样既能追查“结论为什么成立”，也能定位失败发生在运行、编排还是科学判断。完整定义与同一道题的算分案例见[评分细则](evaluation/README.md)。

## 项目结构

```text
SciToolFlow/
├── tasks/                 # 500 题、分类文档、输入附件与公开答案 schema
├── tools/                 # 科学实现、统一契约、执行器、图谱与向量
├── baselines/             # ReAct、SciToolAgent 与公共 harness
├── evaluation/            # 统一评分代码、金标准与参考执行证据
├── configs/               # 四个环境、服务参数和无密钥模板
├── resources/             # 科学工具源码、配置、已分发模型与参数
├── docs/                  # 安装部署、评分案例与题库分析
├── scripts/               # 资源准备、运行流水线和数据检查
├── src/                   # 公共模型客户端、文件与路径函数
├── tests/                 # 工具、评分、baseline、运行时与集成测试
├── results/               # 本机预测、轨迹与分数
└── .local/                # 本机密钥、模型权重与缓存，不纳入版本管理
```

Agent 读取公开任务、附件和工具契约；参考答案与科学判据由独立评分器读取。项目不依赖另外下载原始 SciToolAgent 仓库。[开发指南](docs/architecture.md)说明代码入口与依赖关系。

## 安装与配置

运行目标为 **Linux x86_64、Python 3.10**。四个环境分别承载公共科学工具、LLM、反应模型和 Chroma；日常使用激活 `SciTool-Unified`，执行器自动路由到相应环境。

先按[安装指南](docs/setup.md#1-准备安装源)准备指定 GPU wheel 与安装源，再逐条创建环境：

```bash
git clone https://github.com/haibala-ai/SciToolFlow.git
cd SciToolFlow

conda env create -f configs/environments/SciTool-Unified.yml
conda env create -f configs/environments/SciTool-LLM.yml
conda env create -f configs/environments/SciTool-RXN-Local.yml
conda env create -f configs/environments/SciTool-Chroma.yml

conda activate SciTool-Unified
python -m pip install -e . --no-deps --no-build-isolation
```

创建本机配置，已有文件会保留：

```bash
umask 077
mkdir -p .local/credentials
cp -n configs/services.env.example .local/credentials/services.env
cp -n configs/runtime.env.example .local/credentials/runtime.env

python -m scripts.maintenance.prepare_resources
python -m scripts.maintenance.prepare_resources --check
python -m scripts.tools.check_foundation
python cli.py validate
```

| 配置内容 | 在哪里填写或查看 |
| :--- | :--- |
| Conda 环境与科学程序路径 | `runtime.env`；[环境路径说明](docs/setup.md#填写-conda-路径) |
| Materials Project、Chroma 等科学服务账号 | `services.env`；[账号申请地址](docs/setup.md#填写科学工具的账号) |
| 已包含资源与需自行下载的权重、数据、程序 | [资源准备与下载地址](docs/setup.md#准备科学工具依赖的文件) |
| 用于 baseline 的生成 API／本地模型 | [生成模型配置](docs/setup.md#配置生成模型) |
| SciToolAgent 的同源 embedding 服务 | [检索配置](docs/setup.md#scitoolagent-检索配置) |

本地生成模型由使用者选择，可存放在任意可访问目录，通过 vLLM 服务接入。生成 API 与科学服务、检索 embedding 的凭据分开配置。工具绑定和本地资源可静态预检，远程服务是否可用仍取决于账号、网络及服务状态。<sup><a id="comparison-cite-6" href="#comparison-note-6">[6]</a></sup>

## 运行 baseline

| Baseline | 工具选择与执行方式 |
| :--- | :--- |
| [ReAct](baselines/react/README.md) | 初始看到按学科分类的工具名，按需 DescribeTools，逐步调用、观察、思考并提交答案 |
| [SciToolAgent](baselines/scitoolagent/README.md) | 图谱与向量检索、预先规划、逐工具执行、总结及重规划；需要同源 embedding 配置 |

配置生成模型后，先运行一题检查流程。两种 baseline 均支持 `--backend api` 和 `--backend vllm`，`--model` 指定 API 或本地服务中的模型名：

```bash
# API 生成；模型与服务凭据来自配置，也可显式传 --model
python cli.py run --baseline react --backend api --tasks FLOW-0001 \
  --output results/react_demo/predictions.json

# 本地 vLLM 生成；按实际服务填写模型名
python cli.py run --baseline scitoolagent --backend vllm --model "<served-model-name>" \
  --tasks FLOW-0001 --output results/kg_demo/predictions.json

# 全量测试：两个 baseline 使用相同资源策略
python cli.py run --baseline react --backend vllm --model "<served-model-name>" \
  --tasks all --concurrency 2 --output results/react_full/predictions.json
```

默认每题 **400 次生成请求、7,200 秒**，SciToolAgent 所有角色合计计数。科学调用、DescribeTools 与显式 think 无独立次数上限；连续同工具同参数十个决策步后终止。token 用量另行报告，完整边界见[运行资源策略](docs/execution_policy.md)。

运行和评分均支持 `--dataset full|mini`：full 为默认全集 500 题，mini 为四学科各 50 题的精简集。`--tasks` 在所选题库内抽题；Mini 的独立编号与映射见 [Mini-200](tasks/mini/README.md)。

在相同代码、题库、模型和设置下，可向原命令追加 `--resume`；改变指纹后应新建实验目录。

## 测评

```bash
# 抽测时明确题目范围，与预测文件对应
python cli.py score --tasks FLOW-0001 \
  --predictions results/react_demo/predictions.json \
  --output results/react_demo/scores.json

# 正式全量评分，默认以 500 题为分母
python cli.py score --predictions results/react_full/predictions.json \
  --output results/react_full/scores.json
```

| 核心指标 | 回答的问题 | 输出字段 |
| :--- | :--- | :--- |
| Completion | 是否正常完成并符合提交格式与实验资源要求？ | `pass_rate` |
| Planning | 必要科学能力、来源与数据依赖是否全部成立？ | `tool_planning_accuracy` |
| Answer | 科学答案及其必需证据、公开格式是否全部正确？ | `final_answer_accuracy` |
| **Joint** | **以上三项是否同时成立？** | **`joint_success_rate`** |

存在未决审核时，`joint_success_rate=null`，`joint_pass_rate` 仅表示已证实通过的下界。报告最终主指标前须确认 `final_metric_available=true`。部分分、证据覆盖、选择效率与待审处理详见[评分细则](evaluation/README.md)，从实际回执逐项算分见[完整案例](docs/scoring.md)。

| 实验产物 | 内容 |
| :--- | :--- |
| `predictions.json` | 逐题状态、答案、实际调用及运行指纹 |
| `trajectories/*/trajectory.json` | 模型决策、工具观测、资源账本与终止原因 |
| `progress.json` | 运行进度；完成数表示提交完成，科学正确性由评分给出 |
| `scores.json` | 总体指标和逐题诊断 |
| `scores_review_requests.json` | 未决方法／证据复核请求；名称随评分输出文件名变化 |

## 数据与使用范围

当前版本为 **20261026／0.4.0**。没有独立隐藏测试集，研究队列可能复用。任务类别是设计目标，不是按模型成功率划分的难度等级。参考由原生智能体执行并独立复查，不能据此声称已穷尽所有科学方法或替代领域专家验证。

报告实验时请同时给出题库版本、baseline、模型、后端、采样设置、资源策略、任务分母、待审数及 token 用量完整性。科学主指标与运行成本分别报告。

## 许可与来源

代码许可见 [LICENSE](LICENSE)。SciToolAgent baseline 适配自 [HICAI-ZJU/SciToolAgent](https://github.com/HICAI-ZJU/SciToolAgent)，固定来源与实现差异见[baseline 文档](baselines/scitoolagent/README.md)。外部数据、模型与科学程序遵循各自许可和访问条件，详见[资源说明](resources/README.md)。

## 维护与复验

```bash
python cli.py validate
python -m scripts.references.validate_release
python -m scripts.benchmark.analyze_benchmark
python -m scripts.benchmark.compare_release
```

资源准备、实验流水线及部署脚本的具体说明见[安装与部署指南末尾](docs/setup.md#脚本说明)。

## 统计口径与引用

<a id="comparison-note-1"></a>

**[1] 数据来源。** 上游固定为提交 [`ac1cf19f`](https://github.com/HICAI-ZJU/SciToolAgent/tree/ac1cf19fcef84e69f149db6da424afe4e9b2f11f)，当前题库为 `20261026`。来源文件哈希见[上游元数据](docs/comparison/sources/upstream_metadata.json)，全部对比值、变化量和分类口径见[当前统计](docs/comparison/current.json)。<a href="#comparison-cite-1">返回正文 ↑</a>

<a id="comparison-note-2"></a>

**[2] 工具与分类。** 上游按其注册工具组统计，SciToolFlow 按当前规范目录统计。每侧先去重注册名称；SciToolFlow 的 472 个科学工具不含 DescribeTools。原仓库没有独立 MachineLearning 注册组，不表示原算法完全没有数理能力；注册名称的增减也不能解释为新增或删除了同等数量的算法。<a href="#comparison-cite-2">返回正文 ↑</a>

<a id="comparison-note-3"></a>

**[3] 参考长度。** 上游是公开 `tool_path` 序列，当前是主参考实际科学调用，包含失败恢复；两侧均排除 DescribeTools。长度不是模型轮数、依赖深度或任何有效路线的最少调用次数，4.81× 表示参考调用均值之比。<a href="#comparison-cite-3">返回正文 ↑</a>

<a id="comparison-note-4"></a>

**[4] 覆盖与学科。** 上游统计公开路径出现的注册名称，当前统计真实成功执行的注册名称。分母和分类体系不同，覆盖率差是各自目录内统计值之差，不是同一工具池上的控制实验。任务涉及数为多标签，一题可计入多个工具学科；主学科表则每题只计一次。覆盖不等于远程服务实时可用。<a href="#comparison-cite-4">返回正文 ↑</a>

<a id="comparison-note-5"></a>

**[5] 公开证据范围。** 比较对象为固定提交的 `SciToolEval/data/level2_question.jsonl`、`level2_correct_answer.jsonl` 及公开评分脚本。答案 JSONL 中严格解析成功的 378 条记录未发现答案值字段；这不表示作者内部没有金标准或执行轨迹。[路径评分源码](https://github.com/HICAI-ZJU/SciToolAgent/blob/ac1cf19fcef84e69f149db6da424afe4e9b2f11f/SciToolEval/eval/eval_tool_path.py)与[答案评分源码](https://github.com/HICAI-ZJU/SciToolAgent/blob/ac1cf19fcef84e69f149db6da424afe4e9b2f11f/SciToolEval/eval/eval_accuracy.py)说明其 LLM 判定方式。<a href="#comparison-cite-5">返回正文 ↑</a>

<a id="comparison-note-6"></a>

**[6] 执行资源。** 工具的实现、契约和环境路由随项目提供；使用相关工具仍需按[部署指南](docs/setup.md)配置账号、权重、外部程序和网络。静态预检与参考成功不保证全部远端接口持续可用。<a href="#comparison-cite-6">返回正文 ↑</a>
