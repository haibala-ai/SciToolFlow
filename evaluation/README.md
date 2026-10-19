# 测评与私有参考

| 文件/目录 | 用途 |
| --- | --- |
| [references.jsonl](references.jsonl) | 按任务 ID 对齐的金标准、必要路径、评分字段和证据依赖 |
| [reference_traces/](reference_traces/) | 必要与支持工具证据归档；多数不是完整模型对话 |
| [artifacts/](artifacts/) | 参考执行产生的附件 |
| [file_identities.json](file_identities.json) | 附件内容身份，避免只按文件名比较 |

公开题目位于 `../tasks/questions.jsonl`。本目录用于评分，不提供给 Agent；实际评分实现就在本目录。

```bash
python cli.py score --predictions results/demo/predictions.json --output results/demo/scores_all.json
python cli.py score --tasks FLOW-0285,FLOW-0481 --predictions results/demo/predictions.json --output results/demo/scores.json
python cli.py judge --backend vllm --requests results/demo/scores_review_requests.json --output results/demo/reviews.json
# 同一复核方法也可使用生成 API，密钥和地址来自 services.env 的 SCITOOLFLOW_API_*。
python cli.py judge --backend api --model YOUR_JUDGE_MODEL --requests results/demo/scores_review_requests.json --output results/demo/reviews_api.json
python cli.py score --tasks FLOW-0285,FLOW-0481 --predictions results/demo/predictions.json --reviews results/demo/reviews.json --output results/demo/reviewed.json
```

旧实验的评分和审核保留为历史记录。此次参考文件路径调整会改变审核请求哈希，禁止直接改写旧审核指纹套用到新评分；需要重新生成待审请求并审核。

## 代码职责

| 模块 | 职责 |
| --- | --- |
| runner.py | 加载预测与选择评分范围 |
| scoring.py | 汇总完成、计划、答案和联合指标 |
| answer.py | 完整字段/数组、容差、schema 与部分分 |
| planning.py | 依赖匹配、工具路径和预算 |
| comparison.py | 展示归一化与精确类型实参比较 |
| reviews.py / judge.py | 读取双哈希审核 / 可选 API 或本地模型审核 |
| files.py / validation.py | 文件内容身份 / 全包一致性验证 |

公开输入加载和公开答案 schema 的公共实现位于 scitoolflow/benchmark/，不读取本目录的金标准。

## 评分协议

当前 500 题未分 dev/test。默认分母是全部 500 题，漏交失败；--tasks 是显式抽查模式。
2026-10-18 已修订部分题意、输入说明/常量、答案契约与科学解释，见 [逐条审查](../results/reports/full_run_audit_20261018/README.md)。公开题目在 tasks/、私有参考在 evaluation/；其他 baseline 必须使用同一
公开任务、答案 schema、工具池和资源版本。实际 harness 限制与采样设置另行冻结。

1. Completion：运行器正常完成、答案非空，没有报告失败或科学预算超限。它不是科学正确。
2. Planning：实际成功任务工具调用按参考依赖匹配工具和实参；独立分支顺序可交换，
   失败尝试仍计科学预算。DescribeTools 无论成功/失败都不进入任务路径、召回或 extra_calls。
   参考路径中出现 DescribeTools 被拒绝。声明的 tool_path 不可替代实际 calls。
3. Answer：必填字段/类型和全部科学叶子均检查。容差为 abs(pred-ref)<=atol+rtol*abs(ref)，
   零容差保持为零；标识符、化学式大小写及单位不做数字子串近似。整个数组均检查。
4. Joint：Completion、Planning、Answer 同时通过。数值等价不代表工具计划正确，反之亦然。

工具实参按明确类型和值比较；相同数字组成的不同计算指令不能视为同一计划。可选参数
只在显式等于已声明默认值时自动等价；其他变体与短路径转交独立语义审核。
重叠字段规则的叶子部分分去重，以免重复加权；部分分仅诊断，不代替二元科学判定。

