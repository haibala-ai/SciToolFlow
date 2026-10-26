# 随仓库提供的科学工具资源

本目录保存固定版本的模型、源码、参数、tokenizer、数据索引及来源记录，共约 **502 MiB**，最大存储文件 **48 MiB**。包含 23 个组件、1,556 个还原后的文件；其中两个 RXN checkpoint 使用分块存储，仓库实际保存 1,562 个资源文件。**无需 Git LFS**。

## 目录职责

| 目录／文件 | 用途 |
| --- | --- |
| external_sources/ | 固定的第三方源码、编译依赖与许可；保留上游结构 |
| models/ | 已分发的小型权重、模型配置、词表与tokenizer |
| chunks/ | 大型checkpoint的无损分块；由准备器重组 |
| reference_data/ | 科学工具使用的固定数据快照与索引 |
| provenance/ | 模型版本、下载来源和资源来源证据 |
| manifest.json | 逐文件身份、组件、分块顺序与安装目标 |
| THIRD_PARTY_NOTICES.md | 第三方版权、许可和分发说明 |

运行 `python -m scripts.maintenance.prepare_resources` 后，资源按原目录结构复制到项目 `.local/`。准备器仅安装资源，不改写工具契约、科学实现或检索索引。

| 已包含的组件 | 内容 | 约体积（MiB） |
| --- | --- | ---: |
| MOFSimplify | 两个 HDF5 模型及配套数据表、MIT 许可 | 7.8 |
| OmegaFold | 运行源码、Apache-2.0 许可 | 0.8 |
| DeepTMHMM2 | 运行源码及上游 MIT 声明 | 0.1 |
| DeepTMHMM2 checkpoints | 固定版本的全部 10 个文件，已匹配历史 Git blob | 125.0 |
| RXN Sandbox | 运行源码、词表、小型 SCScore 文件和许可 | 4.5 |
| RXN 预测权重 | Pistachio2025Q2 Forward／Retro 原始 checkpoint，已匹配官方 LFS SHA256 | 295.8 |
| 模型配置与 tokenizer | ProteinForceGPT、ESMFold、七个 BioT5 模型的配套文件和许可 | 26.1 |
| DSSP 离线安装包 | Ubuntu 22.04 amd64 的 DSSP 4.0.4、libcifpp、Boost 依赖及启动器 | 2.9 |
| RASPA2 | 可编译源码、结构／分子定义和 MIT 许可 | 25.8 |
| Zeo++／Voro++ | 可编译源码及原 BSD 类许可 | 3.8 |
| Eigen | 编译所需头文件和完整版权说明 | 8.3 |
| aiida-lsmo 与力场 | 参数来源、渲染器、实际定义及 SHA256 清单 | <0.1 |
| MP 公开小型快照 | 历史分子快照、电荷密度索引 | 0.8 |
| 来源记录 | DeepTMHMM2、HIPPIE 与模型版本记录 | <0.1 |

精确大小、逐文件 SHA256、来源及范围见 [manifest.json](manifest.json)。这些是按工具需要选取的快照，不包含上游项目的全部示例、训练材料或文档；源代码版本未能从现有快照确认的组件只记录内容哈希，不虚构提交号。

RXN 两个原始文件各 155,080,231 字节，分块保存在 `chunks/rxn_sandbox/`。清单的 `files` 以还原后的路径为键，`parts` 记录每个块的路径、顺序、字节数及 SHA256。准备脚本将它们还原为 `.local/models/rxn-sandbox/models/{forward,retrosynthesis}/*.ckpt`，完整文件哈希与官方 LFS 对象一致；工具读取原始 checkpoint，不感知分块。分块没有压缩、量化或修改权重。

## 离线准备与检查

在项目根目录、`SciTool-Unified` 环境中运行：

```bash
python -m scripts.maintenance.prepare_resources
python -m scripts.maintenance.prepare_resources --check
```

准备器先验证整批源文件（含分块及还原后的完整文件）和目标文件，再复制缺失文件；不联网，不修改 Conda 环境，不反序列化模型，不覆盖已修改的文件。冲突时返回非零退出码，并列出相对路径。默认还原全部组件，至少为这些资源预留约 502 MiB 的额外空间；尚未下载的大型权重另计。可用以下参数选择范围或另建目录：

```bash
python -m scripts.maintenance.prepare_resources --component mofsimplify_models
python -m scripts.maintenance.prepare_resources --component rxn_sandbox_weights
python -m scripts.maintenance.prepare_resources --destination .local/work/resource_staging
```

