# SciToolFlow

**用于评估大语言模型科学多工具调用能力的 benchmark。**

SciToolFlow 提供 **500 道多工具任务、546 个任务工具和 ReAct / SciToolAgent 两个 baseline**，覆盖生物、化学、材料与机器学习／数理计算。任务要求模型选择工具、衔接参数、处理执行结果，并提交可核验的结构化答案。

- **任务与执行证据**：每道任务包含公开输入和答案 schema，评分端单独保存参考答案、必要调用路径与工具输出证据。
- **统一工具接口**：工具实现、输入输出契约、图谱与功能向量随项目提供；DescribeTools 支持按需批量查询工具用法。
- **可复现的实验流程**：两个 baseline 共用执行器与评分器，支持 API 和本地模型，分别报告运行完成、工具规划、答案和联合通过率。

[与 SciToolEval Level2 的对比](docs/comparison/README.md) · [任务说明](tasks/README.md) · [工具接口](tools/README.md) · [评分细则](evaluation/README.md)

使用流程为：**安装环境 → 配置工具与模型 → 运行 baseline → 评分与可选 LLM 复核**。下文命令均从 `SciToolFlow/` 根目录执行。

## 项目结构

```text
SciToolFlow/
├── tasks/                       # 公开题目、输入附件和答案 schema
├── tools/                       # 工具实现、契约、worker、图谱与向量
├── baselines/{react,scitoolagent,common}/
├── evaluation/                  # 评分代码、参考答案与执行证据
├── configs/                     # 环境文件、服务参数和配置模板
├── scripts/                     # 模型服务、实验流水线与构建检查
├── results/                     # 实验产生的预测、轨迹与分数
└── .local/                      # 本地密钥、权重和外部资源，不纳入版本管理
```

Agent 运行时只加载公开题目、附件和工具契约；参考答案与参考轨迹由独立评分器读取。项目运行不依赖另外下载原始 SciToolAgent 仓库。

## 安装

运行目标为 **Linux x86_64、Python 3.10**。科学工具按依赖分布在四个 Conda 环境中：

- `SciTool-Unified`：项目入口、测评和大多数科学工具。
- `SciTool-LLM`：vLLM、Transformers 和模型工具。
- `SciTool-RXN-Local`：本地反应模型。
- `SciTool-Chroma`：Chroma 工具。

日常运行只需激活 `SciTool-Unified`，工具执行器会自动选择其余环境的 Python。本地模型与部分科学工具需要 NVIDIA GPU；使用生成 API 不会消除科学工具自身的 GPU 或模型依赖。

### 1. 准备安装源

安装 Conda，并在终端执行 `conda --version` 确认可用。[环境文件](configs/environments/)已列出 Python 和依赖版本，`conda env create` 会依次安装 Conda 与 pip 依赖。

GPU 依赖使用特定构建：需要为 Python 3.10／Linux x86_64 准备 **`vllm==0.21.0+cu129` wheel 和 `xformers==0.0.35` 的 cu128 wheel**。从对应官方发行包或已核验缓存取得 `.whl` 安装包后，放入 `.local/wheels/`；源码仓库不分发这些文件。完整版本见 [LLM 依赖](configs/services/requirements-qwen-vllm.txt)。

```bash
mkdir -p .local/wheels
# 将所需 .whl 文件放入 .local/wheels/ 后，设置安装源。
export PIP_FIND_LINKS="$PWD/.local/wheels"
export PIP_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu https://download.pytorch.org/whl/cu128"
```

### 2. 创建四个环境

逐条执行以下命令，每条成功后再执行下一条。YAML 中的 `name` 决定环境名，命令会创建环境并安装其依赖。

```bash
conda env create -f configs/environments/SciTool-Unified.yml
conda env create -f configs/environments/SciTool-LLM.yml
conda env create -f configs/environments/SciTool-RXN-Local.yml
conda env create -f configs/environments/SciTool-Chroma.yml
```

已有同名环境时跳过对应命令。若报 `No matching distribution found`，按报错中的包名和版本检查安装源；尤其是上述 GPU wheel，缺失时仅复制 YAML 不能完成安装。

### 3. 安装 SciToolFlow

