# 随仓库提供的科学工具资源

本目录保存可直接分发的小型模型、源码、参数、数据索引及历史来源记录。约 **52 MB**，最大单文件约 **2.9 MB**；大模型权重、HIPPIE 完整数据、凭据和编译产物不在其中。

运行 `python scripts/prepare_resources.py` 后，资源按原目录结构复制到项目 `.local/`。现有工具的目录、参数、计算逻辑、图谱和 embedding 均保持原样。

| 已包含的组件 | 内容 | 约体积 |
| --- | --- | ---: |
| MOFSimplify | 两个 HDF5 模型及配套数据表、MIT 许可 | 7.8 MB |
| OmegaFold | 运行源码、Apache-2.0 许可 | 0.8 MB |
| DeepTMHMM2 | 运行源码及上游 MIT 声明 | 0.1 MB |
| RXN Sandbox | 运行源码、词表、小型 SCScore 文件和许可 | 4.5 MB |
| RASPA2 | 可编译源码、结构／分子定义和 MIT 许可 | 25.8 MB |
| Zeo++／Voro++ | 可编译源码及原 BSD 类许可 | 3.8 MB |
| Eigen | 编译所需头文件和完整版权说明 | 8.3 MB |
| aiida-lsmo 与力场 | 参数来源、渲染器、实际定义及 SHA256 清单 | <0.1 MB |
| MP 公开小型快照 | 历史分子快照、电荷密度索引 | 0.8 MB |
| 来源记录 | DeepTMHMM2 与 HIPPIE 开发快照记录 | <0.1 MB |

精确大小、逐文件 SHA256、来源及范围见 [manifest.json](manifest.json)。这些是按工具需要选取的源码快照，不包含上游项目的全部示例、训练材料或文档；源代码版本未能从现有快照确认的组件只记录内容哈希，不虚构提交号。

## 离线准备与检查

在项目根目录、`SciTool-Unified` 环境中运行：

```bash
python scripts/prepare_resources.py
python scripts/prepare_resources.py --check
```

准备器先验证整批源文件和目标文件，再复制缺失文件；不联网，不下载大模型，不修改 Conda 环境，不覆盖已修改的文件。冲突时返回非零退出码，并列出相对路径。可用以下参数选择范围或另建目录：

```bash
python scripts/prepare_resources.py --component mofsimplify_models
python scripts/prepare_resources.py --destination .local/work/resource_staging
```

`--component` 可重复使用，组件 ID 见清单。`--destination` 用于隔离检查；工具仍按既有 `.local/` 路径或配置的覆盖项读取资源。

## 在目标机器编译科学程序

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

DSSP 的平台可执行文件及共享库未打包；按 [DSSP 官方说明](https://github.com/PDB-REDO/dssp)安装 `mkdssp` 后，用 `SCITOOL_DSSP_EXECUTABLE` 指向其绝对路径。

## 仍需下载的资源

ProteinForceGPT、ESMFold、OmegaFold、BioT5、Chroma、DeepTMHMM2／ESM2 和 RXN 预测模型的权重，HIPPIE 完整历史数据，以及使用者选择的生成 LLM，仍按[根 README](../README.md)提供的官方地址取得。账号及 API key 由使用者独立申请。

HIPPIE 来源记录对应 2026-10-13 下载的 v2.4 内容；下载日期、版本名或重命名文件均不能证明字节相同，须核对记录中的 SHA256。DeepTMHMM2 来源记录含权重的上游 Git blob 标识，也不代表权重已随仓库提供。MP 小型快照遵循 [Materials Project 数据条款](https://registry.opendata.aws/materials-project/)，不保证覆盖全部历史对象。

## 来源与许可

第三方文件保留各自的许可和版权通知；SciToolFlow 根目录的 MIT 许可不替代它们。各组件的来源链接与许可位置见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。生成的力场文件保留其参数来源、科学引用与逐文件校验，不能替换为任意同名定义。
