# 两种向量检索后端

SciMas 与 SciToolAgent 可独立选择检索模型。生成模型仍由 `--backend`、`--model` 和 `official`／`school` 服务配置控制。

| 检索选项 | 模型 | 维度 | 索引目录 |
|---|---|---:|---|
| `--embedding-backend api` | `text-embedding-3-large` | 3,072 | `tools/graph/`，保留现有索引 |
| `--embedding-backend local` | `Qwen/Qwen3-Embedding-4B` | 2,560 | `.local/indexes/qwen3-embedding-4b/` |

默认使用 API。也可以设置 `SCITOOL_EMBEDDING_BACKEND=local`；命令行选择优先。本地模式不读取远程 embedding 密钥，也不经过环境中的网络代理。API 模式仍按原有 `SCITOOL_EMBEDDING_API_BASE` 和密钥配置工作。

两种模型的向量空间不同，不能交叉查询。后端各自拥有 SciMas 与 SciToolAgent 的索引产物，缓存键包含模型身份、维度与预处理约定。实验指纹绑定实际选择的索引文件，因此不同后端不能混合续跑。

## 本地模型与服务

模型位于 `.local/models/Qwen3-Embedding-4B/`，约 8.06 GB。本机下载自 [Qwen 官方 ModelScope 仓库](https://modelscope.cn/models/Qwen/Qwen3-Embedding-4B)，文件经过 SHA-256 校验；两个权重分片的哈希与 [Hugging Face 官方仓库](https://huggingface.co/Qwen/Qwen3-Embedding-4B) 一致。下载来源和逐文件哈希记录在模型目录的 `download_manifest.json`。该目录由 Git 忽略。

在其他机器上，可用 Hugging Face CLI 下载同一模型：

```bash
conda activate SciTool-LLM
hf download Qwen/Qwen3-Embedding-4B \
  --revision 5cf2132abc99cad020ac570b19d031efec650f2b \
  --local-dir .local/models/Qwen3-Embedding-4B
```

从项目根目录启动 tmux 服务，使用 GPU 0、1：

```bash
conda activate SciTool-LLM
mkdir -p .local/cache/qwen3_embedding
tmux new-session -d -s qwen3-embedding-4b \
  'python -m scripts.services.embedding_service --gpus 0,1 >.local/cache/qwen3_embedding/server.log 2>&1'

curl --noproxy '*' http://127.0.0.1:18081/health
python -m scripts.services.embedding_service --status
```

服务使用已有 `SciTool-LLM` 环境中的 vLLM，加载本地权重并禁止在线拉取。默认双卡张量并行，BF16，最大输入与批处理 token 上限均为 32,768；具体设置见 [qwen3_embedding.json](../configs/services/qwen3_embedding.json)。端口为 `127.0.0.1:18081`，OpenAI 兼容基础地址为 `http://127.0.0.1:18081/v1`，服务模型名为 `Qwen3-Embedding-4B`。

vLLM 使用 last-token pooling 和归一化。Qwen 的 tokenizer 在输入末尾附加 `endoftext`。服务启动时校验模型文件并记录权重／tokenizer 指纹和进程身份；本地索引必须匹配该指纹，服务更换模型后需要重建本地索引。

停止服务并释放两张卡上的该模型：

```bash
tmux send-keys -t qwen3-embedding-4b C-c
```

## 建库与使用

本地索引编码的仍是当前工具功能描述，不读取任务答案或参考轨迹；图谱结构和工具注册信息沿用已有版本。只在查询侧加入科学工具检索指令，文档侧不加查询指令，符合 [Qwen 官方检索用法](https://github.com/QwenLM/Qwen3-Embedding)。全部 472 个科学工具建立独立向量；`DescribeTools` 继续不进入图谱和向量索引。

服务就绪后运行：

```bash
conda activate SciTool-Unified
python -m scripts.tools.build_local_embeddings
```

建库在临时目录完成校验后整体发布，原来的 OpenAI 索引不会被写入。已有本地索引时拒绝覆盖；需要更新时先保留旧目录，再重新执行建库命令。每套索引分别保留 SciMas 的端口图与 SciToolAgent 的邻接图，切换向量不会合并两种方法的知识图谱。

例如，以 `school` 作为生成服务、以本地 Qwen 作为检索模型：

```bash
python -m scripts.services.configure_api --use school
python cli.py run --baseline scimas --dataset mini --tasks SMAS-0103 \
  --backend api --model deepseek-v4-flash-ascend1 --embedding-backend local \
  --max-context-chars 1500000 --max-output-tokens 65536 \
  --output results/scimas_school_local_embedding/predictions.json
```

SciToolAgent 使用相同的 `--embedding-backend local`。只运行规划阶段时，`cli.py plan` 也接受该参数。ReAct 不使用向量检索。

使用原来的 OpenAI 向量时，改为 `--embedding-backend api`。这会读取原来的 3,072 维索引，并调用其冻结身份指定的 embedding 服务。检索后端不会自动回退，缺少本地服务或本地索引时会明确失败。

评分入口与生成、检索模型无关：

```bash
python cli.py score --dataset mini --tasks SMAS-0103 \
  --predictions results/scimas_school_local_embedding/predictions.json \
  --output results/scimas_school_local_embedding/scores.json
```

原始 OpenAI 查询缓存和新 Qwen 查询缓存按完整身份隔离。改变检索模型会影响召回结果；两种后端的科学任务成绩和速度需要分别实测，不能视作语义上完全等价的嵌入。