```bash
conda activate SciTool-Unified
python -m pip install -e . --no-deps --no-build-isolation
```

`-e .` 从当前源码目录安装项目，`--no-deps` 保留环境文件安装的依赖。其余三个环境运行独立工具 worker，无需重复安装 SciToolFlow。

### 4. 检查环境

```bash
conda env list
conda run -n SciTool-Unified python --version
conda run -n SciTool-LLM python --version
conda run -n SciTool-RXN-Local python --version
conda run -n SciTool-Chroma python --version
```

四个环境应均报告 Python 3.10。运行实验前，还需完成下文的服务与科学资源配置。环境文件来自开发部署的版本快照，跨机器完整重建尚未验证；NVIDIA 驱动、系统库和专用 wheel 需与目标平台匹配。

## 配置工具与本地资源

服务地址和密钥保存在 **`.local/credentials/services.env`**，环境及资源路径保存在 **`.local/credentials/runtime.env`**。首次使用时从模板创建：

```bash
umask 077
mkdir -p .local/credentials
cp -n configs/services.env.example .local/credentials/services.env
cp -n configs/runtime.env.example .local/credentials/runtime.env
```

程序自动读取这两个文件；已有配置会保留。按实验涉及的功能填写，不使用的服务可留空。

### 填写 Conda 路径

执行 `conda env list` 查看环境位置。在 `runtime.env` 中填写四个环境的父目录，以及 LLM 环境的 Python。例如，环境位于 `/opt/conda/envs/` 时设置：

```dotenv
SCITOOL_CONDA_ENVS_PATH=/opt/conda/envs
SCITOOL_LLM_PYTHON=/opt/conda/envs/SciTool-LLM/bin/python
```

将示例中的 `/opt/conda/envs` 替换为实际的绝对路径。

### 填写科学工具的账号

在 `services.env` 中，将以下变量的值替换为对应服务提供的真实密钥：

- **Materials Project**：填写 `MP_KEY`，供材料数据查询工具使用。
- **Brave Search**：填写 `BRAVE_SEARCH_API_KEY`，供名为 `BingSearch` 的搜索工具使用。
- **ChemSpider**：填写 `CHEMSPIDER_API_KEY`，供 `InChIToCSID` 使用。
- **Wolfram Alpha**：填写 `WOLFRAM_ALPHA_APPID`，供 `WolframAlpha` 使用。
- **Chroma**：填写 `CHROMA_KEY`，供四个 Chroma 设计工具使用。

这些是科学工具的授权，与生成 LLM 的密钥分开。公共 HTTP 数据源还需要网络可达。每项配置对应的全部工具名称可查 [tool_resources.json](configs/tool_resources.json)。

### SciToolAgent 检索配置

在 `services.env` 中设置：

```dotenv
SCITOOL_EMBEDDING_API_BASE=https://aihubmix.com/v1
SCITOOL_EMBEDDING_API_KEY=YOUR_EMBEDDING_API_KEY
```

附带的工具索引使用该服务的 `text-embedding-3-large`、3,072 维、L2 归一化向量。将密钥替换为具有该服务 embedding 权限的密钥；模型与维度由索引元数据指定。ReAct 不需要此配置；SciToolAgent 在使用本地生成模型时仍需要检索 embedding。更换提供商或 embedding 模型需要重建索引。

### 选择生成 LLM

使用本地 Qwen 时，将权重放到 `.local/models/Qwen3.5-9B/`，按下一节启动 vLLM，**无需填写生成 API 密钥**。使用远程 API 时，在 `services.env` 填写 `SCITOOLFLOW_API_BASE`、`SCITOOLFLOW_API_KEY`、`SCITOOLFLOW_API_MODEL`，具体格式见下一节。可选 LLM judge 也使用这套生成配置；纯规则评分不需要 LLM。

### 准备科学工具依赖的文件

科学模型、外部程序及归档数据需要单独准备，安装 Python 依赖不会自动下载它们。按所用工具部署对应资源；默认目录如下：

