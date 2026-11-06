# SciMas 历史实验重新评分

本目录使用当前 Mini-200 评分规则，重新评价 `exp/main_scimas` 中原有的 200 条真实运行。**这是对已有实验重新评分，没有重跑模型或补造工具执行。** 原预测、轨迹、结束状态、时间与 token 账目均保持不变。

| 主指标 | 当前结果 | 含义 |
|---|---:|---|
| 运行完成率 | **41.00%（82/200）** | 真实运行正常结束，不检查答案或工具路径 |
| 工具规划准确率 | **34.48%** | 每题 `S=3CE/(2E+C)` 的宏平均 |
| 答案准确率 | **40.00%（80/200）** | 科学答案正确，不要求本次过程正确或完整 |

严格规划通过率为 36.00%（72/200）；平均 C 为 43.99%，平均 E 为 29.40%。所有 200 条原始轨迹通过身份与证据核验，没有待审项。

## 本次修正

- **指标独立性**：格式仅记为诊断。Mini、Full 与 Special-100 作者评分入口都不再用答案格式否决正常结束或正确科学答案。Full 也使用可信参考观测独立核对答案，不要求模型采用正确工具路径。
- **SMAS-0078**：运行原本正常结束。其完整标准上三角距离向量与同序完整方阵无损等价，恢复运行完成与答案通过。该表示规则经逐题核查应用到 16 题的 44 个科学距离字段；邻接矩阵不套用此规则。
- **SMAS-0046**：原始尺度的两个分区具有相同精确全局最优 SSE `645101/100`。枚举全部 31 种无标签非空二分区验证，只接受最优分区，并检查轮廓系数、ARI 与提交分区一致，恢复答案通过。

与本目录修正前的评分相比，运行完成增加 1 题、答案正确增加 2 题；规划分不变。修正前的评分、诊断和规则快照保留在 [before_definition_fix.tar.gz](before_definition_fix.tar.gz)，最初实验的原始 `../scores.json` 也未覆盖。

## 证据与复现

- [scores.json](scores.json)：总体、学科与逐题结果。
- [scoring_issues.json](scoring_issues.json)：逐题变化、修复规则及科学等价证明摘要。
- [validation.json](validation.json)：原始归档、历史提交、当前规则和文件哈希核验。
- [scoring_snapshot.tar.gz](scoring_snapshot.tar.gz)：本次使用的任务、评分规则、代码和可信参考观测上下文，逐文件校验后无损打包。
- [progress.json](progress.json)：最终状态。

在项目根目录运行：

```bash
conda activate SciTool-Unified
python exp/main_scimas/rescore_current/reproduce.py
```

复现器先验证原始归档与历史 actor 提交，再检查题号映射、工具、输入及附件身份。公开格式／语义澄清逐项对应 `tasks/mini/selection.json`；历史任务指纹不会改写成当前版本指纹。普通生产评分入口的版本核验没有放宽。

复现时直接更新压缩快照，不生成 `scoring_snapshot/` 散文件目录。需要检查快照内容时，可先用 `tar -tzf exp/main_scimas/rescore_current/scoring_snapshot.tar.gz` 列出文件，再按需解压到项目外的临时目录。压缩包内保留原项目相对路径。

本结果使用 `scitoolflow.mini.orchestration.v3` / `scitoolflow.mini.three_metrics.v3`。不要把早期严格 0–1 的同名规划指标与当前 C/E 综合分直接比较。历史通信失败仍按原始失败状态保留，也不重新估计运行耗时。
