# Conda 环境

项目使用四个 Python 3.10 环境隔离不兼容的科学依赖。日常从 **SciTool-Unified** 启动 CLI，工具执行器自动选择其他环境，无需逐次切换。

| 环境 | 职责 |
| --- | --- |
| SciTool-Unified | CLI、评分器、常用化学／材料／生物和数理工具 |
| SciTool-LLM | 本地模型推理、vLLM 和依赖深度学习框架的工具 |
| SciTool-RXN-Local | RXN 反应模型及其独立依赖 |
| SciTool-Chroma | Chroma 蛋白模型及其独立依赖 |

在项目根目录依次安装：

```bash
conda env create -f configs/environments/SciTool-Unified.yml
conda env create -f configs/environments/SciTool-LLM.yml
conda env create -f configs/environments/SciTool-RXN-Local.yml
conda env create -f configs/environments/SciTool-Chroma.yml
conda activate SciTool-Unified
python -m pip install -e .
```

已有安装使用 `conda env update -f configs/environments/<环境名>.yml` 更新对应环境。YAML 固定依赖版本，项目源码另以可编辑模式安装；本项目的完整数据、配置与资源从仓库检出目录读取。跨机器安装仍需匹配 NVIDIA 驱动、系统库和专用 wheel，详见[安装与部署](../../docs/setup.md)。

[routing.json](routing.json) 将工具契约中的逻辑执行环境映射到这四个物理环境。`SCITOOL_CONDA_ENVS_PATH` 可指定环境根目录；`SCITOOL_TOOL_ENV_<逻辑名>` 可覆盖个别映射，名称中的连字符写为下划线并使用大写。

[bulk-counts-constraints.txt](bulk-counts-constraints.txt) 固定 bulk-count 统计所需的 PyDESeq2、AnnData 及数值栈。完整 Unified 安装已包含这些依赖；仅补装该功能时使用：

```bash
python -m pip install -c configs/environments/bulk-counts-constraints.txt \
  pydeseq2==0.4.12 anndata==0.10.8 array-api-compat==1.15.0 natsort==8.4.0
```

维护环境快照使用 `python -m scripts.maintenance.export_environments`。脚本从 `CONDA_EXE`、PATH 或当前 Conda 安装定位命令，也接受 `--conda /path/to/conda`。它在写入前检查全部导出，移除本机 prefix，并拒绝带凭据的依赖 URL。
