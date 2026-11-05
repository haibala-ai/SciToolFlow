"""Per-study difficulty and SciMas mechanism review; never passed to actors."""
import hashlib,json
from pathlib import Path
from collections import Counter
BASE=Path(__file__).resolve().parents[1]
ADVANCED={5,11,12,14,16,22,27,28,32,39,41,50}
FOUNDATION={2,3,9,13,18,19,24,35,36,37,44,48}
REWRITTEN={4,5,6,7,8,9,10,11,30,31,32,33,34,37,38}
# shared prerequisite | ready scientific branch A | branch B | scientific join | reason for tier
PROFILES={
1:('完整提交图和选定有机母体的身份','原始完整图的质量','母体的质量和极性','反离子质量差与明确代理排序','对象和电荷不能混用；代理目标受限'),
2:('保留同位素、组分和立体信息的分子身份','平均质量','单同位素精确质量','按明确数值尺度作质量差并保留并列','基础的共享身份与两个互补质量量，不要求推断实验性质'),
3:('受损记录仅采用给定权威替代式，其余记录独立','各记录规范身份与供体计数','各记录质量','按相同有效图计算供体密度','基础局部输入恢复，不强制制造失败，也不猜结构'),
4:('每个保持原图的候选','芳环计数','严格可旋转键计数','AND门控后才启动合格候选的质量/极性','两种失败控制、包含阈值和可选字段空值需一致'),
5:('同一原始图、不同互变异构政策','保留表示及质量见证','规范互变表示及质量见证','政策内/政策间身份相等性核对','控制政策、表示和质量不变量，不能推断溶液丰度'),
6:('一个共同基线的实测质量与极性','各替代图的质量','各替代图的极性','每个替代减同一基线，再比较对照差','公共基线复用与对照方向，避免并排独立算分'),
7:('最大有机片段身份及真实形式电荷','各候选的片段与电荷判别','合格图的供体与受体计数','带电片段停止中性图专属后续，完整保留身份','工具适用域门控，不把整盐净电荷当片段中性'),
8:('同一规范图集合与固定记录顺序','Morgan完整相似矩阵','MACCS完整相似矩阵','同一参考、同一阈值下比较邻域','协议差异而非分子身份；两个表示不能交叉混接'),
9:('各记录保持原图的拓扑对象','螺原子计数','桥头原子计数','分别分类并保留最大螺计数的全部并列','基础双拓扑视角，类别不强制互斥，不称物理刚性'),
10:('每条原始记录选定片段的精确身份','不同图组的质量','不同图组的极性','重复记录共享同图证据但仍逐条报告','去重复用必须以相同图和电荷为条件，不按相似度缓存'),
11:('保持原始图及其独立质量见证','标准InChI到恢复SMILES的有向转换链','原始图质量','恢复图质量、表示相等性与质量差联合审计','真实往返可改变互变表示；质量守恒不能证明表示可逆'),
12:('显式权威修复后的立体图身份','立体中心完整性','含手性/不含手性两种指纹矩阵','区分未指定中心、对映表示与指纹不变性','错误隔离、对象顺序、立体方法三层边界'),
13:('每条规范图的结构命中证据','候选间独立子结构查询','已命中候选的极性后续','未命中分支明确空值，命中分支保留数值','基础真实门控题，适用域窄且易于解释'),
14:('相同来源身份的原胞/超胞/应变几何，不假设共享解析计算','密度和几何匹配面板','衍射和对称性面板','识别表示不变性和真实尺度/形变区别','多证据控制同一科学辨识，不以图宽代替难度'),
15:('固定原始结构与两套明确对称容差','精/粗容差的对称性','密度、邻接与衍射','容差稳定性与不同可观测量的敏感性','中等协议对照面板，不宣传自适应容差搜索'),
16:('有序模型与平均混合占位模型的原始对象身份','占位加权组分和质量密度','仅有序模型的局域几何与匹配','模型适用域排除不能变成虚构有序模型','平均无序与有序对象不可互换，属于方法适用性挑战'),
17:('等原子体积的两种结构','密度与对称性','局部邻域与衍射','相同密度不意味着同一晶体结构','中等独立证据面板，需完整比较而非单属性认定'),
18:('两个固定碳几何及各自实际胞内原子数','局部接触和每原子归一化','密度、衍射与对称性','在相同定义下比较局部拓扑和质量堆积','基础并行验证面板，不从静态属性推断导电/弹性'),
19:('固定几何的替换系列与明确化学式','化学式质量及元素质量分数','质量密度及几何邻接','固定几何不等于相同质量或质量分数','基础分母一致性，原子分数不可代替质量分数'),
20:('固定原子对应和同一个参考端点','wrapped最小镜像位移','unwrapped位移与各结构邻接','验证等价周期表示而非原始坐标差','中等周期对象审计，工具内部搜索复杂度不计为规划难度'),
21:('同一参考与固定Cs/Cl对应','精确半胞镜像简并','近半胞唯一性及密度控制','相同最短距离不保证位移方向唯一','中等边界核验，完整并列镜像不能被确定性约定消去'),
22:('坏格基与整数约化格基的同一周期物理对象','完整邻接镜像、距离和位移','密度、对称性和结构匹配','跨格基的物理不变量及坐标标签一致性','不能只数邻居或固定27胞；搜索由工具完成，难点是跨表示核验'),
23:('保留真实长度与允许等向缩放的两种匹配协议','物理尺度匹配','归一化尺度匹配与密度/邻接','形变、尺度和物理状态分别判断','中等对照设计，不把归一化匹配当相同密度'),
24:('同构盐的固定组成、晶格与衍射协议','质量和密度','首峰和对称性','两种独立排名联合说明同构标签的局限','基础平行证据题，不声称隐含热力学稳定性'),
25:('实际供给胞内的空位/替换身份','占位加权元素库存与原子数','密度和几何接触','缺陷质量差与实际胞的密度比','中等库存审计，约化式不能代替胞内计量'),
26:('固定角域与波长身份','Cu波长粉末线','Mo波长粉末线与独立密度/对称性','校验反射/晶面间距比较的适用范围','中等测量协议对照，不预设受限角域总含相同反射'),
27:('plot与taxon两种对象空间及各自顺序','plot多样性和组分距离','taxon树与性状距离','只在同对象空间进行关联与预设置换判断','多源对象对齐、随机化单位与最终科学判断'),
28:('四个独立plot与不等quadrat努力','plot加权的前/后/配对变化及区间','naive quadrat敏感性区间','比较估计量、区间宽度和符号，不偷换独立单位','组内依赖、配对和不等努力共同限制推断'),
29:('同一观察清单及固定物种列顺序','丰度Bray-Curtis','检出Jaccard与独立条件几何','比较丰度优势和观察到的检出周转','中等双观测定义对照，检出零不等于确认不存在'),
30:('同一地点反复季节观测及行总数','原始计数距离和每季多样性','行归一化距离','零置换的协议一致性与季节均匀度比较','中等估计定义敏感性，不把季节当独立随机点'),
31:('同样pond与guild对象及固定环境列尺度','Euclidean环境/组分关联','Manhattan环境/组分关联','比较两种方法的预设关联判定','中等度量敏感性，两个数值结果不建立因果关系'),
32:('同一无根树的两个序列化根与同样taxon顺序','两个根的树距离和root-to-tip','独立性状距离和两路关联','成对距离不变、根距离可变与性状见证联合核验','拓扑不变量不能与序列化根或进化速率混淆'),
33:('同一空间样方的共同组分矩阵','地理距离和描述性关联','土壤距离和描述性关联','较强关联不意味着因果可识别','中等混杂审计，禁止把空间结构当无限制置换证据'),
34:('相同taxon列与各stand观测单位','局部多样性与两种距离','合并样本多样性','pooled熵与mean-local熵比较','中等非线性估计量汇合，删除无关地区bootstrap'),
35:('原始QC与唯一授权的R3纠正来源','各原始记录独立QC','可用记录的组成和纠正后QC','完整保留原始不确定性及纠正结果','基础局部修复，不猜碱基、不丢原始问题证据'),
36:('四条固定人工、无功能声明的规范控制序列','每条控制的亲疏水库存','脂肪族指数和本地pI','相同序列身份下汇总多种测量控制属性','基础属性库存，用于受控并行与报告一致性，不称科学发现'),
37:('每条人工RNA的原始不确定性与nongap分母','各记录的质量/GC界','规范记录的组成','全部GC宽度及最大不确定记录的并列','基础不确定性分支，宽度不能被已知碱基比例替代'),
38:('相同plot配对次序及给定单调评分','线性与秩相关四路对照','两种尺度的独立bootstrap','秩不变性与尺度相关性分别判断','中等变换敏感性，不把序数均值当原单位平均生长'),
39:('按设备分组的唯一训练/持出划分','各惩罚模型的训练与预测','各分支的真正持出误差','收齐各模型误差后选择，禁止读数级泄漏','共享划分、数据边界和模型选择共同约束'),
40:('共享图Laplacian与明确时间单位','特征谱','多个时刻的指数传播链','按同一目标比较实际传播结果','中等共享算子、多级分支，不把矩阵指数实现难度当方法发现'),
41:('各矩阵的实际谱及严格SPD阈值','独立候选的谱检验','通过后逆矩阵和独立线性系统解','不合格分支空值与两个数值结果核验','观测门控、错误/科学否定区分和方法分叉'),
42:('每个独立实例内的配对差与共同检验族','各优化器精确配对随机化','各效应bootstrap','所有p值共同BH调整后统一报告','中等共享对照和跨分支多重性汇合'),
43:('仅训练期拟合的概率模型与同一持出概率向量','校准质量','多阈值分类/代价链','以实际代价统一选择而非默认0.5','中等共享概率及决策域，需要一致的标准化坐标'),
44:('每个传感器的同一估计梯度','积分恢复变化','Hermite中点插值','与源变化闭合并比较离散诊断','基础共享导数与fork/join，不伪装为不确定度估计'),
45:('同一资源矩阵/目标与不同场景容量','各场景LP','各解的资源及目标独立回代','可行见证核验后比较收益','中等求解和证书并行，不把只找到数值当约束验证'),
46:('同一探索对象与唯一标准化结果','原始空间聚类/几何','标准化空间聚类/几何','标签不变的ARI及两种质量','中等状态复用，簇编号任意但分区必须一致'),
47:('冻结的训练尺度与训练PCA基','各维数持出重建','独立投影几何','跨维数误差及符号不变的距离核验','中等有界无泄漏投影，不是无限维度搜索'),
48:('同一有限总体和稀有标记计数','无放回覆盖','不同样本量有放回计数分布','比较零命中概率与最大概率质量','基础分布模型对照，标记间独立性不被假设'),
49:('共享训练/持出角色及各自拟合初值和界','各响应函数族的拟合','各族持出评估链','根据真正持出误差比较族','中等竞争模型工作流，不能训练残差选胜者'),
50:('每条传感器的拟合多项式','完整逆目标根','导数转折根及物理支持检查','保留多根、复根和支持内候选，不能假设唯一逆','逆问题多解、支持边界与共用拟合的双重证据链')}


