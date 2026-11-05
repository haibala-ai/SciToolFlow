"""Individually reviewed Full-source selections for Mini; IDs refer directly to Full."""

SELECTION = {'Chemical': [1, 15, 29, 35, 47, 64, 68, 70, 71, 72, 74, 75, 76, 77, 78, 79, 83, 87, 92, 125, 127, 396, 461, 464, 488], 'Material': [6, 19, 28, 101, 107, 147, 153, 155, 175, 181, 182, 185, 190, 193, 195, 198, 199, 200, 202, 206, 208, 211, 214, 215, 220], 'Biology': [239, 242, 245, 252, 254, 255, 256, 259, 260, 263, 265, 267, 281, 285, 288, 300, 305, 315, 322, 326, 329, 331, 334, 353, 358], 'MachineLearning': [377, 378, 379, 381, 382, 383, 385, 387, 389, 400, 427, 433, 439, 443, 449, 450, 467, 468, 471, 472, 476, 481, 483, 490, 499]}

REVIEW = {
  "1": {
    "scientific_goal": "候选结构的多证据筛选",
    "parallel_subtasks": [
      "候选的中性精确质量核验",
      "候选的结构选择性检验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Calibrated mass and graph-selective evidence are independent candidate tests; their join preserves unresolved identities rather than choosing one guessed structure."
  },
  "15": {
    "scientific_goal": "扩散NMR条件间尺寸比较",
    "parallel_subtasks": [
      "第一条件的衰减曲线拟合",
      "第二条件的衰减曲线拟合"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Qualify condition-specific attenuation windows, share each fitted nuisance correction, and compare normalized radii; absolute diffusion remains a separate identifiability question."
  },
  "29": {
    "scientific_goal": "附加光谱通道的信息比较",
    "parallel_subtasks": [
      "第一附加通道的设计矩阵分析",
      "第二附加通道的设计矩阵分析"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Each additional channel has an independently assessed physical response matrix; a common singular-value criterion compares information without candidate-specific rescaling."
  },
  "35": {
    "scientific_goal": "线性逐步增长模型的单体选择",
    "parallel_subtasks": [
      "第一组候选的醇羟基计数",
      "其余候选的醇羟基计数"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Graph-derived alcohol functionality gates molecular inventory measurements; the join is a defined stoichiometric model rather than a preparation procedure."
  },
  "47": {
    "scientific_goal": "训练验证集的骨架重叠审查",
    "parallel_subtasks": [
      "训练记录的骨架提取",
      "验证记录的骨架提取"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Training and validation scaffold extraction share one aromaticity policy; identity-aware intersection tests split independence without equating it with molecule inequality."
  },
  "64": {
    "scientific_goal": "竞争动力学模型的观测设计",
    "parallel_subtasks": [
      "第一模型的平稳与时间响应",
      "第二模型的平稳与时间响应"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two rate generators support independent balance and transient branches; one finite observation-plan comparison joins stationary equivalence with time-dependent discrimination."
  },
  "68": {
    "scientific_goal": "弛豫校正的内标定量",
    "parallel_subtasks": [
      "待测物信号窗口的积分",
      "参考物信号窗口的积分"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Reference/analyte integrations and independent relaxation factors meet in a unit-consistent amount estimate; optical assignment is fixed input, not inferred."
  },
  "70": {
    "scientific_goal": "沉积电荷与干质量守恒核验",
    "parallel_subtasks": [
      "样品电流的全区间积分",
      "匹配空白电流的全区间积分"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Sample and matched blank traces require independent integrations; stoichiometric mass and measured dry gain form a conservation check, not a mechanistic attribution."
  },
  "71": {
    "scientific_goal": "示踪回收率与停留时间资格",
    "parallel_subtasks": [
      "各运行的零阶回收积分",
      "其他运行的零阶回收积分"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Each tracer run has independent recovery evidence; eligibility controls which normalized time moment can be interpreted as a residence mean."
  },
  "72": {
    "scientific_goal": "静态与动态猝灭机制比较",
    "parallel_subtasks": [
      "寿命响应关系拟合",
      "校正通量后的非寿命响应拟合"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Throughput-corrected intensities and lifetimes constrain competing photophysical models independently; their joint consistency distinguishes model families."
  },
  "74": {
    "scientific_goal": "候选位点的四极跃迁归属",
    "parallel_subtasks": [
      "第一候选位点的能级计算",
      "第二候选位点的能级计算"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two site EFG branches share spin and unit conventions but require separate principal-axis/Hamiltonian spectra; assignment uses the complete observed line pair."
  },
  "75": {
    "scientific_goal": "多模式振动温度一致性审查",
    "parallel_subtasks": [
      "各Stokes频带的基线积分",
      "各anti-Stokes频带的基线积分"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Three mode-specific calibrated band integrals lead to independent temperature estimates and a common-temperature assessment; response and photon conventions remain fixed."
  },
  "76": {
    "scientific_goal": "色谱柱与速度的约束选择",
    "parallel_subtasks": [
      "第一色谱柱的模型拟合",
      "第二色谱柱的模型拟合"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Each column has an independent constrained model audit and admissible domain; the final comparison minimizes time only among scientifically feasible operating points."
  },
  "77": {
    "scientific_goal": "酸碱物种分布下的分配比较",
    "parallel_subtasks": [
      "第一中性结构的分配估计",
      "第二中性结构的分配估计"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Each solute has an independent speciation/partition branch under the same phase-volume rule; the robust pH decision joins both worst-case fractions."
  },
  "78": {
    "scientific_goal": "振动几何与IR强度联合归属",
    "parallel_subtasks": [
      "源计算的振动位移读取",
      "同源频率与IR强度读取"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Source-linked equilibrium geometry and mode/intensity evidence meet in an actual displacement classification; it is not a repeated thermal-component inventory."
  },
  "79": {
    "scientific_goal": "随机支化模型的进料比较",
    "parallel_subtasks": [
      "第一候选进料的官能团核验",
      "其他候选进料的官能团核验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Independent graph functionalities and weighed-feed conversions form blend-specific excess-functionality calculations; one branching model joins the competing feeds."
  },
  "83": {
    "scientific_goal": "固定报告吸附量下的表观热比较",
    "parallel_subtasks": [
      "第一负载水平的温度斜率拟合",
      "第二负载水平的温度斜率拟合"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Several temperature curves share uptake identity but require independent inverse-pressure interpolation; supported-load eligibility precedes the common heat-proxy comparison."
  },
  "87": {
    "scientific_goal": "资格约束下的形状多样性选择",
    "parallel_subtasks": [
      "各候选的分子式资格检查",
      "合格候选的统一构象形状分析"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Formula,charge and fragment eligibility precede conformer-specific shape comparisons; the objective is pair diversity rather than mirror/pose equivalence."
  },
  "92": {
    "scientific_goal": "双电极的传质校正活性比较",
    "parallel_subtasks": [
      "第一电极的传质与膜联合拟合",
      "第二电极的传质与膜联合拟合"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Each electrode has an independent thickness/rotation inverse problem; kinetic ranking and observed-current ranking are joined without conflating transport and activity."
  },
  "125": {
    "scientific_goal": "离子归属的多证据筛选",
    "parallel_subtasks": [
      "各候选的中性精确质量核验",
      "各候选的电荷与组成核验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Calibration/validation roles anchor independent candidate-ion hypotheses; all isotope-tagged peaks must be reconciled with one charge/copy assignment."
  },
  "127": {
    "scientific_goal": "旋光逆问题的可辨识范围",
    "parallel_subtasks": [
      "同一约束集上的组分下界求解",
      "同一约束集上的组分上界求解"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Stereochemical identity, concentration constraints and optical channels feed rank and feasible-bound analyses; sign of rotation is not an identity label."
  },
  "396": {
    "scientific_goal": "可逆交换速率的守恒核验",
    "parallel_subtasks": [
      "对映体R的份额清点",
      "对映体S的份额清点"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Full-series decay fitting and conservation-linked state predictions audit a directional-rate interpretation; this differs from selecting a transient measurement plan."
  },
  "461": {
    "scientific_goal": "共晶水合物的分析物质量分数",
    "parallel_subtasks": [
      "完整化学式单元的质量核验",
      "全部组分及其重复次数核验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Whole formula-unit inventory and analyte inventory remain distinct parallel mass bases; their join audits component loss in a calibration handoff."
  },
  "464": {
    "scientific_goal": "位点同位素标记的可辨识性",
    "parallel_subtasks": [
      "同一观测约束下的位点下界",
      "同一观测约束下的位点上界"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Independent atom inventories and site-label constraints support sharp isotope-location bounds; a marginal label histogram does not identify a joint site assignment."
  },
  "488": {
    "scientific_goal": "不同机械边界下的气体平衡",
    "parallel_subtasks": [
      "恒压边界下的平衡求解",
      "定容边界下的平衡求解"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two declared mechanical boundary models have independent equilibrium branches; compare their physically admissible solutions without treating gas balance as one universal condition."
  },
  "6": {
    "scientific_goal": "介电弛豫与导电竞争模型",
    "parallel_subtasks": [
      "第一组时间常数模型的拟合",
      "其他时间常数及导电模型的拟合"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Relaxation/conduction candidates share training/validation roles and fit independent complex-response systems; admissibility and untouched validation jointly determine support."
  },
  "19": {
    "scientific_goal": "混合价态的体相与子晶格证据",
    "parallel_subtasks": [
      "化学式约束的价态清点",
      "子晶格磁矩候选的求解"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Formula neutrality, response-corrected spectroscopy and sublattice magnetic constraints are independent evidence; the join preserves equivalent labelled assignments."
  },
  "28": {
    "scientific_goal": "框架的仿射与松弛稳定性",
    "parallel_subtasks": [
      "仿射刚度的谱分析",
      "松弛刚度的谱分析"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Periodic bar geometry is a common prerequisite for affine and internally relaxed mechanics; the join audits rigidity with gauge and shear conventions intact."
  },
  "101": {
    "scientific_goal": "磁热响应的可逆性审查",
    "parallel_subtasks": [
      "一条扫场分支的积分",
      "另一条扫场分支的积分"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two sweep branches independently produce Maxwell proxies; the join audits reversibility rather than declaring a derivative calculation thermodynamic proof."
  },
  "107": {
    "scientific_goal": "DSC峰高与潜热报告口径",
    "parallel_subtasks": [
      "样品与空白的窗口积分",
      "质量及基线归一化所需的独立汇总"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Matched baseline reconstruction and excess-trace integration separate heat capacity from latent enthalpy while retaining dimensional consistency."
  },
  "147": {
    "scientific_goal": "非金属候选的光学各向异性",
    "parallel_subtasks": [
      "第一候选的主光轴分析",
      "其他候选的主光轴分析"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Electronic-tensor spectra are independent phase branches, followed by a shared optical-surrogate ranking; total static tensors are ineligible substitutes."
  },
  "153": {
    "scientific_goal": "指定方向的弹性刚度比较",
    "parallel_subtasks": [
      "一个传播方向的刚度分析",
      "其他指定方向的刚度分析"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Three stress-direction solves share one full compliance convention; projected strains jointly determine directional stiffness without replacing it by a scalar modulus."
  },
  "155": {
    "scientific_goal": "平面扩散张量反演",
    "parallel_subtasks": [
      "纵向协方差斜率拟合",
      "横向及交叉协方差斜率拟合"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Independent displacement-covariance slopes form one physical diffusion tensor; its spectrum audits anisotropy and the off-diagonal response."
  },
  "175": {
    "scientific_goal": "不同传播方向的声学模态",
    "parallel_subtasks": [
      "第一传播方向的模态求解",
      "第二传播方向的模态求解"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "One density/stiffness source supports direction-specific Christoffel matrices and modal branches; the scientific join compares actual directional speeds and splitting."
  },
  "181": {
    "scientific_goal": "XANES有限能轴偏移的选择",
    "parallel_subtasks": [
      "第一组候选偏移的配准",
      "其他候选偏移的配准"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Candidate axis shifts are independent frozen-reference comparisons on the same observation grid; the join selects alignment without a chemical-state claim."
  },
  "182": {
    "scientific_goal": "两个XANES谱的形状比较",
    "parallel_subtasks": [
      "第一谱的归一化积分",
      "第二谱的归一化积分"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Each computed spectrum has an independent derivative anchor and normalized integration branch; both must use the same finite-window descriptor."
  },
  "185": {
    "scientific_goal": "声子态密度的质量热容比较",
    "parallel_subtasks": [
      "第一态密度的积分与质量核验",
      "第二态密度的积分与质量核验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Each phonon DOS has independent normalization, thermal integration and mass-basis checks; the final comparison preserves full-cell versus per-atom identity."
  },
  "190": {
    "scientific_goal": "固定邻居对应下的局域畸变",
    "parallel_subtasks": [
      "参考与第一状态的几何核验",
      "参考与其他状态的几何核验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "State-specific fixed-neighbor least-squares fits share one correspondence; residual nonaffinity distinguishes deformation from rigid/basis changes."
  },
  "193": {
    "scientific_goal": "自旋态密度的局部与积分指标",
    "parallel_subtasks": [
      "第一自旋通道的窗口积分",
      "第二自旋通道的窗口积分"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Fermi-point interpolation and supplied-window spin integrations are independent readouts; the join prevents a local descriptor from becoming a whole-cell moment."
  },
  "195": {
    "scientific_goal": "迁移路径的移动原子归属",
    "parallel_subtasks": [
      "第一组路径图像的几何提取",
      "其余路径图像的几何提取"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Adjacent path segments require independent periodic displacement observations; the join compares all-atom and dominant-atom path summaries."
  },
  "198": {
    "scientific_goal": "电极电位的区间配对积分",
    "parallel_subtasks": [
      "第一组成区间的电位积分",
      "其他组成区间的电位积分"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Electrode curves have independent coordinate/interval reconstructions; a common accessible charge window precedes the energy calculation."
  },
  "199": {
    "scientific_goal": "有限能量截断的谱矩覆盖",
    "parallel_subtasks": [
      "较低候选截止的覆盖积分",
      "较高候选截止的覆盖积分"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Several finite cutoffs share a normalization and static reference; independent cumulative moments must establish both sufficiency and failure of smaller cutoffs."
  },
  "200": {
    "scientific_goal": "有限本征值路径的费米穿越",
    "parallel_subtasks": [
      "第一候选的能带范围核验",
      "第二候选的能带范围核验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Candidate eigenvalue paths have independent occupancy/crossing checks; any gap statement must retain k-point correspondence and candidate eligibility."
  },
  "202": {
    "scientific_goal": "晶界快照的体积超额比较",
    "parallel_subtasks": [
      "第一边界快照的几何核验",
      "第二边界快照的几何核验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Bulk volume-per-atom and two boundary geometries supply independent inventories/areas; excess lengths are compared under one interface-count convention."
  },
  "206": {
    "scientific_goal": "热运动各向异性的反射误差",
    "parallel_subtasks": [
      "晶胞度量的提取",
      "热位移张量主方差的求解"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Reciprocal geometry and a Cartesian thermal covariance support reflection-specific attenuation branches; comparison retains the distinct covariance representation."
  },
  "208": {
    "scientific_goal": "有限候选的局域离子环境复核",
    "parallel_subtasks": [
      "第一候选的周期配位环境",
      "第二候选的周期配位环境"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Independent ionic-environment audits require every valid periodic-image contact; sitewise residuals are joined before prioritizing the candidate records."
  },
  "211": {
    "scientific_goal": "有效质量的方向与高阶模型",
    "parallel_subtasks": [
      "第一方向的高阶色散拟合",
      "第二方向的高阶色散拟合"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two directions and two curvature models form independent fits on common reciprocal coordinates; the join separates physical anisotropy from finite-window model bias."
  },
  "214": {
    "scientific_goal": "同一样品的吸附路径依赖",
    "parallel_subtasks": [
      "第一历史分支的数据投影",
      "第二历史分支的数据投影"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two adsorption histories have independently bounded/interpolated curves; the join tests path dependence without replacing it by one equilibrium fit."
  },
  "215": {
    "scientific_goal": "表面重构对受限平衡形状的影响",
    "parallel_subtasks": [
      "允许重构的半空间几何求解",
      "不允许重构的半空间几何求解"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Surface-state choices share one restricted shape model but require independent reconstruction candidates; their comparison retains the declared feasible geometry."
  },
  "220": {
    "scientific_goal": "压力下竞争相的稳定性",
    "parallel_subtasks": [
      "第一相的能量体积拟合",
      "第二相的能量体积拟合"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Competing phase branches share pressure/energy conventions; their finite-pressure stability comparison is distinct from static phase labels or crystal-matching controls."
  },
  "239": {
    "scientific_goal": "有限肽质量通道的混合物可辨识性",
    "parallel_subtasks": [
      "同一非负可行集的各项下界",
      "同一非负可行集的各项上界"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Finite mass channels support independent feasible-composition extrema; the joint interpretation preserves mixture nonidentifiability rather than identifying a sequence to engineer."
  },
  "242": {
    "scientific_goal": "构象系综的距离反演局限",
    "parallel_subtasks": [
      "近构象的源几何距离",
      "远构象的源几何距离"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two conformer geometries feed a nonlinear measurement/population inversion; a single-distance surrogate is compared with the actual mixture model."
  },
  "245": {
    "scientific_goal": "组成变化与绝对表达的区别",
    "parallel_subtasks": [
      "外标约束的每细胞校准",
      "内源总量归一化的组成变化"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Library composition and spike-normalized amount evidence have separate denominators; their join audits which absolute changes the observation convention identifies."
  },
  "252": {
    "scientific_goal": "计数差异与注释富集的分阶段核验",
    "parallel_subtasks": [
      "规定模型的全背景计数拟合",
      "同一基因背景的直接注释清点"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Count eligibility/effects and source-filtered annotations are separate scientific branches; their enrichment join retains both testing families and the original background."
  },
  "254": {
    "scientific_goal": "坐标质量与完整蛋白质量的区别",
    "parallel_subtasks": [
      "坐标文件原子库存质量",
      "参考序列各片段的完整质量"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Observed coordinate inventory and intact-sequence mass are independent measurements; a shared cell convention exposes their different crystallographic estimates."
  },
  "255": {
    "scientific_goal": "对数异速模型的回变换比较",
    "parallel_subtasks": [
      "直接指数回变换的测试误差",
      "训练涂抹校正回变换的测试误差"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Training-only log calibration supports two backtransformations and independent held-out errors; this is predictive retransformation, not sigma-covariance rescaling."
  },
  "256": {
    "scientific_goal": "叶绿体CDS坐标与翻译一致性",
    "parallel_subtasks": [
      "拼接后翻译的终止位点检查",
      "完整翻译与源蛋白的比对"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Annotation coordinate extraction and source-protein comparison audit one immutable CDS handoff; it performs no sequence redesign or functional enhancement."
  },
  "259": {
    "scientific_goal": "结构弹性网络的软模资格",
    "parallel_subtasks": [
      "一个接触半径下的网络谱",
      "其他接触半径下的网络谱"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Contact graphs at several radii have independent connectivity/spectrum branches; the join separates internal soft modes from disconnected zero modes."
  },
  "260": {
    "scientific_goal": "NMR系综的代表构象选择",
    "parallel_subtasks": [
      "第一组提交构象的坐标核验",
      "其余提交构象的坐标核验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Matched-residue pair fits cover the complete submitted NMR ensemble; the medoid and diameter require a global join, not an arbitrary single pose."
  },
  "263": {
    "scientific_goal": "A280报告的半胱氨酸假设",
    "parallel_subtasks": [
      "第一参考蛋白的质量与组分核验",
      "第二参考蛋白的质量与组分核验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Independent deposited-chain inventories support two coefficient assumptions per candidate; the final bias comparison is a finite reporting audit, not protein modification."
  },
  "265": {
    "scientific_goal": "祖先相关对均值信息量的影响",
    "parallel_subtasks": [
      "树相关模型的GLS方差",
      "独立末端模型的参照方差"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Tree covariance and independent-tip reference calculations share one root convention; compare information and GLS weights before observing traits."
  },
  "267": {
    "scientific_goal": "固定酵母基因面板的功能概览",
    "parallel_subtasks": [
      "第一组功能节点的后代查询",
      "其余功能节点的后代查询"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Gene-specific evidence filtering and ontology traversals are independent; their nonexclusive coverage join deduplicates genes and preserves open-world limitations."
  },
  "281": {
    "scientific_goal": "未知根性状的祖先预测误差",
    "parallel_subtasks": [
      "未知根条件下的预测误差计算",
      "把估计根当已知时的对照计算"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Tip/ancestor covariance and unknown-root uncertainty meet in prediction and variance branches; this differs from tree-root distance invariance."
  },
  "285": {
    "scientific_goal": "RNA计数输入与设计就绪性",
    "parallel_subtasks": [
      "原始计数输入的合法性审查",
      "样本设计的秩与可辨识性审查"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Count-integrity and annotation/design-rank checks are independent handoff audits; every blocking reason must survive the joint readiness decision."
  },
  "288": {
    "scientific_goal": "种群阶段矩阵的局部敏感性",
    "parallel_subtasks": [
      "主模态的右向量求解",
      "主模态的左向量求解"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "One Perron mode anchors separately computed left/right sensitivity evidence; the final parameter-elasticity comparison retains stage identity."
  },
  "300": {
    "scientific_goal": "植被聚类与管理分类的一致性",
    "parallel_subtasks": [
      "无管理标签参与的群落预处理",
      "管理记录的样地身份对齐"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Community geometry and independently keyed management records are reconciled only for assessment; partition labels cannot substitute for matched sample identity."
  },
  "305": {
    "scientific_goal": "两个处理对共同对照的比较",
    "parallel_subtasks": [
      "第一处理相对对照的检验",
      "第二处理相对对照的检验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two shared-control contrasts are independent scientific calculations until their declared multiplicity-family join; signs and unequal-variance assumptions remain explicit."
  },
  "315": {
    "scientific_goal": "生长曲线的公共窗口累积量",
    "parallel_subtasks": [
      "第一组个体的基线相对积分",
      "其余个体的基线相对积分"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Each supported growth trajectory has its own baseline/window integration; the join excludes unsupported curves and retains all maxima."
  },
  "322": {
    "scientific_goal": "分枝过程的存续与灭绝",
    "parallel_subtasks": [
      "第一后代分布的灭绝根求解",
      "第二后代分布的灭绝根求解"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two complete offspring laws have independent admissible fixed-point branches; their join separates mean growth from persistence probability."
  },
  "326": {
    "scientific_goal": "局域变异对配准约定的稳健性",
    "parallel_subtasks": [
      "一种配准约定下的变换求解",
      "其他配准约定下的变换求解"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Anchor-set/model alignment branches share fixed residue identities; the join compares window variability under complete transformed coordinates."
  },
  "329": {
    "scientific_goal": "整体与分链刚体解释的区别",
    "parallel_subtasks": [
      "参考结构各链的几何提取",
      "移动结构各链的几何提取"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Class-preserving chain assignments and global/independent rigid models form alternative multi-branch fits; the join compares nested SSE with correct point weighting."
  },
  "331": {
    "scientific_goal": "竞争模型的共存与局部稳定性",
    "parallel_subtasks": [
      "共存点的Jacobian谱分析",
      "边界状态的入侵能力分析"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Interior balance, scaled local stability and boundary invasion calculations are independent witnesses; the join does not invent an initial-condition-independent winner."
  },
  "334": {
    "scientific_goal": "最优通量面的非唯一性",
    "parallel_subtasks": [
      "同一最优面的各通量下界",
      "同一最优面的各通量上界"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Optimal-face extrema and candidate assay discrimination share one feasible flux set; the result preserves route uncertainty and a post-assay update."
  },
  "353": {
    "scientific_goal": "区域消失与真实存活的区别",
    "parallel_subtasks": [
      "同一历史约束下的存活下界",
      "同一历史约束下的存活上界"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Observation-history matching and latent survival/emigration bounds are separate witnesses; their join reports partial rather than point identification."
  },
  "358": {
    "scientific_goal": "平移不变谐模型的相对涨落",
    "parallel_subtasks": [
      "第一平衡载荷的静态响应",
      "第二平衡载荷的静态响应"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Balanced-load solves and gauge-invariant covariance contrasts are independent branches; compare pair compliance without substituting marginal fluctuations."
  },
  "377": {
    "scientific_goal": "采集成本约束下的测量协议",
    "parallel_subtasks": [
      "第一可负担特征协议的验证",
      "其他可负担特征协议的验证"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Candidate measurement protocols share one valid cohort and accounting budget; independent held-out evidence is joined only among affordable models."
  },
  "378": {
    "scientific_goal": "形态校准的子群迁移审查",
    "parallel_subtasks": [
      "有性别编码子群的预测误差",
      "幼体编码子群的预测误差"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "One frozen morphology calibration feeds two disjoint cohort-error branches; the join compares transport error and signed bias without refitting test labels."
  },
  "379": {
    "scientific_goal": "配对研究的两种推断口径",
    "parallel_subtasks": [
      "精确随机分配检验",
      "名义配对t检验"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Technical readings and randomized-unit metadata are reconciled before two independent null-specific tests; the join keeps design-based and model-based claims distinct."
  },
  "381": {
    "scientific_goal": "标签位移下的未标注批次组成",
    "parallel_subtasks": [
      "未标注批次的固定预测",
      "独立校准样本的混淆矩阵"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Recognizer predictions on calibration and target panels have independent aggregate roles; a common class-conditional transfer model determines mixture feasibility."
  },
  "382": {
    "scientific_goal": "未来时间块的趋势模型选择",
    "parallel_subtasks": [
      "线性季节模型的拟合与预测",
      "二次季节模型的拟合与预测"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Competing seasonal trend bases have independent fits and future-block errors; the join selects a model, unlike fixed-ridge embargo or rolling-scale checks."
  },
  "383": {
    "scientific_goal": "固定分类器的条件性能",
    "parallel_subtasks": [
      "第一预先指定子群的混淆矩阵",
      "第二预先指定子群的混淆矩阵"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "A fixed recognizer supports multiple group/class-conditioned error branches; the join preserves denominators and separates conditional gaps from marginal gaps."
  },
  "385": {
    "scientific_goal": "冻结预测器的配对损失差",
    "parallel_subtasks": [
      "第一冻结模型的持出预测",
      "第二冻结模型的持出预测"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two frozen predictions share held-out vehicle identity; paired losses and paired-bootstrap uncertainty are joined without independently resampling models."
  },
  "387": {
    "scientific_goal": "拟合预测与区间校准的分离",
    "parallel_subtasks": [
      "固定模型的最终评估预测",
      "独立校准残差的有限样本排序"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Training,calibration and final-assessment branches have distinct information roles; one calibrated radius feeds untouched prediction-coverage assessment."
  },
  "389": {
    "scientific_goal": "含参数选择的完整外层验证",
    "parallel_subtasks": [
      "第一组外层划分内的选择与评估",
      "其余外层划分内的选择与评估"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Independent outer splits each contain full tuning/refit subgraphs; pooled errors estimate the complete selection procedure rather than one fixed candidate."
  },
  "400": {
    "scientific_goal": "训练期可用性约束下的预测",
    "parallel_subtasks": [
      "不同候选特征的训练期可用性检查",
      "其余候选特征的训练期可用性检查"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Training availability and imputation decisions anchor a frozen predictor; held-out evaluation cannot feed either preprocessing decision."
  },
  "427": {
    "scientific_goal": "不同误差尺度的校准拟合",
    "parallel_subtasks": [
      "原始响应尺度下的拟合",
      "对数响应尺度下的拟合"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Original-response and log-response estimators have independent fits but a common scientific response-scale assessment; distinct from absolute-sigma covariance checks."
  },
  "433": {
    "scientific_goal": "残差影响协议的预测稳健性",
    "parallel_subtasks": [
      "平方损失协议的预测",
      "软损失协议的预测"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Two residual-influence protocols have independent constrained fits and predictions; the join reports sensitivity without unsupported covariance claims."
  },
  "439": {
    "scientific_goal": "开发选择重拟合的完整边界",
    "parallel_subtasks": [
      "第一正则化候选的验证评估",
      "其他正则化候选的验证评估"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Parallel development candidates share one role boundary; selection must trigger a legitimate full-development refit before final untouched assessment."
  },
  "443": {
    "scientific_goal": "分组校准与总体校准的区别",
    "parallel_subtasks": [
      "固定模型的查询点预测",
      "分组及总体校准分数的有限样本排序"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Group-specific calibration branches share one training predictor; a pooled alternative is audited without equating pooled and within-group coverage."
  },
  "449": {
    "scientific_goal": "弱标签下的相对性能范围",
    "parallel_subtasks": [
      "各分类器风险的下界计算",
      "各分类器风险的上界计算"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Marginal and paired classifier-risk extrema share one possible truth allocation; their join cannot subtract incompatible optimized endpoints."
  },
  "450": {
    "scientific_goal": "不完全依从下的因果可辨识范围",
    "parallel_subtasks": [
      "同一观测约束下的效应下界",
      "同一观测约束下的效应上界"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Observed encouragement panels and latent response-type extrema share one population model; the join separates local from population effects."
  },
  "467": {
    "scientific_goal": "分层与边际优势比的区别",
    "parallel_subtasks": [
      "各层内的分子与分母计算",
      "边际混合分布的组成计算"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Within-stratum and marginal association branches use the same actual cells; the join audits noncollapsibility without declaring a causal mechanism."
  },
  "468": {
    "scientific_goal": "校准设计的目标特异性",
    "parallel_subtasks": [
      "各候选设计的信息矩阵求逆",
      "其他设计的信息矩阵求逆"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Candidate information matrices are independent design branches with common nuisance coefficients; query-specific variance and determinant objectives are compared."
  },
  "471": {
    "scientific_goal": "双通道的完整对象覆盖",
    "parallel_subtasks": [
      "共同半宽下的下端点计算",
      "共同半宽下的上端点计算"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Channel-specific residual/scaling branches must be joined by whole-object calibration; independent channel claims cannot certify simultaneous coverage."
  },
  "472": {
    "scientific_goal": "选择性记录下的双稳健估计",
    "parallel_subtasks": [
      "工作结果模型的残差计算",
      "记录概率模型的比率计算"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Four nuisance-model combinations are independent estimator branches under common exact population moments; the join checks double robustness and its limits."
  },
  "476": {
    "scientific_goal": "通道单位与规范相关分析",
    "parallel_subtasks": [
      "协方差块的可容许性核验",
      "原始交叉谱的奇异值分析"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Covariance-admissibility,raw cross-covariance and normalized CCA calculations are independent witnesses; an explicit unit-change branch checks coordinate invariance."
  },
  "481": {
    "scientific_goal": "重复插补的不确定性合并",
    "parallel_subtasks": [
      "插补点估计的组间离散程度",
      "各完成数据集方差的均值"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Within- and between-imputation uncertainty are separate paired-record summaries; their join differs scientifically from collecting independent studies."
  },
  "483": {
    "scientific_goal": "名义参数数与有效模型复杂度",
    "parallel_subtasks": [
      "各候选模型的有效自由度计算",
      "各候选模型的风险分解"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Ridge candidates share a fixed design/noise model but have independent smoother and SURE branches; selection does not preserve candidate-wise unbiasedness automatically."
  },
  "490": {
    "scientific_goal": "插值拟合与真正的留一预测",
    "parallel_subtasks": [
      "各候选次数的拟合与复杂度检查",
      "各候选次数的留一预测检查"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "Degree-specific leave-one-out subgraphs and training fits are separate evidence; the join rejects an interpolation residual as a predictive PRESS score."
  },
  "499": {
    "scientific_goal": "共同校准误差下的证据合并",
    "parallel_subtasks": [
      "完整协方差下的最优权重",
      "独立性假设下的参照估计量"
    ],
    "join_requirement": "等待所需分支及原题指定的其他检查完成后，按完整证据作比较、筛选或汇总。",
    "category": "standard",
    "note": "A shared covariance anchors optimal GLS and an independent naive estimator audit; signed weights and actual variance remain linked to the same source errors."
  }
}

REVIEW = {int(k): v for k, v in REVIEW.items()}
NOTES = {k: v["note"] for k, v in REVIEW.items()}
