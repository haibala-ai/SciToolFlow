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

该文件位于忽略提交的 `.local/` 下，不上传 GitHub。完整文件清单与逐文件校验值位于同目录 `inventory.json`；正式评分与回归测试不依赖本地归档。原始实验 `exp/main_scimas` 的归档清单与286条原文件记录保持不变。

若需要恢复作者工作进度，在项目根目录先核对压缩包SHA-256，再运行：

```bash
sha256sum .local/archives/scoring_cleanup_20261106_174600/mini_orchestration.tar.gz
tar -xzf .local/archives/scoring_cleanup_20261106_174600/mini_orchestration.tar.gz -C .
```

压缩包保留 `evaluation/authoring/mini_orchestration/` 下的原始相对路径，恢复后可继续原作者流程。解压会恢复历史文件，应在需要续审时执行。

重评分的当前代码／数据快照与修正前结果分别保存在 `exp/main_scimas/rescore_current/scoring_snapshot.tar.gz` 和 `before_definition_fix.tar.gz`，作为两个便于复核的完整压缩包交付。复现入口见[重评分说明](../../../exp/main_scimas/rescore_current/README.md)。