def generate(base=BASE):
    from publication import REVISED_IDS
    tasks=[json.loads(l) for l in (base/'questions.jsonl').read_text().splitlines()]
    designs={d['id']:d for d in json.loads((base/'design.json').read_text())['studies']}
    studies=[]
    for task in tasks:
        tid=task['id'];n=int(tid[-4:]);design=designs[tid]
        if n<=50 and n!=8:
            shared,a,b,join,reason=PROFILES[n]
            tier='advanced' if n in ADVANCED else 'foundation' if n in FOUNDATION else 'intermediate'
            profiles={'difficulty_tier':tier,'difficulty_basis':reason,'shared_prerequisite':shared,'parallel_scientific_subtasks':[a,b],'scientific_join':join}
        else:
            profiles={k:design[k] for k in ['difficulty_tier','difficulty_basis','shared_prerequisite','parallel_scientific_subtasks','scientific_join']}
        profiles.update(reference_action='regenerated_clean_react' if tid in REVISED_IDS else 'reused_after_identity_and_scientific_review',
            fit_evidence='Scientific task, current criteria, real observations and source-backed isolation annotations; no baseline outcome selection.')
        design.update(profiles)
        studies.append({'id':tid,'domain':task['domain'],'title':task['question'].split('. ')[0],**profiles})
    counts=dict(Counter(t['difficulty_tier'] for t in studies));domains=dict(Counter(t['domain'] for t in tasks))
    assert len(tasks)==100 and set(domains.values())=={25},domains
    assert counts=={'advanced':28,'intermediate':52,'foundation':20},counts
    for domain in domains:
        assert Counter(t['difficulty_tier'] for t in studies if t['domain']==domain)=={'advanced':7,'intermediate':13,'foundation':5}
    data={'schema_version':'scimas.special.strata.v1','suite':'scimas-special-100-v2','reviewed_on':'2026-11-05',
        'task_count':100,'difficulty_counts':counts,'domain_counts':domains,
        'advanced_domain_counts':dict(Counter(t['domain'] for t in studies if t['difficulty_tier']=='advanced')),
        'reference_policy':{'regenerated':len(REVISED_IDS),'unchanged_reused':100-len(REVISED_IDS),'model':'gpt-6.1-sol','generation_api_used':False,
            'scope':'Relative to Special-100 v1. Every revised public question, including the redesigned multi-record0073, has a new public-context reference; unchanged57 retain current-identity verified references.'},
        'difficulty_definition':{'advanced':'Interacting scientific/method-domain boundaries with meaningful branches and a nontrivial scientific join; design-based, not measured baseline failure.',
            'intermediate':'A coherent multi-method comparison or dependency graph with shared evidence and an actual scientific decision.',
            'foundation':'A bounded control problem with reusable state, independent branches and a consistent scientific join. Lower effort for graph execution, not a claim that serial methods trivially solve it.'},
        'selection_policy':['Every task has a scientific purpose and an explicit graph-execution mechanism.',
            'Tool count or internal algorithm complexity alone does not establish task difficulty.',
            'Public inputs and three metrics are shared across baselines; equivalent correct scientific routes are eligible.',
            'No model-specific score bonus or hidden reference serial-order requirement.',
            'Readiness and execution-safety evidence do not establish measured end-to-end speedup.'],
        'scope':'Independent Special-100; neither Full-500 nor Mini-200 modified.','tasks':studies}
    for name,value in [('strata.json',data),('design.json',{'studies':[designs[t['id']] for t in tasks]})]:
        (base/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:data[k] for k in ['task_count','difficulty_counts','domain_counts','advanced_domain_counts']},ensure_ascii=False))

if __name__=='__main__':generate()