- 将 ProteinForceGPT 放到 `.local/models/ProteinForceGPT/`，ESMFold 放到 `.local/models/esmfold_v1/`，OmegaFold 权重放到 `.local/models/OmegaFold/`。
- 将 BioT5 的 `biot5-base-*`、`biot5-plus-base-chebi20` 模型目录，以及 Chroma 的 `chroma/` 目录放在 `.local/models/` 下。
- 将 DeepTMHMM2 代码和 checkpoint 放到 `.local/external_sources/DeepTMHMM2/`，其主干权重缓存保留在 `.local/models/torch_cache/`；OmegaFold 代码保留在 `.local/external_sources/OmegaFold/`。
- 将 RXN sandbox 代码放到 `.local/external_sources/rxn-sandbox/`，模型放到 `.local/models/rxn-sandbox/`。
- 将 MOFSimplify 模型放到 `.local/models/MOFSimplify/`；RASPA2 程序、力场和其他科学程序保留在 `.local/external_sources/`。默认 RASPA 可执行文件为 `.local/external_sources/RASPA2/install/bin/simulate`。
- 将 MP、QChem、HIPPIE 归档数据保留在 `.local/reference_data/`，其他缓存保留在 `.local/data/`。

如果把这些资源放到其他位置，在 `runtime.env` 中填写对应的绝对路径：`FORCEGPT_MODEL_PATH`、`ESMFOLD_MODEL_PATH`、`OMEGAFOLD_MODEL_PATH`、`DEEPTMHMM_MODEL_PATH`、`QizhiPei_MODEL_PATH`、`SOLVENT_THERMAL_MODELS`、`RASPA_EXECUTABLE_PATH`。RXN sandbox 等代码中固定使用项目目录的资源应保留上述结构。模型及数据按原项目许可取得。

### 验证安装与工具配置

```bash
python cli.py validate                  # 题目、参考、源码和契约完整性
python scripts/check_foundation.py      # 547 个入口的绑定、环境、资源和图谱静态预检
python cli.py describe PearsonCorrelation
python cli.py call PearsonCorrelation --arguments '{"x":[1,2,3],"y":[2,4,6]}'
```

预检列出缺少的环境、密钥、权重和程序。工具接口是否在线还需实际调用确认；数据包验证与静态预检不需要启动生成 LLM。

## 配置生成模型

两种方式都适用于 **ReAct、SciToolAgent，以及可选 LLM judge**；actor 与 judge 可以选不同后端和模型。

### 本地模型：推荐 vLLM 常驻服务

```bash
# 示例使用 GPU 0、1；按实际可用设备修改 --gpus。
# 启动器自动寻找 SciTool-LLM 的解释器；也可传 --python 指定。
tmux new-session -d -s scitoolflow-model -c "$PWD" \
  "$CONDA_PREFIX/bin/python scripts/model_service.py start --foreground --gpus 0,1 --model-path .local/models/Qwen3.5-9B"
python scripts/model_service.py status
export SCITOOLFLOW_VLLM_BASE=http://127.0.0.1:8016/v1
export SCITOOLFLOW_VLLM_MODEL=Qwen3.5-9B
```

该示例以 TP=2、BF16、显存预算 0.95、上下文 49,152 启动 Qwen3.5-9B，原生 thinking 默认关闭；完整参数见 [qwen_vllm.json](configs/services/qwen_vllm.json)。服务已启动时，`start` 不会修改其设置；更换设备或权重前，先执行 `python scripts/model_service.py stop`。其他模型可通过兼容的本地 vLLM 服务提供，再设置 base/model 变量。`--backend vllm` 连接本机 loopback 服务，不读取生成 API 密钥。

`--backend local` 可直接运行 Qwen Transformers worker：配置 `SCITOOL_MODEL_PATH`、`SCITOOL_LLM_PYTHON`、`SCITOOL_LLM_GPU`，并发必须为 1。它不需要 HTTP 服务；如果同权重的 vLLM 服务已经驻留，会复用该服务。直接 Transformers 使用贪心解码，与 vLLM 采样及结构约束不完全一致，报告结果时须标明后端。

### 生成 API：OpenAI Chat Completions 兼容接口

在 `services.env` 设置：