不同英文措辞、不同但可能正确的执行计划会保持 pending，默认低估计记不通过并报告
待审数量、上下界，不能静默跳过。--reviews 文件须绑定 reference_sha256、
prediction_sha256，并提供 reviewer、rationale、reviewed_at 与布尔判定。
明确的数值错误、缺字段或 schema 错误不能被审核改成正确。默认没有自动 LLM judge。

预测 JSON/JSONL 包含 id、completed、status、calls、final_answer、failure_reason、
trace_path 等。calls 保存全部真实调用，包括 kind=discovery 的 DescribeTools。
排除依据为正式工具名/登记别名，不信任任意 kind 标签。非法预算、重复/未知任务 ID、
不完整参考或审核指纹不符明确反馈。

仍需注意：参考是助手审查而非实验真理；外部数据版本可能变化；同义单位/其他正确格式
可能需要人工或独立审核；当前未按实体/工作流设置隐藏测试集，不能声称独立泛化；
500 条参考自评分 1.0 只检验协议一致性，不是 benchmark 质量证明。

可选的 judge 命令支持 `--backend api|vllm|local` 和 `--model`：生成 API、常驻本地 vLLM 或直接 Qwen worker；与两个 baseline 共用模型客户端。API 不复用 embedding 密钥；生成服务需显式配置模型。读取已生成的待审请求并产生双哈希审核文件。
它仅对 null/pending 的维度提出判定，定量/格式失败不可被覆盖；整份证据超出上下文时
保留未决而不截断科学值。自动 LLM 审核与人工审核明确区分，同一个弱模型兼任 agent/judge
可能有相关误差，其结论不是科学认证，也不适合据此声称正式准确率。默认 score 仍是纯离线。

本地 vLLM 使用精确 tokenize 预算；API 和直接 worker 先按字符限制保留完整证据，模型上下文错误进入 unresolved。API judge 会把问题、参考和观测发给所配置的服务。输出记录 backend、model、provider 与调用次数；是否实际收费无法从兼容接口推断，外部 API 的 paid_model_api_used 保留 null，不虚报“免费”。

## 当前版本的补充口径

`planning_strict`、`answer_strict` 也须满足完成条件。未完成但恰好调用参考路径的情况只进入独立诊断 `reference_path_match_rate`；语义审核后的状态与原始严格状态分别保存。评分入口核验预测绑定的公开题库哈希，拒绝把旧版本预测静默套到新契约。

补齐原来未覆盖的必需科学叶子；可选 observation/provenance 标签不作为科学答案强制内容。标准 InChI/InChIKey 用精确字符串核验；微小非零 p 值和焦耳量不能在过大的绝对容差下被零替代。仅明确标注的文档键集合允许无序比较，普通科学向量保持有序。

`equivalence.py` 对选择加入该策略的任务共同验证特征基底、投影、方差，或聚类分组与对应中心，才规范化比较副本；原提交不改写。仅翻转半套结果、错换中心、改特征值仍失败。个别标签语义在 prose 中的表达继续留待审核。

`evidence.py` 仅对 FLOW-0191/0192/0193 的未固定种子惯性比值启用明示规则：必须有同工具、精确输入的真实成功观测，再独立重算对应差值和约束。固定种子的矩、其他科学量及工具计划仍单独检查；没有观测不能以历史值代替。

`source_drift.py` 只检测已支持材料选择器的同输入非空标识符集合/顺序变化，不宣称检测所有数据库字段变化。发现变化时转交独立科学复核；不自动判对，不以模型回答替换金标准，也不让默认 Qwen judge 处理。格式失败仍失败。复核文件必须绑定双哈希并明确 `reviewer_kind=human` 或 `independent_scientific_review`。本次历史选择器集合未检测到这种变化，三处计数错误已按归档原文纠正。

原始 500 题结果、当前规则和未来正式运行须分别报告。没有独立专家复核的字段仍为 provisional；全套自评分通过只证明内部一致性。
