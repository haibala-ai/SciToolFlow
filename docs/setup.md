# 安装、配置与部署

本指南说明四个 Conda 环境、科学工具账号、已分发资源、需自行下载的权重，以及生成 API／本地模型的配置。所有命令从 SciToolFlow 项目根目录执行。运行与测评入口见[项目 README](../README.md)，评分定义见[评分细则](../evaluation/README.md)。

## 安装

运行目标为 **Linux x86_64、Python 3.10**。科学工具按依赖分布在四个 Conda 环境中：

- `SciTool-Unified`：项目入口、测评和大多数科学工具。
- `SciTool-LLM`：vLLM、Transformers 和模型工具。
- `SciTool-RXN-Local`：本地反应模型。
- `SciTool-Chroma`：Chroma 工具。

日常运行只需激活 `SciTool-Unified`，工具执行器会自动选择其余环境的 Python。本地模型与部分科学工具需要 NVIDIA GPU；使用生成 API 不会消除科学工具自身的 GPU 或模型依赖。

### 1. 准备安装源

从 [Miniconda 官方安装说明](https://www.anaconda.com/docs/getting-started/miniconda/install)安装 Conda，并在终端执行 `conda --version` 确认可用。[环境文件](../configs/environments/)已列出 Python 和依赖版本，`conda env create` 会依次安装 Conda 与 pip 依赖。

GPU 依赖使用特定构建：需要为 Python 3.10／Linux x86_64 准备 **`vllm==0.21.0+cu129` wheel 和 `xformers==0.0.35` 的 cu128 wheel**。下载入口为 [vLLM v0.21.0 发行页](https://github.com/vllm-project/vllm/releases/tag/v0.21.0)和 [PyTorch cu128 的 xformers 安装包目录](https://download.pytorch.org/whl/cu128/xformers/)；选择对应版本与平台的 `.whl` 后放入 `.local/wheels/`。源码仓库不分发这些文件。完整版本见 [LLM 依赖](../configs/services/requirements-qwen-vllm.txt)。

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

- **Materials Project**：注册并登录 [Materials Project](https://materialsproject.org/)，在 [Dashboard](https://next-gen.materialsproject.org/dashboard)取得 API key，填入 `MP_KEY`。操作说明见[官方 API 入门](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started)。
- **Brave Search**：从 [Brave Search API](https://brave.com/search/api/)进入控制台，开通适用计划并在 API Keys 中创建密钥，填入 `BRAVE_SEARCH_API_KEY`。供名为 `BingSearch` 的工具使用；[官方授权说明](https://api-dashboard.search.brave.com/documentation/guides/authentication)。
- **ChemSpider**：通过 [RSC Developer Portal](https://developer.rsc.org/)注册或登录，申请具有 ChemSpider／Compounds API 权限的密钥，填入 `CHEMSPIDER_API_KEY`，供 `InChIToCSID` 使用。门户可能要求登录；访问权限与申请条件以 RSC 为准。
- **Wolfram Alpha**：在 [Developer Portal](https://developer.wolframalpha.com/)创建应用并取得 AppID，填入 `WOLFRAM_ALPHA_APPID`；[官方 AppID 获取说明](https://products.wolframalpha.com/api/documentation)。
- **Chroma**：从官方仓库提供的[权重授权申请入口](https://chroma-weights.generatebiomedicines.com/)申请下载 token，填入 `CHROMA_KEY`。这是科学工具模型的权重授权；[官方说明](https://github.com/generatebio/chroma#get-started)。

这些是科学工具的授权，与生成 LLM 的密钥分开。公共 HTTP 数据源还需要网络可达。每项配置对应的全部工具名称可查 [tool_resources.json](../configs/tool_resources.json)。

### SciToolAgent 检索配置

在 [AIHubMix 控制台](https://console.aihubmix.com/)创建有 embedding 调用权限的 API key，按[官方密钥管理说明](https://docs.aihubmix.com/cn/console/api-keys)配置。在 `services.env` 中设置：

```dotenv
SCITOOL_EMBEDDING_API_BASE=https://aihubmix.com/v1
SCITOOL_EMBEDDING_API_KEY=YOUR_EMBEDDING_API_KEY
```

附带的工具索引使用该服务的 `text-embedding-3-large`、3,072 维、L2 归一化向量。将密钥替换为具有该服务 embedding 权限的密钥；模型与维度由索引元数据指定。ReAct 不需要此配置；SciToolAgent 在使用本地生成模型时仍需要检索 embedding。更换提供商或 embedding 模型需要重建索引。

### 选择生成 LLM

用于 baseline 的模型由使用者选择，**不限定模型系列，也不要求权重存放在 `.local/`**。本地部署可使用任意兼容的模型目录，通过 vLLM 的服务地址与模型名接入；远程 API 使用 `SCITOOLFLOW_API_BASE`、`SCITOOLFLOW_API_KEY`、`SCITOOLFLOW_API_MODEL`。具体启动方式见下文“配置生成模型”。纯规则评分不需要 LLM。

### 准备科学工具依赖的文件

科学工具使用的资源与驱动 Agent 的生成 LLM 分开配置。仓库直接提供约 **502 MiB** 的固定版本源码、参数、中型预测模型和 tokenizer／配置，尽量减少版本不一致。RXN 的较大权重以分块形式保存，离线准备脚本自动还原，**无需 Git LFS 或手动拼接**。精确体积和逐文件哈希见 [资源清单](../resources/manifest.json)。

**仓库已包含，无需另行下载：**

- **MOFSimplify**：两个小型 HDF5 模型及配套训练／验证／测试表格，约 7.8 MiB，位于 [resources/models/MOFSimplify](../resources/models/MOFSimplify)。
- **DeepTMHMM2 checkpoints**：固定版本的全部 10 个文件，约 125 MiB，已按历史来源记录核对 Git blob；ESM2 主干仍需下载。
- **RXN 预测权重**：Pistachio2025Q2 Forward／Retro 两个完整 checkpoint，合计约 296 MiB，已核对官方 Hugging Face 的 LFS SHA256。准备脚本将分块还原到工具默认目录。
- **外部源码**：OmegaFold、DeepTMHMM2、RXN Sandbox 的源码与 RXN 词表；RASPA2、Zeo++／Voro++ 的可编译源码，以及 Eigen 头文件，位于 [resources/external_sources](../resources/external_sources)。RXN 同时包含其小型 SCScore 支持文件。
- **模型配置与 tokenizer**：ProteinForceGPT、ESMFold 和七个 BioT5 模型的现用配置、词表、tokenizer 与来源许可。它们的大型权重仍需下载；文件哈希及可核验的上游版本见 [模型快照记录](../resources/provenance/model_metadata_snapshots.json)。
- **DSSP 固定安装包**：DSSP 4.0.4、libcifpp 及三个 Boost 库的六个 Ubuntu 22.04 amd64 安装包和相对路径启动器。无需系统级安装，按资源说明离线解包；其他平台安装匹配的版本。
- **力场与参数**：本项目实际使用的 RASPA 力场定义、逐文件 SHA256 清单，以及对应 aiida-lsmo 参数／渲染器和许可。
- **小型归档与来源记录**：MP 公开历史快照及电荷密度索引、DeepTMHMM2 和 HIPPIE 的历史来源记录。HIPPIE 原始数据未打包。
- **公开任务输入**：Q-Chem 输出等任务附件已在 [tasks/assets](../tasks/assets/) 中，无需重复下载。

首次使用时执行一次离线准备，将资源放到工具要求的 `.local/` 路径：

```bash
python -m scripts.maintenance.prepare_resources
python -m scripts.maintenance.prepare_resources --check
```

离线准备脚本的参数与冲突处理见文末“脚本说明”。文件清单、来源许可及编译步骤见 [resources/README.md](../resources/README.md) 和 [resources/manifest.json](../resources/manifest.json)。

**仍需自行下载或安装：**

下列 ProteinForceGPT、ESMFold 和 BioT5 链接直接指向已核验版本的权重文件，配套配置无需重新下载。

- **用于 Agent 的本地生成模型**：自由选择模型，按下文部署；使用远程生成 API 时无需下载其权重。
- **ProteinForceGPT 大型权重**：[lamm-mit/ProteinForceGPT](https://huggingface.co/lamm-mit/ProteinForceGPT/resolve/342569141fb643ac49fd9690e644a859a9c5f881/model.safetensors?download=true)，将 `model.safetensors` 放入 `.local/models/ProteinForceGPT/`；配置与 tokenizer 已包含。
- **ESMFold 大型权重**：[facebook/esmfold_v1](https://huggingface.co/facebook/esmfold_v1/resolve/75a3841ee059df2bf4d56688166c8fb459ddd97a/pytorch_model.bin?download=true)，将 `pytorch_model.bin` 放入 `.local/models/esmfold_v1/`；配置与词表已包含。
- **OmegaFold 权重**：下载 [release1.pt](https://helixon.s3.amazonaws.com/release1.pt)，保存为 `.local/models/OmegaFold/release1.pt`。源码已提供，本工具使用 model 1。
- **DeepTMHMM2 的 ESM2 主干**：从 [ESM 官方模型清单](https://github.com/facebookresearch/esm#available-models)取得 `esm2_t33_650M_UR50D.pt` 与 contact-regression 文件，放入 `.local/models/torch_cache/hub/checkpoints/`。10 个 DeepTMHMM2 checkpoints 无需再次下载，资源准备后位于 `.local/external_sources/DeepTMHMM2/checkpoints/`。
- **BioT5 大型权重**：分别下载 [dti-human](https://huggingface.co/QizhiPei/biot5-base-dti-human/resolve/09c8c777f5d64595574231dd248ae25e4f799684/model.safetensors?download=true)、[peer-binloc](https://huggingface.co/QizhiPei/biot5-base-peer-binloc/resolve/af582313f5c2a50ed16f16c3d0cc1e2129050e70/model.safetensors?download=true)、[peer-human_ppi](https://huggingface.co/QizhiPei/biot5-base-peer-human_ppi/resolve/ef36a858815ca284956e75bfc5609984b870dd3a/model.safetensors?download=true)、[peer-solubility](https://huggingface.co/QizhiPei/biot5-base-peer-solubility/resolve/8243f70fb11b125da21ba145b9f51d8e7466df64/model.safetensors?download=true)、[peer-yeast_ppi](https://huggingface.co/QizhiPei/biot5-base-peer-yeast_ppi/resolve/2643ff69d9ba0e8a0b1c8dea7e1fd49a2f54af39/model.safetensors?download=true)、[text2mol](https://huggingface.co/QizhiPei/biot5-base-text2mol/resolve/a924f57898bbf2d32fd27a1e6270f8775654dccb/model.safetensors?download=true)和 [BioT5+ chebi20](https://huggingface.co/QizhiPei/biot5-plus-base-chebi20/resolve/d9c77cf0ec4c4cd5e1caddf13d892de2e3b18044/model.safetensors?download=true)的 `model.safetensors`，放入 `.local/models/` 下对应同名模型目录；配套配置与 tokenizer 已包含。
- **Chroma 权重**：按 [generatebio/chroma](https://github.com/generatebio/chroma#get-started)申请 token 并配置 `CHROMA_KEY`；权重及校验缓存写入 `.local/models/chroma/`。
- **HIPPIE 完整数据**：约 132 MiB，从[官方下载页](https://cbdm-01.zdv.uni-mainz.de/~mschaefer/hippie/download.php)选择 v2.4 TAB；当前工具读取 `.local/reference_data/HIPPIE/hippie_v2_4_20261013.tsv`。尚未找到明确的再分发许可，因此不随仓库上传。已提供的历史 SHA256 是核验依据；新的 `current` 文件或不同版本不能视为同一快照。
- **科学程序的可执行文件**：RASPA2 和 Zeo++ 在目标机器编译。Ubuntu 22.04 amd64 可直接解包附带的 DSSP 安装包；其他平台按 [DSSP 官方说明](https://github.com/PDB-REDO/dssp)安装。具体命令和路径配置见 [资源说明](../resources/README.md)。

大模型的下载方法见 [Hugging Face 官方文档](https://huggingface.co/docs/huggingface_hub/guides/download)。优先使用[模型快照记录](../resources/provenance/model_metadata_snapshots.json)中核验过的 `verified_revision` 和权重 SHA256，避免下载新版权重却复用旧版配置；不要覆盖已提供的配置和 tokenizer。MP 的完整归档仍从 [MP 官方 AWS 数据集](https://registry.opendata.aws/materials-project/)取得；仓库内的小型快照不代表全部历史对象。服务账号及密钥仍按前文单独申请和配置。

资源放到其他位置时，在 `runtime.env` 设置相应绝对路径：`FORCEGPT_MODEL_PATH`、`ESMFOLD_MODEL_PATH`、`OMEGAFOLD_MODEL_PATH`、`DEEPTMHMM_MODEL_PATH`、`QizhiPei_MODEL_PATH`、`SOLVENT_THERMAL_MODELS`、`RASPA_EXECUTABLE_PATH`、`SCITOOL_ZEOPP_EXECUTABLE`、`SCITOOL_DSSP_EXECUTABLE`。RXN 等固定目录资源保留上述结构。

### 验证安装与工具配置

```bash
python cli.py validate                  # 题目、参考、源码和契约完整性
python -m scripts.tools.check_foundation      # 473 个入口的绑定、环境、资源和图谱静态预检
python cli.py describe PearsonCorrelation
python cli.py call PearsonCorrelation --arguments '{"x":[1,2,3],"y":[2,4,6]}'
```

预检列出缺少的环境、密钥、权重和程序。工具接口是否在线还需实际调用确认；数据包验证与静态预检不需要启动生成 LLM。

## 配置生成模型

两种方式都适用于 **ReAct 和 SciToolAgent**；评分器无需配置生成模型。

### 本地模型：通过 vLLM 接入自选模型

模型可从其发布方或 [Hugging Face 模型库](https://huggingface.co/models)取得，保存到任意可访问目录。选择支持对话生成的模型，确认所安装 vLLM 版本支持其架构，参见 [vLLM 支持模型清单](https://docs.vllm.ai/en/latest/models/supported_models/)。模型系列、规模、量化方式、权重位置和 GPU 数量均由使用者决定。

在独立终端或 tmux 中启动服务。以下 `/absolute/path/to/your-model` 是自选模型的实际目录，`scitoolflow-local` 是对外服务名：

```bash
conda activate SciTool-LLM
CUDA_VISIBLE_DEVICES=0,1 vllm serve /absolute/path/to/your-model \
  --served-model-name scitoolflow-local \
  --host 127.0.0.1 --port 8016 --tensor-parallel-size 2 \
  --dtype auto --gpu-memory-utilization 0.90 --max-num-seqs 2
```

例如单卡部署时，将 `CUDA_VISIBLE_DEVICES` 改为一个设备编号，并将 `--tensor-parallel-size` 改为 `1`。模型的 chat template、上下文上限和原生 reasoning 参数按其官方部署要求设置；[vLLM 服务文档](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/)。

在 `.local/credentials/services.env` 配置相同的地址和服务名，然后回到 `SciTool-Unified` 环境运行 baseline：

```dotenv
SCITOOLFLOW_VLLM_BASE=http://127.0.0.1:8016/v1
SCITOOLFLOW_VLLM_MODEL=scitoolflow-local
```

`--backend vllm` 只连接本机 loopback 服务，不读取生成 API 密钥。使用远程自托管服务时，按下文 API 方式配置地址。运行参数 `--max-input-tokens` 与 `--max-output-tokens` 应为所选模型的上下文窗口预留足够空间；更换模型后使用新结果目录并记录模型版本和采样设置。

通用本地模型使用上述 vLLM 服务接入。项目另附 Qwen 专用启动配置及直接 worker，其适用范围见文末“脚本说明”。

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

## 脚本说明

### 离线资源准备：`scripts/maintenance/prepare_resources.py`

将 `resources/manifest.json` 列出的资源复制到 `.local/`，全程不联网。先验证整批源文件 SHA256，再检查目标：相同文件复用；发现内容冲突则停止，不覆盖本地修改。RXN 分块按记录顺序还原为原始 checkpoint，同时核对各块与完整文件 SHA256，不反序列化模型。准备完成只表示随仓库资源齐全，不表示另行下载的大权重、密钥或科学程序已经配置。

```bash
python -m scripts.maintenance.prepare_resources
python -m scripts.maintenance.prepare_resources --check
# 只准备指定组件，可重复传入 --component。
python -m scripts.maintenance.prepare_resources --component mofsimplify_models
# 使用独立目录检查，不改变工具默认读取路径。
python -m scripts.maintenance.prepare_resources --destination .local/work/resource_staging
```

### 实验流水线：`scripts/benchmark/run_benchmark.py`

依次执行 baseline 和离线评分，结果写入 `--output-dir`。遇到未知科学方法时，评分输出待审证据；完成独立审核并更新共享判据后，重新执行评分。

全量运行及自动评分：

```bash
# 选择 scitoolagent 可运行 KG baseline；--backend api 使用已配置的生成 API。
python -m scripts.benchmark.run_benchmark --baseline react --backend vllm --tasks all --concurrency 2 \
  --output-dir results/react_full
```

流水线与 CLI 的运行和评分均支持 `--dataset full|mini`，默认 full。Mini 的 200 题使用独立编号，直接传 `--dataset mini` 即可运行并按 200 题评分；`--tasks` 只在所选题库中进一步抽题。

### 预检与构建脚本

- `scripts/tools/check_foundation.py`：检查工具绑定、解释器、声明资源、图谱和向量，结果写入 `results/reports/tool_preflight.json`；不调用科学工具或生成 LLM。
- `scripts/benchmark/index_results.py`：为本机结果生成 `results/index.json`，保留原始轨迹和哈希。
- `scripts/benchmark/analyze_benchmark.py`：从当前题库与真实参考重算图表、学科与工具覆盖；不调用科学工具或LLM。
- `scripts/maintenance/freeze.py`：在源码、文档或打包资源变更后重建 `MANIFEST.json`；随后执行 `python cli.py validate` 校验分发文件。

重算当前500题的统计与索引：

```bash
python -m scripts.benchmark.analyze_benchmark
python -m scripts.benchmark.index_tasks
```

与固定 SciToolEval Level2 来源的对比使用 `python -m scripts.benchmark.compare_release` 重算；图表共享绘图模块，按各自的工具池分母统计，口径见根 README。

### Qwen 专用启动配置

项目另提供 [Qwen 部署配置](../configs/services/qwen_vllm.json)及 `scripts/services/model_service.py`，用于已验证的 Qwen 启动参数；该脚本包含 Qwen 专用 reasoning 设置。`--backend local` 也属于 Qwen3.5 专用 Transformers worker，并发为 1，使用 `SCITOOL_MODEL_PATH`、`SCITOOL_LLM_PYTHON` 和 `SCITOOL_LLM_GPU` 配置，可能复用同权重常驻服务。未显式指定 `SCITOOL_LLM_GPU` 时继承启动进程的 `CUDA_VISIBLE_DEVICES`；两者均未指定才使用单卡 0。**其他本地模型使用上面的通用 vLLM 接入方式**，不依赖这两个 Qwen 专用入口。