```dotenv
SCITOOLFLOW_API_BASE=https://your-provider.example/v1
SCITOOLFLOW_API_KEY=YOUR_GENERATION_API_KEY
SCITOOLFLOW_API_MODEL=YOUR_MODEL
SCITOOLFLOW_API_TOKEN_PARAMETER=max_completion_tokens
```

若接口只接受 `max_tokens`，将最后一项改为 `max_tokens`。默认请求 JSON object；不支持时设 `SCITOOLFLOW_API_JSON_MODE=0`，仍做本地协议／答案格式校验。支持 JSON Schema 的服务可显式设置 `SCITOOLFLOW_API_STRUCTURED_OUTPUT=1`；默认不开启。可用 `SCITOOLFLOW_API_EXTRA_BODY` 配置 temperature 等供应商参数，禁止覆盖模型、messages、token 上限和结构协议。HTTP 失败不自动重发付费生成。

将 `YOUR_GENERATION_API_KEY` 和 `YOUR_MODEL` 替换为供应商提供的值。生成 API 与检索 embedding 分别配置，支持使用不同的服务和授权。

## 运行 baseline

先用两条任务确认部署，再运行全部 500 题：

```bash
# 本地 ReAct
python cli.py run --baseline react --backend vllm --tasks FLOW-0285,FLOW-0481 \
  --output results/react_demo/predictions.json
# 生成 API：读取 services.env 中的 SCITOOLFLOW_API_MODEL
python cli.py run --baseline react --backend api --tasks FLOW-0285,FLOW-0481 \
  --output results/react_api_demo/predictions.json
# SciToolAgent：同一套 backend/model 参数
python cli.py run --baseline scitoolagent --backend vllm --tasks FLOW-0285,FLOW-0481 \
  --output results/kg_demo/predictions.json
python cli.py run --baseline scitoolagent --backend api --tasks FLOW-0285,FLOW-0481 \
  --output results/kg_api_demo/predictions.json
```

ReAct 从分类工具名开始，按需调用 DescribeTools，支持 think、inspect、工具调用和 finish。SciToolAgent 依次进行 KG 检索、计划链生成、逐工具执行和总结，支持至多三轮重规划；所有角色的模型请求均计入预算。两者共用执行器、公开答案结构及评分，DescribeTools 不计入科学调用路径。

默认每题最多 80 个决策步、20 次工具发现、8 次显式 think、1,800 秒，每次模型输出最多 4,096 tokens；科学调用预算读取题目的 `max_tool_calls`。同工具同参连续十个决策步后终止，非连续重复不累计。完整参数见 `python cli.py run --help`，协议与实现见 [ReAct](baselines/react/README.md) 和 [SciToolAgent](baselines/scitoolagent/README.md)。比较 baseline 时应固定预算、采样、模型及 API 结构约束能力。

全量运行及自动评分：

```bash
# 选择 scitoolagent 可运行 KG baseline；--backend api 使用已配置的生成 API。
python scripts/run_benchmark.py --baseline react --backend vllm --tasks all --concurrency 2 \
  --output-dir results/react_full
# 可选：本地 actor + API judge；仅处理规则评分留下的 pending 项
python scripts/run_benchmark.py --baseline react --backend vllm --tasks all --concurrency 2 \
  --judge --judge-backend api --judge-model YOUR_JUDGE_MODEL --output-dir results/react_with_judge
```

长任务建议在 tmux 中运行。中断后，在**同一代码、题库和运行设置**下向原命令追加 `--resume`；已记录失败也会保留，只有显式 `--retry-failed` 的单独 run 命令才重做失败题。未写断点的中断题从头运行。代码或模型设置变更时须使用新结果目录，禁止改指纹强行合并。

## 测评

**规则评分纯离线，不调用 LLM。** 默认按全部 500 题计分；抽测必须给 `--tasks`，否则其余题按缺失失败计算。

```bash
python cli.py score --tasks FLOW-0285,FLOW-0481 --predictions results/react_demo/predictions.json \
  --output results/react_demo/scores.json
# 可选本地 judge；也支持 --backend local
python cli.py judge --backend vllm --requests results/react_demo/scores_review_requests.json \
  --output results/react_demo/reviews_local.json
# 可选 API judge，支持与 actor 不同的模型
python cli.py judge --backend api --model YOUR_JUDGE_MODEL --requests results/react_demo/scores_review_requests.json \
  --output results/react_demo/reviews_api.json
# 只有显式传 reviews 才应用复核结论
python cli.py score --tasks FLOW-0285,FLOW-0481 --predictions results/react_demo/predictions.json \
  --reviews results/react_demo/reviews_local.json --output results/react_demo/reviewed_scores.json
```

