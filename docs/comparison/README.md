# 与 SciToolEval Level2 的对比数据

面向读者的对比图表、优势与限制统一展示在[项目 README](../../README.md#与-scitooleval-level2-的对比)。本目录提供其固定来源、统计与可复现图件。

| 文件 | 内容 |
| --- | --- |
| [current.json](current.json) | 当前正式题库与固定上游快照的统计、学科覆盖与差异 |
| [current.svg](current.svg) | README 使用的矢量图 |
| [current.png](current.png) / [current.pdf](current.pdf) | 320 dpi 位图与嵌入字体的 PDF |
| [sources/upstream_metadata.json](sources/upstream_metadata.json) | 上游公开任务路径、注册名称、分类及固定提交身份 |

上游为 SciToolAgent 仓库提交 `ac1cf19fcef84e69f149db6da424afe4e9b2f11f` 中的 SciToolEval Level2。统计按各自的规范注册名称去重，排除当前 DescribeTools 文档查询。SciToolFlow 统计正式主参考中的实际调用；覆盖要求对应工具具有成功结果。原 Level2 统计其公开参考工具路径，未重新部署上游工具环境。

两者使用各自工具池和原生学科分类，覆盖率是各自集合内的比例，不能解释为同一工具池的配对增益。调用长度包含不同对象上的重复使用，不等于串行依赖深度。上游公开文件的缺项只描述所比较快照，不推断作者内部资产。完整限定与来源链接见根 README 的统计注释。

从项目根目录重算，不调用科学工具或 LLM：

```bash
python -m scripts.benchmark.compare_release
```

重算后检查根 README 的数据表与统计注释；输入身份记录在 `current.json`。题库本身的分布与工具覆盖详见[500 题分析](../benchmark_analysis/README.md)。
