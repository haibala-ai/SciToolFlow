# Special-100 逐题复核

审查分开记录科学正确性、图结构适配、公开信息边界和参考身份。参考自检通过不能替代题目质量判断，也不能证明 SciMas 优于其他方法。

共审查 100 题：66 题有多层工具依赖，34 题主要是单层并行证据面板。后者有实际并行工作，但不能统一称为复杂多阶段编排。

其中 23 道中等／较难题目前主要考察并行证据汇合；若要将其作为强多阶段编排题，应增强科学依赖。没有仅凭工具层数设立用户未规定的硬门槛，也没有宣称这些题已证明强编排优势。题号：SMAS-0006, SMAS-0014, SMAS-0015, SMAS-0016, SMAS-0017, SMAS-0020, SMAS-0021, SMAS-0022, SMAS-0023, SMAS-0025, SMAS-0026, SMAS-0028, SMAS-0034, SMAS-0038, SMAS-0053, SMAS-0054, SMAS-0058, SMAS-0062, SMAS-0069, SMAS-0071, SMAS-0075, SMAS-0077, SMAS-0079。

泄露检查涵盖题目标题、正文、输入、答案格式和公开 JSON 附件。移除了直接给出的判断、明确工具接口名和不必要的解题顺序。算法定义、计量单位、实验条件、容差和输出字段用于固定科学问题，予以保留。原始计算输出和用于评估预测的观测真值也属于合法题目数据。

SMAS-0035 的授权纠正来源、SMAS-0054 的原始坐标、SMAS-0028 的前后变化输入均在逐题记录中说明。它们不等于最终判断；不能仅凭字段名把合法观测误删。

[完整逐题记录](evaluation/task_review.json) 包括每题科学审查意见、共享前提、独立子任务、科学汇合、相关方法族区分、信息检查和当前参考身份。