| 指标（JSON 字段） | 含义 |
| :--- | :--- |
| **Completion** (`pass_rate`) | 正常提交非空答案，未报告失败或科学预算超限；不表示答对 |
| **Planning** (`tool_planning_accuracy`) | 完成任务，真实成功调用的工具、实参与参考依赖匹配；独立分支可以换序，合法短路径可交复核 |
| **Answer** (`final_answer_accuracy`) | 完成任务，必填字段、类型、科学内容、完整数组及显式容差均通过 |
| **Joint** (`joint_pass_rate`) | 同一题 Completion、Planning、Answer 全部通过 |
| `*_strict` | 复核前的规则判定，不因 LLM 复核而覆盖；pending 按未通过计入比例 |
| `pending_*` | 仍需语义／独立审核的题数；没有静默从分母删除 |
| `joint_accuracy_lower_bound / upper_bound` | 当前已通过的比例／可满足条件的 pending 全部通过时的乐观上界，不是统计置信区间 |
| `reference_path_match_rate` | 路径匹配诊断，不以正常完成为前提；不能当作正式 Planning |
| `mean_answer_*_credit_supplied` | 已提供预测的字段／科学叶子微平均部分分；叶子规则去重，不等于整题准确率 |
| `mean_step_recall_supplied` | 已提供预测的必要调用（工具及实参）匹配召回均值；不等于完整计划正确 |
| `mean_tool_occurrence_recall_supplied` | 已提供预测按工具出现次数计算的召回均值；弱于实参／依赖核验 |

比例字段取 0–1；正式主指标分母为所选全部有效题（当前全量为 500），失败和漏交均保留。科学数值按 `abs(pred-ref) <= atol + rtol*abs(ref)` 比较；标识符、单位、对象身份和数组顺序按规则检查。DescribeTools 的实际成本保留，但排除于科学路径、召回和科学预算。

LLM judge **只复核 pending**，不能把明确数值错误、缺字段或 schema 错误改判通过；数据源变化等要求独立审查的项目不自动交给 LLM。API judge 会向所配服务发送问题、参考和完整实际证据；超出上下文的请求保留未决，不截断科学结果。复核绑定参考／预测双哈希；规则分和复核分分别保存，同一弱模型自审不是专家认证。

## 实验产物

| 产物 | 内容 |
| :--- | :--- |
| `predictions.json` | 每题状态、真实 calls、答案、失败原因和运行指纹 |
| `trajectories/*/trajectory.json` | 每步模型决策、观察、预算；KG baseline 还含检索和角色阶段 |
| `progress.json / experiment.json` | 逐题进度／实验阶段；前者的 completed 只是运行完成数 |
| `scores.json / scores_review_requests.json` | 规则分数／待复核证据 |
| `reviews*.json / reviewed_scores.json` | 复核记录／明确应用复核后的分数 |

## 数据版本与使用范围

题库版本为 `20261018-scientific-contract-audit`。500 条参考为经助手逐项审查的暂定版本，尚未划分独立隐藏测试集。任务覆盖和静态部署检查不代表所有外部接口持续可用；学科分布、比较口径与已知限制见[对比页](docs/comparison/README.md)。

报告实验时，应同时记录题库版本、baseline、模型、后端、采样、预算和是否使用 LLM 复核。规则分与复核分分别保留；不同题库或运行指纹的预测不应合并。已有运行与审查记录见 [results](results/README.md)。

## 许可与来源

代码许可见 [LICENSE](LICENSE)。SciToolAgent baseline 适配自 [HICAI-ZJU/SciToolAgent](https://github.com/HICAI-ZJU/SciToolAgent)，来源、固定版本与实现差异见 [baseline 文档](baselines/scitoolagent/README.md)。外部模型、数据和科学程序遵循各自的许可与访问条件。