`--component` 可重复使用，组件 ID 见清单。`--destination` 用于隔离检查；工具仍按既有 `.local/` 路径或配置的覆盖项读取资源。

## 科学程序的编译与离线部署

RASPA2 和 Zeo++ 使用源码分发。以下步骤需要 C／C++ 编译器、GNU Make 和基本构建工具；不需要另行下载相应源码。所有命令从项目根目录开始。

### RASPA2

```bash
cd .local/external_sources/RASPA2
./configure --prefix="$PWD/install"
make -j2
make install
cd ../../..
```

默认可执行文件为 `.local/external_sources/RASPA2/install/bin/simulate`。使用其他安装位置时，在 `runtime.env` 设置 `RASPA_EXECUTABLE_PATH`。

### Zeo++

```bash
make -j2 -C .local/external_sources/zeopp-lsmo/voro++/src
make -j2 -C .local/external_sources/zeopp-lsmo/zeo++ \
  CFLAGS="-O2 -std=c++11 -I$PWD/.local/external_sources/eigen3/runtime/usr/include" network
```

默认可执行文件为 `.local/external_sources/zeopp-lsmo/zeo++/network`。其他位置用 `SCITOOL_ZEOPP_EXECUTABLE` 指定。Eigen 头文件已包含，无需为此步骤单独下载 Debian 安装包。

### DSSP：Ubuntu 22.04 amd64 离线安装

已提供 `dssp_4.0.4-1_amd64.deb`、`libcifpp2`／`libcifpp-data` 2.0.5-1build1，以及 `libboost-{iostreams,program-options,regex}1.74.0` 1.74.0-14ubuntu3。保留这些文件能避免系统安装了不同版本的 DSSP、Boost 或字典。准备资源后，在项目根目录执行：

```bash
mkdir -p .local/external_sources/dssp/runtime
for package in .local/external_sources/dssp/*.deb; do
  dpkg-deb -x "$package" .local/external_sources/dssp/runtime
done
.local/external_sources/dssp/run_mkdssp --version
```

只解包到项目目录，不运行安装脚本，不需要 root。`run_mkdssp` 使用相对路径设置库与字典位置，是当前工具的默认入口，无需另填绝对路径。版本应为 4.0.4。安装包保留原版权与许可；字典文件也按包内原样恢复。**这些二进制包适用于 Ubuntu 22.04 x86_64，不是跨平台静态程序**，仍使用目标机器的 glibc、libstdc++ 等基础库；其他平台按 [DSSP 官方说明](https://github.com/PDB-REDO/dssp)安装，并配置 `SCITOOL_DSSP_EXECUTABLE`。

## 仍需下载的资源

ProteinForceGPT、ESMFold、OmegaFold、BioT5、需要授权的 Chroma，以及 ESM2 主干的大型权重、HIPPIE 完整历史数据和使用者选择的生成 LLM，仍按[根 README](../README.md)提供的官方地址取得。DeepTMHMM2 的 10 个 checkpoints 和 RXN 的两个预测 checkpoint 已包含。账号及 API key 由使用者独立申请。

ProteinForceGPT、ESMFold 和七个 BioT5 模型的配套文件已提供；[model_metadata_snapshots.json](provenance/model_metadata_snapshots.json)记录已核验的官方提交、缺失权重的文件名／大小／SHA256。每个 `verified_revision` 都经过全部打包元数据的 Git blob／LFS 身份比较，以及本地大型权重对官方 LFS SHA256 的比较。下载时使用该版本，**只下载缺少的权重**，再核对 SHA256，不要用上游最新版覆盖配套配置。该记录不表示大型权重已随仓库分发。

HIPPIE 来源记录对应 2026-10-13 下载的 v2.4 内容；下载日期、版本名或重命名文件均不能证明字节相同，须核对记录中的 SHA256。截至 2026-10-19，已查看的[官方下载页](https://cbdm-01.zdv.uni-mainz.de/~mschaefer/hippie/download.php)和[信息页](https://cbdm-01.zdv.uni-mainz.de/~mschaefer/hippie/information.php)未列出明确的再分发许可，因此暂不镜像其原始数据。MP 小型快照遵循 [Materials Project 数据条款](https://registry.opendata.aws/materials-project/)，不保证覆盖全部历史对象。

## 来源与许可

第三方文件保留各自的许可和版权通知；SciToolFlow 根目录的 MIT 许可不替代它们。各组件的来源链接与许可位置见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。生成的力场文件保留其参数来源、科学引用与逐文件校验，不能替换为任意同名定义。
