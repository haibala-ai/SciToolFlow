# 维护与实验命令

从仓库根目录使用 `python -m scripts.<分类>.<模块>`。日常查询、工具调用、baseline 与评分使用 `python cli.py`；这里集中构建、验证、服务管理和实验编排命令。

| 分类 | 模块 | 职责 |
| --- | --- | --- |
| tools | build_catalog | 校验实现签名，刷新契约、源码绑定、实现索引和资源配置清单 |
| tools | build_graph | 从当前契约重建图谱；`--embed` 编码变化的功能描述 |
| tools | check_foundation | 核查工具契约、环境、数据端口、图谱与向量的静态一致性 |
| tools | audit_tool_overlap | 静态筛查核心能力重叠候选，候选仍需人工判断 |
| benchmark | run_benchmark | 编排 baseline 批量运行、进度保存与离线评分 |
| benchmark | analyze_benchmark | 从正式题库和主参考重算分布、覆盖及分析图表 |
| benchmark | compare_release | 对照固定 SciToolEval Level2 来源，生成当前对比统计和图件 |
| benchmark | index_tasks | 更新公开任务浏览索引 |
| benchmark | index_results | 为本机实验结果建立浏览索引 |
| references | validate_release | 核验全部主／额外参考的身份、实际证据、科学计分和独立审核 |
| references | native_reference_session | 创建只读公开任务与工具的受限原生 ReAct 执行会话 |
| references | collect_workflow_reference | 收集候选参考，保护正式参考免于误覆盖 |
| references | audit_workflow_design | 检查任务、证据与评分判据的一致性 |
| references | audit_cross_task_patterns | 检查跨题的共性边界和设计问题 |
| services | model_service | 管理已配置的本地 vLLM 服务 |
| maintenance | prepare_resources | 安装或检查仓库分发的科研资源 |
| maintenance | export_environments | 从本机 Conda 导出四个无凭据的环境快照 |
| maintenance | freeze | 重建正式发布文件的 SHA256 清单 |

`benchmark/figures.py` 提供分析图与对比图共用的样式和绘图函数，由上述分析命令调用。绘图依赖可用 `python -m pip install -e ".[plots]"` 安装。

常用检查：

```bash
python -m scripts.tools.check_foundation
python -m scripts.maintenance.prepare_resources --check
python -m scripts.references.validate_release
python -m scripts.maintenance.freeze
python cli.py validate
```

构建顺序与源码修改后的验证见[开发指南](../docs/architecture.md)。模型服务与科研账号配置见[安装与部署](../docs/setup.md)。维护脚本不依赖项目外的设计归档；原始参考记录中的生成路径是执行证据的一部分，不作为当前路径入口。