| 题号 | 学科 | 难度 | 图结构 | 适配范围 | 当前参考 |
| --- | --- | --- | --- | --- | --- |
| SMAS-0001 | Chemical | intermediate | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0002 | Chemical | foundation | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0003 | Chemical | foundation | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0004 | Chemical | intermediate | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0005 | Chemical | advanced | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0006 | Chemical | intermediate | 1 层 / 宽 8 | 主要并行面板 | 匹配 |
| SMAS-0007 | Chemical | intermediate | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0008 | Chemical | intermediate | 4 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0009 | Chemical | foundation | 1 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0010 | Chemical | intermediate | 2 层 / 宽 8 | 符合定位 | 匹配 |
| SMAS-0011 | Chemical | advanced | 3 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0012 | Chemical | advanced | 2 层 / 宽 8 | 符合定位 | 匹配 |
| SMAS-0013 | Chemical | foundation | 3 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0014 | Material | advanced | 1 层 / 宽 11 | 主要并行面板 | 匹配 |
| SMAS-0015 | Material | intermediate | 1 层 / 宽 10 | 主要并行面板 | 匹配 |
| SMAS-0016 | Material | advanced | 1 层 / 宽 10 | 主要并行面板 | 匹配 |
| SMAS-0017 | Material | intermediate | 1 层 / 宽 9 | 主要并行面板 | 匹配 |
| SMAS-0018 | Material | foundation | 1 层 / 宽 8 | 符合定位 | 匹配 |
| SMAS-0019 | Material | foundation | 1 层 / 宽 9 | 符合定位 | 匹配 |
| SMAS-0020 | Material | intermediate | 1 层 / 宽 5 | 主要并行面板 | 匹配 |
| SMAS-0021 | Material | intermediate | 1 层 / 宽 5 | 主要并行面板 | 匹配 |
| SMAS-0022 | Material | advanced | 1 层 / 宽 7 | 主要并行面板 | 匹配 |
| SMAS-0023 | Material | intermediate | 1 层 / 宽 10 | 主要并行面板 | 匹配 |
| SMAS-0024 | Material | foundation | 1 层 / 宽 12 | 符合定位 | 匹配 |
| SMAS-0025 | Material | intermediate | 1 层 / 宽 9 | 主要并行面板 | 匹配 |
| SMAS-0026 | Material | intermediate | 1 层 / 宽 8 | 主要并行面板 | 匹配 |
| SMAS-0027 | Biology | advanced | 2 层 / 宽 8 | 符合定位 | 匹配 |
| SMAS-0028 | Biology | advanced | 1 层 / 宽 9 | 主要并行面板 | 匹配 |
| SMAS-0029 | Biology | intermediate | 2 层 / 宽 8 | 符合定位 | 匹配 |
| SMAS-0030 | Biology | intermediate | 2 层 / 宽 7 | 符合定位 | 匹配 |
| SMAS-0031 | Biology | intermediate | 2 层 / 宽 8 | 符合定位 | 匹配 |
| SMAS-0032 | Biology | advanced | 2 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0033 | Biology | intermediate | 2 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0034 | Biology | intermediate | 1 层 / 宽 7 | 主要并行面板 | 匹配 |
| SMAS-0035 | Biology | foundation | 1 层 / 宽 9 | 符合定位 | 匹配 |
| SMAS-0036 | Biology | foundation | 1 层 / 宽 13 | 符合定位 | 匹配 |
| SMAS-0037 | Biology | foundation | 1 层 / 宽 7 | 符合定位 | 匹配 |
| SMAS-0038 | Biology | intermediate | 1 层 / 宽 7 | 主要并行面板 | 匹配 |
| SMAS-0039 | MachineLearning | advanced | 4 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0040 | MachineLearning | intermediate | 3 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0041 | MachineLearning | advanced | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0042 | MachineLearning | intermediate | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0043 | MachineLearning | intermediate | 4 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0044 | MachineLearning | foundation | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0045 | MachineLearning | intermediate | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0046 | MachineLearning | intermediate | 3 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0047 | MachineLearning | intermediate | 3 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0048 | MachineLearning | foundation | 1 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0049 | MachineLearning | intermediate | 3 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0050 | MachineLearning | advanced | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0051 | Chemical | advanced | 3 层 / 宽 12 | 符合定位 | 匹配 |
| SMAS-0052 | Chemical | intermediate | 4 层 / 宽 9 | 符合定位 | 匹配 |
| SMAS-0053 | Chemical | intermediate | 1 层 / 宽 15 | 主要并行面板 | 匹配 |
| SMAS-0054 | Chemical | advanced | 1 层 / 宽 10 | 主要并行面板 | 匹配 |
| SMAS-0055 | Chemical | intermediate | 3 层 / 宽 12 | 符合定位 | 匹配 |
| SMAS-0056 | Chemical | intermediate | 3 层 / 宽 19 | 符合定位 | 匹配 |
| SMAS-0057 | Chemical | foundation | 1 层 / 宽 20 | 符合定位 | 匹配 |
| SMAS-0058 | Chemical | intermediate | 1 层 / 宽 9 | 主要并行面板 | 匹配 |
| SMAS-0059 | Chemical | advanced | 3 层 / 宽 12 | 符合定位 | 匹配 |
| SMAS-0060 | Chemical | advanced | 4 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0061 | Chemical | intermediate | 4 层 / 宽 16 | 符合定位 | 匹配 |
| SMAS-0062 | Chemical | intermediate | 1 层 / 宽 13 | 主要并行面板 | 匹配 |
| SMAS-0063 | Material | advanced | 3 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0064 | Material | intermediate | 4 层 / 宽 5 | 符合定位 | 匹配 |
| SMAS-0065 | Material | intermediate | 2 层 / 宽 8 | 符合定位 | 匹配 |
| SMAS-0066 | Material | advanced | 2 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0067 | Material | advanced | 4 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0068 | Material | intermediate | 4 层 / 宽 12 | 符合定位 | 匹配 |
| SMAS-0069 | Material | intermediate | 1 层 / 宽 9 | 主要并行面板 | 匹配 |
| SMAS-0070 | Material | intermediate | 3 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0071 | Material | intermediate | 1 层 / 宽 6 | 主要并行面板 | 匹配 |
| SMAS-0072 | Material | advanced | 6 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0073 | Material | foundation | 1 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0074 | Material | foundation | 1 层 / 宽 12 | 符合定位 | 匹配 |
| SMAS-0075 | Biology | advanced | 1 层 / 宽 9 | 主要并行面板 | 匹配 |
| SMAS-0076 | Biology | advanced | 7 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0077 | Biology | intermediate | 1 层 / 宽 9 | 主要并行面板 | 匹配 |
| SMAS-0078 | Biology | intermediate | 3 层 / 宽 5 | 符合定位 | 匹配 |
| SMAS-0079 | Biology | intermediate | 1 层 / 宽 6 | 主要并行面板 | 匹配 |
| SMAS-0080 | Biology | foundation | 3 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0081 | Biology | intermediate | 4 层 / 宽 8 | 符合定位 | 匹配 |
| SMAS-0082 | Biology | intermediate | 3 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0083 | Biology | advanced | 3 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0084 | Biology | foundation | 2 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0085 | Biology | intermediate | 2 层 / 宽 12 | 符合定位 | 匹配 |
| SMAS-0086 | Biology | advanced | 3 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0087 | Biology | intermediate | 2 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0088 | MachineLearning | advanced | 5 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0089 | MachineLearning | intermediate | 4 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0090 | MachineLearning | advanced | 2 层 / 宽 2 | 符合定位 | 匹配 |
| SMAS-0091 | MachineLearning | intermediate | 4 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0092 | MachineLearning | foundation | 3 层 / 宽 5 | 符合定位 | 匹配 |
| SMAS-0093 | MachineLearning | intermediate | 3 层 / 宽 4 | 符合定位 | 匹配 |
| SMAS-0094 | MachineLearning | advanced | 3 层 / 宽 9 | 符合定位 | 匹配 |
| SMAS-0095 | MachineLearning | intermediate | 4 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0096 | MachineLearning | foundation | 2 层 / 宽 6 | 符合定位 | 匹配 |
| SMAS-0097 | MachineLearning | intermediate | 2 层 / 宽 3 | 符合定位 | 匹配 |
| SMAS-0098 | MachineLearning | intermediate | 5 层 / 宽 2 | 符合定位 | 匹配 |
| SMAS-0099 | MachineLearning | advanced | 2 层 / 宽 7 | 符合定位 | 匹配 |
| SMAS-0100 | MachineLearning | foundation | 4 层 / 宽 6 | 符合定位 | 匹配 |
