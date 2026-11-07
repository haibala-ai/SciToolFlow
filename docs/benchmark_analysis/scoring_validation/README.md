# 评分验收与归档

当前评分规则、参考和真实轨迹发布在 `tasks/mini/evaluation/`，运行与评分使用项目统一 CLI。这里保存最终验收报告，不参与 Agent 输入或评分计算。

| 文件 | 内容 |
|---|---|
| [summary.json](summary.json) | 200题逐题验收、参考来源及回归检查摘要 |
| [metric_definition_review.json](metric_definition_review.json) | Mini200与Full500评分定义扫描、指标独立性和科学等价边界 |
| [distance_representation_controls.json](distance_representation_controls.json) | 16题44个距离字段的等价表示、错误数值与缺项控制 |
| [package_validation.json](package_validation.json) | 完整项目与700份参考的验证结果 |
| [archive_manifest.json](archive_manifest.json) | 清理前归档路径、文件数、大小、SHA-256及清理验证状态 |

完整逐题作者记录、旧评分设计、控制结果、原参考源快照和阶段脚本已逐文件校验后归档到本机：

```text
.local/archives/scoring_cleanup_20261106_174600/mini_orchestration.tar.gz
```

该文件位于忽略提交的 `.local/` 下，不上传 GitHub。完整文件清单与逐文件校验值位于同目录 `inventory.json`；正式评分与回归测试不依赖本地归档。旧 Mini-200 实验的完整归档已随正式结果更新移入本地备份；当前 `exp/main_scimas/` 为 Mini-100 主实验。

若需要恢复作者工作进度，在项目根目录先核对压缩包SHA-256，再运行：

```bash
sha256sum .local/archives/scoring_cleanup_20261106_174600/mini_orchestration.tar.gz
tar -xzf .local/archives/scoring_cleanup_20261106_174600/mini_orchestration.tar.gz -C .
```

压缩包保留 `evaluation/authoring/mini_orchestration/` 下的原始相对路径，恢复后可继续原作者流程。解压会恢复历史文件，应在需要续审时执行。

旧 Mini-200 重评分快照和修正前结果保留在本地备份 `.local/archives/main_scimas_20261107_194927/rescore_current/`，不属于当前正式实验。当前主实验的复核入口见 [主实验说明](../../../exp/main_scimas/README.md)。
