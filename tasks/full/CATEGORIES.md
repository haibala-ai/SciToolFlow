# 任务分类

500 道任务按设计目标分为三类。分类用于浏览与分组分析，不改变科学评分标准，也不向 Agent 提供参考答案。

| 类别 | 数量 | 主要考察目标 |
| --- | ---: | --- |
| 高难度题 | 100 | 有明确边界的科学探究，强调方法选择、证据整合与多阶段推理 |
| 工具组合题 | 50 | 有科学意义的工具筛选、输入输出衔接和组合使用，兼顾工具覆盖 |
| 正常题 | 350 | 常规科学工作流中的工具选择、计算、验证与结果整合 |

正常题同样可能包含较难推理；调用次数本身不能决定科学难度。分类不是数据来源或修订批次，也不构成独立的训练／测试划分。

| 类别 | 化学 | 材料 | 生物／生态 | 机器学习／数理 |
| --- | ---: | ---: | ---: | ---: |
| 高难度题 | 25 | 25 | 25 | 25 |
| 工具组合题 | 16 | 17 | 17 | 0 |
| 正常题 | 102 | 102 | 69 | 77 |

以下列出全部题号及问题摘要。完整题文可用 `python cli.py task FLOW-0001 --dataset full` 查看，或在 [questions.jsonl](questions.jsonl) 中按题号查找。

## 高难度题

| 题号 | 学科 | 问题摘要 |
| --- | --- | --- |
| FLOW-0007 | 材料 | A thin-film screening team must decide what its present capacitance measurements establish before paying … |
| FLOW-0008 | 材料 | An alloy-screening team proposes that setting the middle principal transformation stretch to one is enoug… |
| FLOW-0020 | 化学 | A molecular-mixture study has several structure records, an unresolved neutral-mass window and two select… |
| FLOW-0102 | 材料 | A periodic tracer-hopping calculation appears to predict transport whenever its unit-cell graph is connec… |
| FLOW-0104 | 材料 | A nanocrystal team has only translated, volume-normalized shape information at several reservoir settings… |
| FLOW-0105 | 材料 | Determine whether a periodic heavy-atom basis can actually be identified from ideal diffraction. Reconcil… |
| FLOW-0106 | 材料 | Determine which physical band-topology conclusions are identifiable from energy spectroscopy and coherent… |
| FLOW-0109 | 材料 | Infer the infinite-lattice harmonic model from aliased small-supercell Hessians and a separate elastic me… |
| FLOW-0112 | 材料 | Determine the continuous equilibrium phase geometry of a controlled substitutional alloy from free-energy… |
| FLOW-0113 | 材料 | Resolve self-consistent charged-defect populations in a finite-site negative-U semiconductor model while … |
| FLOW-0114 | 材料 | Audit a proposed negative-capacitance stability and voltage-amplification claim using two supplied crysta… |
| FLOW-0117 | 材料 | Determine whether phase-speed inversion can establish complete in-plane auxeticity of an orthotropic coat… |
| FLOW-0118 | 材料 | Determine what fixed-composition energy observations and an average disordered crystal actually identify … |
| FLOW-0126 | 材料 | Audit directional plastic-work bounds of a controlled textured FCC aggregate. Reconstruct work-conjugate … |
| FLOW-0138 | 材料 | Infer a tilted two-phase thermoelectric laminate from source-calibrated coupled transport and two control… |
| FLOW-0145 | 材料 | Determine the full linear stability and damping-design limits of a nonconservative two-link elastic proto… |
| FLOW-0156 | 材料 | Design a passive composite thermal rectifier without confusing a large heat-flow ratio with guaranteed th… |
| FLOW-0177 | 材料 | Does the first local Griffith equality determine when a calibrated specimen cracks in a finite loading ma… |
| FLOW-0196 | 材料 | Does a rebounding stress-relaxation curve imply an active material? Identify an exact memory law, disting… |
| FLOW-0197 | 材料 | Can a calibrated layered dielectric support an omnidirectional bulk stopband without absorbing light? Res… |
| FLOW-0201 | 材料 | Does an electron-like low-field Hall signal contradict a hole-majority material, and does a large magneto… |
| FLOW-0205 | 材料 | Does a thermal cycle that repeats its stresses also stop plastic flow or accumulated deformation? Certify… |
| FLOW-0222 | 材料 | Which kinetic control genuinely accelerates polymorph conversion under uncertain equilibrium basin popula… |
| FLOW-0228 | 材料 | Can finite-scale helicity measurements distinguish a critical vortex separatrix from quasi-long-range and… |
| FLOW-0231 | 化学 | A glycine speciation analysis gives several microscopic acid-base calibrations that look compatible with … |
| FLOW-0236 | 化学 | A spectroscopy team has one completed water harmonic-frequency calculation, but only rounded displacement… |
| FLOW-0243 | 生物／生态 | A comparative plant-trait study must decide how robust its environment association is to shared ancestry,… |
| FLOW-0246 | 化学 | Infer what time-sampled conformational switching actually reveals about a driven three-state molecular cy… |
| FLOW-0261 | 生物／生态 | A mature-protein proteomics study appears to show conflicting changes in a plant RuBisCO small subunit. R… |
| FLOW-0270 | 生物／生态 | A structural-biology group wants to distinguish protein domain rearrangement from whole-protein repositio… |
| FLOW-0276 | 化学 | Audit an effective-spin interpretation of a three-center molecular magnet. Infer exchange parameters from… |
| FLOW-0277 | 生物／生态 | An evolutionary-genomics team has mixed exports of independent single-copy gene trees and wants to evalua… |
| FLOW-0286 | 材料 | How robust is an apparently stable nonreciprocal material chain when its boundary is weakly closed? Recon… |
| FLOW-0297 | 生物／生态 | Plan a defensible plant-occupancy census when both missed detections and false positives are possible. Fr… |
| FLOW-0317 | 生物／生态 | Determine exactly how much disulfide connectivity is identifiable from three complete nonreducing peptide… |
| FLOW-0332 | 化学 | Audit oxygen-provenance inference from a reaction graph and time-resolved isotope fine structure. Enumera… |
| FLOW-0333 | 化学 | Determine what anomalous scattering actually identifies about absolute molecular hand in a controlled inv… |
| FLOW-0337 | 生物／生态 | Audit a real published paired bulk RNA-seq analysis while distinguishing statistical discovery, scientifi… |
| FLOW-0339 | 化学 | Infer what an ideal conformational-ensemble spectroscopy model can actually identify from frozen molecula… |
| FLOW-0340 | 化学 | Audit a stereochemical candidate inventory for chemical screening. Classify all cyclic relative-configura… |
| FLOW-0341 | 生物／生态 | Determine what a partially observed neutral-marker haplotype alignment establishes about evolutionary his… |
| FLOW-0342 | 生物／生态 | Design a species-discovery subsampling allocation for six real frozen tropical-forest census plots. Audit… |
| FLOW-0343 | 化学 | Determine whether an exact functional-group conversion assay establishes polymer gel formation when react… |
| FLOW-0345 | 生物／生态 | Audit a stage-structured plant population in serially correlated environments. Determine whether positive… |
| FLOW-0346 | 生物／生态 | Investigate why positive stationary biomass correlation can conceal directional ecological interactions a… |
| FLOW-0347 | 化学 | Audit a coherent quantum-statistical model of hydrogen-isotope exchange and spin conversion. Recover isot… |
| FLOW-0348 | 化学 | Audit a reversible surface-reaction model using actual molecular identities, complete physical branches a… |
| FLOW-0350 | 化学 | Audit a four-pi-electron molecular distortion problem without replacing a fixed-N molecule by independent… |
| FLOW-0354 | 生物／生态 | Build a reusable, source-traceable resource-calibration hand-off and determine whether identical nutrient… |
| FLOW-0355 | 生物／生态 | Audit a linked-marker selection report whose marginal allele frequencies stay unchanged. Reconstruct phas… |
| FLOW-0356 | 化学 | Audit the thermodynamics of a restricted ideal-gas water-gas-shift/methanation system with inert ballast.… |
| FLOW-0357 | 化学 | Can a thermodynamically inconsistent quinone redox/proton square be repaired without changing trusted cal… |
| FLOW-0359 | 化学 | Can standard molecular graph tools distinguish a mechanically linked macrocycle assembly, and can a pairw… |
| FLOW-0360 | 化学 | Do two calibrated optical signals distinguish one-triplet release from two-triplet fission? Reconstruct e… |
| FLOW-0361 | 生物／生态 | Audit two anonymous evolutionary panels with different observation schemes. Use the complete source align… |
| FLOW-0362 | 生物／生态 | Do quaternary structural change and cooperative ligand binding identify a concerted allosteric mechanism?… |
| FLOW-0363 | 生物／生态 | Does matching stationary gene-expression noise preserve the time to a high RNA count? Identify every posi… |
| FLOW-0364 | 化学 | Can a driven chemical microreactor pattern remain stable when perturbations escape the symmetry used to c… |
| FLOW-0365 | 化学 | Does a chromatographic concentration overshoot require solute production, and which displacement fronts a… |
| FLOW-0368 | 化学 | When does an adiabatic geometric phase correctly describe molecular distortion motion, and where does it … |
| FLOW-0369 | 生物／生态 | Can a lineage movie identify population growth and clonal variability? Recover a heritable cell-cycle mod… |
| FLOW-0370 | 生物／生态 | Can silent single-neuron tuning and pairwise statistics hide a useful population code? Recover a four-neu… |
| FLOW-0371 | 生物／生态 | Can leaf gas exchange identify its internal biochemical limitation, and does the best carbon-water strate… |
| FLOW-0372 | 化学 | Can two exact exchange-NMR spectral points identify the molecule’s dynamics? Recover every admissible par… |
| FLOW-0374 | 生物／生态 | Which finite-time pulling protocol best estimates an equilibrium conformational free-energy difference, a… |
| FLOW-0375 | 化学 | Can a molecular interference node retain an ordinary low-temperature Lorenz ratio once dephasing and open… |
| FLOW-0386 | 机器学习／数理 | A scientific detector must be released before its deployment site and class mix are known. Its candidate … |
| FLOW-0390 | 生物／生态 | Can complete decision-time and acceptance-error observations identify the internal order and event cost o… |
| FLOW-0392 | 化学 | Which transport quantities can a finite-layer chemical admittance actually identify? Resolve the full spe… |
| FLOW-0393 | 机器学习／数理 | A compartment-transport team observes only two of six nodes after an unknown two-source tracer pulse. Det… |
| FLOW-0394 | 生物／生态 | Do identical stationary filament-length snapshots imply identical target-search kinetics? Resolve the ina… |
| FLOW-0397 | 化学 | Does one visible product imply coherent reaction channels? Derive the completely positive reaction-record… |
| FLOW-0405 | 机器学习／数理 | A laboratory needs a surrogate for the responses of all specimens in a future, previously unseen material… |
| FLOW-0406 | 机器学习／数理 | A materials-characterization laboratory wants to replace its logged two-stage assay policy. Audit which p… |
| FLOW-0407 | 机器学习／数理 | Develop a calibrated scientific surrogate and a robust next-batch measurement plan for a temperature-depe… |
| FLOW-0408 | 机器学习／数理 | Construct and audit a kinetic coarse-graining of periodic scientific configurations. Select a physically … |
| FLOW-0409 | 机器学习／数理 | Audit whether a selected scientific classifier really exceeds its paired-randomization null after the com… |
| FLOW-0412 | 机器学习／数理 | Audit a path-dependent reliability claim when every two-time increment marginal is known but higher-order… |
| FLOW-0413 | 机器学习／数理 | Investigate what a randomized encouragement study can establish about an optional numerical preconditione… |
| FLOW-0414 | 机器学习／数理 | Design and validate a learned rare-event path sampler for two overlapping failure definitions. Train a fi… |
| FLOW-0416 | 机器学习／数理 | Audit a finite scientific screening protocol whose stopping decision depends on repeatedly inspected data… |
| FLOW-0417 | 生物／生态 | Does a small equilibrium master fraction imply an error threshold at finite genome length? Reconcile the … |
| FLOW-0418 | 机器学习／数理 | Design a globally optimal adaptive scientific measurement policy for a fragile specimen under three candi… |
| FLOW-0419 | 机器学习／数理 | Calibrate a signed-source sensing dictionary and diagnose sparse reconstruction when a common operating o… |
| FLOW-0420 | 化学 | Can pressure variation overcome an azeotropic separation obstruction? Infer a consistent liquid-vapor mod… |
| FLOW-0421 | 机器学习／数理 | Can observational sparsity safely determine a scientific causal model, and which interventions are worth … |
| FLOW-0422 | 机器学习／数理 | How much does an exact set of scientific moment readouts identify about rare-event probabilities? Recover… |
| FLOW-0424 | 机器学习／数理 | What does noisy independent-component analysis actually identify? Recover dense binary-source mixing thro… |
| FLOW-0425 | 机器学习／数理 | Does increasing graph-clustering resolution reveal one consistent hierarchy? Certify the complete global … |
| FLOW-0426 | 机器学习／数理 | Can correlated noisy reruns of scientific summaries satisfy their marginal privacy promises jointly, and … |
| FLOW-0428 | 机器学习／数理 | What do partially overlapping sensor campaigns identify about joint variability, extreme contrast risk an… |
| FLOW-0429 | 机器学习／数理 | Does a two-factor scientific signal model deserve an ordinary two-parameter BIC penalty, and what do its … |
| FLOW-0430 | 机器学习／数理 | Does a sparse dynamical model learned from clean relaxation trajectories identify the governing law? Reco… |
| FLOW-0435 | 机器学习／数理 | Does equally successful separable logistic training select the same classifier under a change of optimiza… |
| FLOW-0436 | 机器学习／数理 | When does a knockoff filter actually control false discoveries? Construct the maximal valid Gaussian coup… |
| FLOW-0437 | 机器学习／数理 | What does an unpaired distribution alignment actually identify? Certify the complete transport cost/tail-… |
| FLOW-0438 | 机器学习／数理 | Does stochastic log-determinant estimation remain unbiased after finite Krylov truncation or adaptive sto… |
| FLOW-0458 | 生物／生态 | Can a mass-balanced metabolic optimum create impossible cellular work? Certify all thermodynamic process … |
| FLOW-0459 | 生物／生态 | When do force and extension ensembles agree for a short semiflexible filament? Infer bending from an exac… |
| FLOW-0470 | 材料 | When does a soft zero mode represent a real mechanism, and when can prestress or nonlinear elasticity sta… |

## 工具组合题

| 题号 | 学科 | 问题摘要 |
| --- | --- | --- |
| FLOW-0003 | 材料 | A crystal database handoff treats a per-atom packing-volume field as atomic number density and compares m… |
| FLOW-0009 | 化学 | Qualify a conformer-specific rotor export before using it in a rotational model. Recover the mass moments… |
| FLOW-0011 | 化学 | Select which attached chemical records best match a reference under two explicitly different retrieval re… |
| FLOW-0014 | 化学 | Recover the molecular graph implied by the attached coordinates under the stated bond-perception policy,t… |
| FLOW-0016 | 化学 | An analytical structure catalogue uses a single keto representation as an exact substructure filter. Dete… |
| FLOW-0030 | 化学 | A chemical annotation handoff assumes that merging two explicit hydrogen nodes into a nitrogen query nece… |
| FLOW-0032 | 化学 | Choose a molecular reference for a declared analytical calibration while respecting its exact descriptor … |
| FLOW-0033 | 化学 | Audit a molecular surface-report handoff that mixes atomic EState indices,EState-binned surface contribut… |
| FLOW-0037 | 化学 | Audit exported molecular atom-pair features against the attached graph and declared packing convention. R… |
| FLOW-0043 | 化学 | Construct a compact chemical reference panel using the attached fixed fingerprint-distance policy. Recove… |
| FLOW-0045 | 化学 | Audit a maximum-score chemical fragment hit before treating it as an exact structural match. Select the d… |
| FLOW-0046 | 化学 | Audit molecular-fragment cache de-duplication under two source spellings and a constitutional isomer. Obt… |
| FLOW-0054 | 化学 | Audit whether a molecular descriptor export gives equal weight to two named feature families. Obtain both… |
| FLOW-0061 | 化学 | Audit aromatic graph serialization before reusing molecular features. Carry the actual Kekule representat… |
| FLOW-0095 | 化学 | Audit a report that converts the sum of local radical electrons directly into a unique total-spin assignm… |
| FLOW-0098 | 化学 | Qualify a coordinate-preserving torsion handoff from an attached SDF. Recover the actual indexed candidat… |
| FLOW-0137 | 材料 | Qualify an electronic-structure scalar handoff before it is reused as a work-function or doping report. R… |
| FLOW-0141 | 材料 | A scalar capacitor report substitutes an electronic-only dielectric value for a static dielectric respons… |
| FLOW-0170 | 材料 | Qualify a database magnetic summary before using its per-site normalization. Reconcile its two moment rep… |
| FLOW-0171 | 材料 | Compare two computed phases under the attached common-driving-force capillary proxy. Obtain their source-… |
| FLOW-0172 | 材料 | Screen the attached polymorph candidates using two distinct thermodynamic reference comparisons. Retrieve… |
| FLOW-0174 | 材料 | Audit a forward-scattering export for a database calculation cell. Select the source composition capabili… |
| FLOW-0176 | 材料 | Assess whether a database local-environment report is sufficient to certify a regular tetrahedral geometr… |
| FLOW-0179 | 材料 | Estimate a local mechanical response from a published EOS curve. Resolve source-task ownership,keep energ… |
| FLOW-0180 | 材料 | Construct a conditional harmonic response from a source-consistent phonon DOS. Retrieve and read its full… |
| FLOW-0183 | 材料 | Compare two explicitly identified XAS records returned by a formula search while preserving their separat… |
| FLOW-0184 | 材料 | Qualify an archived charge-density export against an official historical object relationship. Choose the … |
| FLOW-0189 | 材料 | Audit a solvent-labelled molecular thermochemistry handoff. Reconcile each attached row identity and calc… |
| FLOW-0194 | 材料 | Audit two charge-state records by reconciling composition,reported charge,spin multiplicity and the vacuu… |
| FLOW-0203 | 材料 | Prepare the correct site mask for MOF branch analysis while auditing a proposed terminal-site substitutio… |
| FLOW-0219 | 材料 | Construct a chemically selected local coordinate export for a MOFsite. Follow the actual bond graph into … |
| FLOW-0229 | 材料 | Build a complete chemical inventory of the linker fragments produced from an attached MOF. Separate insta… |
| FLOW-0241 | 生物／生态 | Audit a coordinate-frame handoff that treats a geometric atom centroid as a mass center when reporting to… |
| FLOW-0266 | 生物／生态 | Assess whether a three-mode approximation is adequate for the explicitly defined coordinate-network fluct… |
| FLOW-0279 | 生物／生态 | Can a composition-only quality-control handoff preserve an order-sensitive protein descriptor? For the tw… |
| FLOW-0280 | 生物／生态 | Qualify an acidic peptide used as a theoretical charge-model reference. Retrieve its explicitly named pI … |
| FLOW-0293 | 生物／生态 | Determine which complete hypotheses survive a controlled DNA inventory audit that combines bulk GC and av… |
| FLOW-0294 | 生物／生态 | Reconcile an oligonucleotide UV concentration report before recording stock amounts. Retrieve the source-… |
| FLOW-0295 | 生物／生态 | Audit a structural summary whose declared broad-helix fraction was calculated using only DSSP class H. Se… |
| FLOW-0296 | 生物／生态 | Prepare an observed-residue handoff for a discontinuous protein-domain annotation. Reconcile the attached… |
| FLOW-0298 | 生物／生态 | Audit how an evidence-source filter changes an existing human molecular-function annotation report. Retri… |
| FLOW-0303 | 生物／生态 | Validate a circular-sequence comparison using a controlled record-origin test. Run the registered rotatio… |
| FLOW-0306 | 生物／生态 | Select an analysis window from a sparse published residue-score profile. Determine actual positional supp… |
| FLOW-0307 | 生物／生态 | Prepare a motif annotation for a residue-indexed handoff when the provider origin convention is unresolve… |
| FLOW-0308 | 生物／生态 | A reporting pipeline converts every published N-end-rule entry into one exact decay curve,including lower… |
| FLOW-0310 | 生物／生态 | Validate a source-matched predicted structure against the attached fixed coordinate reference. Generate o… |
| FLOW-0316 | 生物／生态 | Assess whether two completed entry-specific interface checks support a global noninteraction claim. Inspe… |
| FLOW-0336 | 化学 | Choose descriptor evidence that can actually distinguish branching between two same-size saturated carbon… |
| FLOW-0457 | 生物／生态 | Prepare a direct-interaction evidence summary while avoiding duplicate row inflation. Query the attached … |
| FLOW-0462 | 生物／生态 | Assess what a capped orthology retrieval actually supports before reusing it as a comparative sequence pa… |

## 正常题

| 题号 | 学科 | 问题摘要 |
| --- | --- | --- |
| FLOW-0001 | 化学 | A controlled synthetic analytical case uses the attached benign candidate-structure panel. Observed neutr… |
| FLOW-0002 | 材料 | Assess whether the declared ordinary non-anomalous powder observation can identify the orientation sign o… |
| FLOW-0004 | 材料 | Determine which mobility assignment and carrier-population interpretation the attached controlled low-fie… |
| FLOW-0005 | 材料 | Assess which finite-level entropy statements the attached controlled two-field calorimetry can identify. … |
| FLOW-0006 | 材料 | Determine which supplied relaxation/conduction models are supported by the attached controlled complex-pe… |
| FLOW-0010 | 材料 | Determine which transition sets the polarization-resolved bright onset in this controlled electronic-pane… |
| FLOW-0012 | 化学 | A controlled simulated chemical quantification study includes calibration standards and one diluted unkno… |
| FLOW-0013 | 化学 | Audit energy bookkeeping in the supplied simulated calorimeter calibration. Treat consecutive recorded he… |
| FLOW-0015 | 化学 | Assess whether the analyte effective hydrodynamic size changed between the two controlled diffusion-NMR c… |
| FLOW-0017 | 化学 | Plan a detector protocol and read count to detect the stated target concentration while controlling one-s… |
| FLOW-0018 | 化学 | Audit whether a candidate assay's mean transfer bias is equivalent to the reference for the prespecified … |
| FLOW-0019 | 材料 | A mixed-valence structure report treats equal spectral line areas as equal valence populations and then a… |
| FLOW-0021 | 化学 | Audit the gas-phase thermal Gibbs correction supported by the attached completed water frequency output a… |
| FLOW-0022 | 化学 | Prioritize the three supplied completed harmonic-frequency calculations for an explicitly defined low-fre… |
| FLOW-0023 | 化学 | Select the strongest computed IR diagnostic band in the1500–2000cm^-1 window of the attached completed vi… |
| FLOW-0024 | 化学 | Quantify sample-A using an internal standard that corrects multiplicative injection variation. Every aliq… |
| FLOW-0025 | 化学 | Choose an integrated kinetic model for a controlled concentration-time study. Zero-, first-, and second-o… |
| FLOW-0026 | 化学 | Estimate Arrhenius parameters from the attached controlled rate study using absolute kelvin. Documented t… |
| FLOW-0027 | 化学 | Adjust the controlled liquid→gas phase-change enthalpy from298.15K to330K using Kirchhoff’s law and the p… |
| FLOW-0028 | 材料 | A framework-mechanics report uses positive affine stiffness to certify resistance to every small uniform … |
| FLOW-0029 | 化学 | Select one additional spectroscopy channel to improve a two-analyte assay. Each candidate matrix contains… |
| FLOW-0031 | 化学 | Compare three controlled binary liquid mixtures for volumetric nonideality. Composition is ethanol mole f… |
| FLOW-0034 | 化学 | Review which digital structures can enter a stereochemistry-labeled model without inventing assignments. … |
| FLOW-0035 | 化学 | Screen a defined polyol panel for a computational linear step-growth material design. Require exactly two… |
| FLOW-0036 | 化学 | Choose an analogue of ethylbenzene CCc1ccccc1 from the library. Require an exact aromatic benzene ring; f… |
| FLOW-0038 | 化学 | Review input eligibility for a descriptor model trained on neutral single molecular entities. Require exa… |
| FLOW-0039 | 化学 | Quantify an unknown with response6.000 using the controlled calibration and its independently known respo… |
| FLOW-0040 | 化学 | Assess what can be quantified from the attached exact linear mixture assay, assuming nonnegative concentr… |
| FLOW-0041 | 化学 | Check whether the exact response can be explained by nonnegative amounts of the supplied library species … |
| FLOW-0042 | 化学 | Audit the attached digital equation annotations for conservation of every element. Coefficients multiply … |
| FLOW-0044 | 化学 | Summarize the controlled homolog distribution on both molecular-count and mass-weighted bases. The listed… |
| FLOW-0047 | 化学 | Audit scaffold-level overlap across the digital training and validation split. Use the ring-and-linker Be… |
| FLOW-0048 | 化学 | Estimate relative fluorescence quantum yield from the controlled corrected spectra and reference. Excitat… |
| FLOW-0049 | 化学 | Audit the controlled aqueous analysis on a charge-equivalent basis. The four reported species are free io… |
| FLOW-0050 | 化学 | Infer lithium amount in the unspiked sample from the controlled stable-isotope blend. Atom fractions in s… |
| FLOW-0051 | 化学 | A gas-property report substitutes the compressibility factor at one pressure for the integrated fugacity … |
| FLOW-0052 | 化学 | Audit the vibrational energy convention and reporting precision in the supplied completed Q-Chem frequenc… |
| FLOW-0053 | 化学 | Infer empirical partial orders of A and B from the controlled two-reactant initial-rate panel at fixed te… |
| FLOW-0055 | 化学 | Compute the ideal entropy of mixing for the attached distinguishable,nonreacting ideal gases initially se… |
| FLOW-0056 | 化学 | Locate the interior equal-composition point in the controlled binary vapor/liquid table. Use piecewise-li… |
| FLOW-0057 | 化学 | Estimate uncertainty in the equal-weight mean preparation bias relative to100mg/L. Each preparation is an… |
| FLOW-0058 | 化学 | Choose the least-cost acquisition setting that meets the declared idealized neutral-mass resolving criter… |
| FLOW-0059 | 化学 | Audit the controlled relative-free-energy network before reporting globally reconciled state energies. Ea… |
| FLOW-0060 | 化学 | Estimate the mean atom0-to-atom3 distance in the attached finite controlled conformer ensemble at298.15 K… |
| FLOW-0062 | 化学 | Select the lamp that gives the larger detected count rate perunitarea under the controlled ideal detector… |
| FLOW-0063 | 化学 | For the controlled three-state closed kinetic model,choose the earliest listed wait time at which BOTH sp… |
| FLOW-0064 | 化学 | Compare the two controlled kinetic models using both stationary and time-dependent evidence. Use column-v… |
| FLOW-0065 | 材料 | A full-cell energy estimate balances two reversible electrode capacities but ignores the finite lithium c… |
| FLOW-0066 | 化学 | Reconcile gas-phase Q-Chem thermochemical bookkeeping when replacing the 1 atm ideal translational standa… |
| FLOW-0067 | 化学 | Resolve the vapor/liquid equilibrium of the controlled mixture at345K and0.8bar under ideal Raoult-law be… |
| FLOW-0068 | 化学 | Audit internal-standard quantitation when the assigned analyte and reference signals have unequal longitu… |
| FLOW-0069 | 化学 | Identify which listed hydrationnumber is consistent with ALL three controlled initial/residuemass pairs. … |
| FLOW-0070 | 化学 | Reconcile the controlled drymass gain with the samplecurrent after the matchedblank correction. The decla… |
| FLOW-0071 | 化学 | Decide which finitewindow tracer runs support a normalized residence-time mean under the declared conserv… |
| FLOW-0072 | 化学 | Determine whether the paired fluorescence observations support dynamic quenching alone,static quenching a… |
| FLOW-0073 | 化学 | Assess whether the two assigned hydrogen sites can be distinguished by choosing a fixed crystalorientatio… |
| FLOW-0074 | 化学 | Assign the simulated zero-field nuclear-quadrupole linepair to one of the two candidate Al sites using BO… |
| FLOW-0075 | 化学 | Assess whether a single vibrational temperature is supported across the three assigned Raman modes in the… |
| FLOW-0076 | 化学 | Choose the fastest scientifically admissible column/linear-velocity pair for this controlled separation. … |
| FLOW-0077 | 化学 | Compare the listed pH conditions for the controlled dilute octanol/water distribution surrogate. Estimate… |
| FLOW-0078 | 化学 | Assign the symmetric O-H stretching mode in the supplied genuine completed water frequency calculation us… |
| FLOW-0079 | 化学 | Compare the controlled alcohol feeds using the ideal Flory-Stockmayer random-branching model. Only alipha… |
| FLOW-0080 | 化学 | Determine which candidate isotope assignments are compatible with the simulated rotational constants at t… |
| FLOW-0081 | 化学 | Infer the affine transfer relationship between the two controlled concentration-reporting instruments whe… |
| FLOW-0082 | 化学 | Determine which controlled binary-mixture study constrains its composition more tightly from the supplied… |
| FLOW-0083 | 化学 | Use the archived nitrogen/Zeolite5A temperature series to estimate an APPARENT fixed-reported-uptake heat… |
| FLOW-0084 | 化学 | Analyze the controlled binary-copolymer composition panel at the zero-conversion limit. The specified ter… |
| FLOW-0085 | 化学 | Compare two atom-centered monopole descriptions of the attached charged single-point calculation: NPA net… |
| FLOW-0086 | 化学 | Audit the controlled exact-mass oligomer ladder against the supplied finite mass models. Every reported p… |
| FLOW-0087 | 化学 | Select a pair of shape-diverse molecular controls from the attached finite panel while holding molecular … |
| FLOW-0088 | 化学 | Audit three proposed activity-coefficient pairs before using them as one binary-liquid thermodynamic mode… |
| FLOW-0089 | 化学 | Determine the three bulk-solution characterization quantities in the answer schema from this controlled m… |
| FLOW-0090 | 化学 | Audit whether an inventory-ratio pH shortcut remains adequate as the same weak-acid/sodium-salt inventory… |
| FLOW-0091 | 化学 | Choose the most selective admissible fixed-pH condition for the supplied controlled two-metal/one-ligand … |
| FLOW-0092 | 化学 | Compare the intrinsic kinetic activity of the two generic electrodes in the supplied controlled rotating-… |
| FLOW-0093 | 化学 | Decompose the rotational entropy change from the source water isotopolog to the one-site HDO counterfactu… |
| FLOW-0094 | 化学 | Audit the supplied fixed-checkpoint retrosynthesis proposal system against the virtual inventory. Obtain … |
| FLOW-0096 | 化学 | Use the controlled host–guest calorimetry to separate buffer-linked proton exchange from the observed bin… |
| FLOW-0097 | 化学 | Infer the self-association equilibrium and the shared species spectrum from the controlled paired-path op… |
| FLOW-0099 | 材料 | Audit whether classical vibrational equipartition is a defensible approximation for the attached complete… |
| FLOW-0100 | 材料 | Assess how strongly the attached open-shell calculation supports a one-site, nonnegative spin-localizatio… |
| FLOW-0101 | 材料 | A magnetic caloric report integrates one sweep and publishes the result as a reversible entropy change. A… |
| FLOW-0103 | 材料 | A phase-equilibrium report treats a single reference latent enthalpy as temperature independent over the … |
| FLOW-0107 | 材料 | A thermal-analysis summary reports the height of an endothermic DSC peak as latent enthalpy and divides i… |
| FLOW-0108 | 材料 | A phase-selection argument predicts the first nucleus by choosing the phase with the larger bulk free-ene… |
| FLOW-0110 | 材料 | A structure report assumes that a complete set of exact ordinary diffraction intensities uniquely specifi… |
| FLOW-0111 | 材料 | A vibrational-spectrum report attributes a finite spectral window only to modes whose centers fall inside… |
| FLOW-0115 | 材料 | A homogeneous polarization report treats every locally stable stationary branch as thermodynamic equilibr… |
| FLOW-0116 | 材料 | A stress-relaxation report accepts a passive discrete Maxwell representation because its finite observed … |
| FLOW-0119 | 材料 | A spherical-contact fit assigns all measured approach to specimen indentation and ignores test-machine an… |
| FLOW-0120 | 材料 | A porosimetry report turns each first intrusion pressure directly into a pore-body radius and counts newl… |
| FLOW-0121 | 材料 | A photonic-stack report replaces a layered period by its optical-path-matched uniform medium and equates … |
| FLOW-0122 | 材料 | An optical fit uses two exact excitation peaks to report a signed intersite coupling and assumes that mat… |
| FLOW-0123 | 化学 | Determine whether the attached hypothetical regular solution should remain homogeneous at its weighed fee… |
| FLOW-0124 | 化学 | Resolve a proposed inert-gas dilution argument for the attached controlled ideal associating gas. Begin w… |
| FLOW-0125 | 化学 | Determine which ion assignments the attached controlled mass-spectrometric evidence actually identifies. … |
| FLOW-0127 | 化学 | A chemical-analysis report interprets positive rotation at two wavelengths as proof that the lactic-acid … |
| FLOW-0128 | 化学 | A membrane-equilibrium report treats the outside solution as an unchanged salt reservoir and counts fixed… |
| FLOW-0129 | 化学 | A closed-mixture report uses the300K equilibrium constant to predict an adiabatic conversion and only aft… |
| FLOW-0130 | 化学 | A proton-binding analysis labels two intrinsic site pKa values as the two sequential macroscopic pKa valu… |
| FLOW-0131 | 化学 | An isotope-envelope report estimates one mean13Cfraction and assumes every carbon site labels independent… |
| FLOW-0132 | 化学 | A gated-kinetics report multiplies product-formation rate by an equilibrium conformer fraction and interp… |
| FLOW-0133 | 材料 | Choose one predicted crystal phase for a hypothetical lightweight elastic support using attached genuine … |
| FLOW-0134 | 化学 | A current-transient analysis assumes an electrode area before estimating diffusivity,then subtracts no ba… |
| FLOW-0135 | 化学 | A tautomer enumeration is used as if every returned graph had equal population,and its partition coeffici… |
| FLOW-0136 | 材料 | A hypothetical electrolyte permits every used electrode plateau only between2.5 and4.5V. Review the speci… |
| FLOW-0139 | 材料 | Identify every candidate record consistent with the controlled forward-simulated powder observation, then… |
| FLOW-0140 | 材料 | Compare the three specified calculated configurations for a lightweight magnetic-response study. Rank by … |
| FLOW-0142 | 材料 | Audit the specified MnO record before using it as an antiferromagnetic reference. Normalize its reported … |
| FLOW-0143 | 材料 | Estimate the reversible small-strain elastic energy stored in the specified Fe calculation cell under vol… |
| FLOW-0144 | 材料 | Plan shear-response characterization of the specified TiO2 phase. Before using the listed VRH estimate as… |
| FLOW-0146 | 材料 | Triage three phases for a metallic-alloy ductility follow-up using the attached MP summary and elasticity… |
| FLOW-0147 | 材料 | Compare the three specified nonmetal phases as ideal transparent, nonmagnetic optical-anisotropy candidat… |
| FLOW-0148 | 材料 | Audit the isotropic acoustic velocities of the specified Fe elasticity calculation. Independently reconst… |
| FLOW-0149 | 材料 | Can the attached Fe elasticity response be treated as calibrated to the geometry in the independent summa… |
| FLOW-0150 | 材料 | Quantify a controlled structure perturbation relative to the reference cell. The attached role index iden… |
| FLOW-0151 | 材料 | Estimate uniform isotropic lattice strain from the attached indexed, forward-simulated powder observation… |
| FLOW-0152 | 材料 | Calibrate an unknown X-ray wavelength using the attached indexed line from a known undeformed silicon ref… |
| FLOW-0153 | 材料 | Select the stiffest of the100,110 and111 directions for the supplied Fe IEEE stiffness tensor. For each u… |
| FLOW-0154 | 材料 | Infer the temperature gradient required to sustain the prescribed heat flux in the attached controlled an… |
| FLOW-0155 | 材料 | Infer a planar diffusion tensor from the attached centered displacement-covariance study. Initial displac… |
| FLOW-0157 | 材料 | Estimate the ideal energy to create two clean equivalent Fe(100) faces with the in-plane cell area of the… |
| FLOW-0158 | 材料 | Prepare a machine-readable formal-redox curation record for the specified insertion-electrode snapshot. R… |
| FLOW-0159 | 材料 | Convert the attached active-material crystal metric into a controlled porous-electrode design estimate. B… |
| FLOW-0160 | 材料 | Assess the framework expansion evidence of the attached computed insertion cycle. Volumes and masses are … |
| FLOW-0161 | 材料 | Estimate a provisional quasistatic ZnO voltage-response surrogate from the supplied piezoelectric,elastic… |
| FLOW-0162 | 材料 | Evaluate an idealized network-connectivity budget for the attached oxide design. Assume allSi andAl are t… |
| FLOW-0163 | 材料 | Use the supplied structure and the declared computational screen to prioritize,not certify,a MOF for furt… |
| FLOW-0164 | 材料 | Run the declared finite computational CO2/H2mixture screen on the supplied charged framework. Use absolut… |
| FLOW-0165 | 材料 | Audit normalization before using a periodic surface-slab cell as a specimen density. The role index ident… |
| FLOW-0166 | 材料 | Evaluate the largest polarization response permitted by a unit Frobenius norm of symmetric strain for the… |
| FLOW-0167 | 材料 | Assess the specified computed Fe3O4 record against the attached two competing stable phases in one GGA_GG… |
| FLOW-0168 | 材料 | Estimate finite-interval expansion coefficients from two controlled model cell states. The CIF axes corre… |
| FLOW-0169 | 材料 | Estimate two-phase Wiener bounds for the controlled dielectric composite. The first phase is silicon and … |
| FLOW-0173 | 材料 | Assess which of two declared idealized cellular-solid regimes better describes the controlled normalized … |
| FLOW-0175 | 材料 | Compare long-wavelength acoustic modes for the two supplied propagation directions in the computed Fe pha… |
| FLOW-0178 | 材料 | Screen the attached anisotropic dielectric response exports under the stated single-frequency loss criter… |
| FLOW-0181 | 材料 | Choose the best of the listed energy-axis shifts for the controlled observation relative to the authentic… |
| FLOW-0182 | 材料 | Compare a defined shape descriptor of the two genuine computed Fe K-XANES spectra. For each spectrum defi… |
| FLOW-0185 | 材料 | Compare the two supplied full-zone DFPT phonon density-of-states snapshots for harmonic constant-volume h… |
| FLOW-0186 | 材料 | Audit acoustic/optical separation using the authentic GaAs path branches and independently sampled full-z… |
| FLOW-0187 | 材料 | Decide whether replacing the site-dependent mass model by one mean mass is accurate enough for the HIGHES… |
| FLOW-0188 | 材料 | Determine which element supplies more integrated site-projected vibrational weight between the first posi… |
| FLOW-0190 | 材料 | Audit the two controlled periodic snapshots against the reference using the supplied fixed central-site a… |
| FLOW-0191 | 材料 | Identify the candidate whose geometric periodic components are all two-dimensional under the declared 1.8… |
| FLOW-0192 | 材料 | Reconcile the z-polarization branch of the published ordered BaTiO3 deformationpath. Allcells use the sam… |
| FLOW-0193 | 材料 | For the two published numerical spin-DOS curves,quantify how a Fermi-level indicator differs from an inte… |
| FLOW-0195 | 材料 | Audit whether the ordered migrationpath can be summarized by one moving atom. Preserve the source same-in… |
| FLOW-0198 | 材料 | A discharge report subtracts two whole-electrode average potentials and multiplies by the smaller nominal… |
| FLOW-0199 | 材料 | Determine the smallest listed energy cutoff for which the discrete spectral-moment coverage indicator rea… |
| FLOW-0200 | 材料 | Audit the supplied non-spin-polarized eigenvalue paths before treating either candidate as gapped in this… |
| FLOW-0202 | 材料 | Compare the geometric volume excess of the two published boundary snapshots, using the supplied bulk stru… |
| FLOW-0204 | 材料 | A phonon report would remove a small translational-sum-rule error and then certify the sampled model stab… |
| FLOW-0206 | 材料 | Identify which listed reflection is least accurately represented by an isotropic approximation to atom 0'… |
| FLOW-0207 | 材料 | Audit the insulating-crystal Born-charge translational sum rule before using the supplied tensors as a li… |
| FLOW-0208 | 材料 | Prioritize the two relaxed oxide geometries for local ionic-model review under the supplied cation and ox… |
| FLOW-0209 | 材料 | Determine what the supplied 300 K marginal atomic-motion tensors imply for the linearized parallel relati… |
| FLOW-0210 | 材料 | Test whether ONE magnitude of the long-range two-sublattice order parameter can explain both odd-reflecti… |
| FLOW-0211 | 材料 | Assess the directional effective-mass anisotropy of the supplied local X-valley electronic band and wheth… |
| FLOW-0212 | 材料 | Estimate the Curie-Weiss parameters only after qualifying finite-field linear response in the controlled … |
| FLOW-0213 | 材料 | Evaluate whether the positive isotropic Poisson ratio reported for this computed phase rules out lateral … |
| FLOW-0214 | 材料 | Quantify path dependence of the reported xenon inventory on the same Vycor specimen at the study target s… |
| FLOW-0215 | 材料 | Determine how allowing the supplied surface reconstructions changes the restricted equilibrium shape of t… |
| FLOW-0216 | 材料 | Screen the two candidate adsorption pressures for the attached example framework using the declared finit… |
| FLOW-0217 | 材料 | Assess the specified Fe3O4 candidate against the complete SUPPLIED compatible Fe-O cohort. Work strictly … |
| FLOW-0218 | 材料 | Plan a GEOMETRY-ONLY follow-up to the supplied single collinear DFT state. Identify source sites whose ab… |
| FLOW-0220 | 材料 | Assess whether the ambient higher-energy nominal phase becomes favored under hydrostatic pressure within … |
| FLOW-0221 | 材料 | Locate any acoustic axis strictly inside the supplied basal-plane propagation sector of this computed tet… |
| FLOW-0223 | 材料 | Select a loading system for stable crack-growth characterization in the supplied controlled linear-elasti… |
| FLOW-0224 | 材料 | Audit the supplied original crystal as an input to a proposed automatic guest-deletion preprocessing step… |
| FLOW-0225 | 材料 | Determine whether fine layering can restore ideal macroscopic compatibility with the undeformed reference… |
| FLOW-0226 | 材料 | Reanalyze the supplied official silicon quasi-harmonic example under the explicitly stated finite-volume … |
| FLOW-0227 | 材料 | Determine which listed slip system first activates as uniaxial tension increases in the attached crystal … |
| FLOW-0230 | 生物／生态 | A plant–pollinator network report treats its degree margins as sufficient to determine nested structure a… |
| FLOW-0232 | 机器学习／数理 | Audit an inverse temperature-calibration report that replaces coefficient uncertainty by a symmetric erro… |
| FLOW-0233 | 材料 | A defect report evaluates formation energies at an arbitrarily chosen Fermi level and then assumes equal … |
| FLOW-0234 | 材料 | A site-occupancy report takes positive square roots of two coherent intensities and interprets the result… |
| FLOW-0235 | 机器学习／数理 | Choose a scientifically defensible geometry for comparing the attached positive oxide compositions when t… |
| FLOW-0237 | 材料 | A material shortlist has modulus and density calibrated by the same uncertain coordinate. Select a robust… |
| FLOW-0238 | 机器学习／数理 | Audit a laboratory instrument reliability report when two different terminal failure modes compete. From … |
| FLOW-0239 | 生物／生态 | A quantitative-proteomics methods study needs to decide which parent-polypeptide amounts are determined b… |
| FLOW-0240 | 生物／生态 | A comparative-gene handoff uses species labels as though every between-species pair were orthologous. Rec… |
| FLOW-0242 | 生物／生态 | An ensemble-distance report inverts one normalized transfer efficiency and calls the result the structure… |
| FLOW-0244 | 生物／生态 | A partial proteolysis report collapses identical peptide sequences and normalizes two measured signals as… |
| FLOW-0245 | 生物／生态 | A sequencing handoff interprets equal-library compositional changes as absolute per-cell regulation after… |
| FLOW-0247 | 材料 | Curate the thermodynamic charge-transition diagram of the attached defect model. Construct the global for… |
| FLOW-0248 | 机器学习／数理 | Audit whether the attached exact population covariance identifies the effect of setting X on Y under the … |
| FLOW-0249 | 生物／生态 | A peptide-mixture report defines its neutral-charge pH by averaging theoretical pIs. Use the declared com… |
| FLOW-0250 | 生物／生态 | A cross-species interaction summary conserves each edge independently and concludes that one ortholog map… |
| FLOW-0251 | 生物／生态 | A curator must release an auditable teaching protein-record panel under the attached identity/metadata po… |
| FLOW-0252 | 生物／生态 | Assess a proposed retrospective interpretation that an upregulated set is overrepresented in the six supp… |
| FLOW-0253 | 生物／生态 | A proposed reanalysis would interpret a whole-community/whole-environment distance association as ecologi… |
| FLOW-0254 | 生物／生态 | Audit a controlled crystallographic-summary scenario in which coordinate atom-inventory mass would be sub… |
| FLOW-0255 | 生物／生态 | Audit a proposed mean-volume report from archived tree measurements, comparing the two declared backtrans… |
| FLOW-0256 | 生物／生态 | Audit a controlled preprocessing scenario in which the full genomic span of an annotated chloroplast CDS … |
| FLOW-0257 | 生物／生态 | A researcher needs usable nucleotide-composition covariates for the complete historical marker panel and … |
| FLOW-0258 | 生物／生态 | A proposed chloroplast annotation index would use gene-name counts, CDS-feature counts and distinct encod… |
| FLOW-0259 | 生物／生态 | A structural-data researcher needs a coarse-grained fluctuation model whose soft internal mode is not con… |
| FLOW-0260 | 生物／生态 | A structural-data archive needs one submitted conformer to represent its complete NMR ensemble in a downs… |
| FLOW-0262 | 生物／生态 | An ecological-methods analyst must separate site state from imperfect observation in the attached histori… |
| FLOW-0263 | 生物／生态 | Audit a proposed protein-analysis summary that would use one A280 coefficient without documenting its cys… |
| FLOW-0264 | 生物／生态 | Check whether the supplied deposited disulfide endpoint annotations agree with the actual sulfur geometry… |
| FLOW-0265 | 生物／生态 | A comparative-trait study is planning which uncertainty calculation it can justify from a supplied refere… |
| FLOW-0267 | 生物／生态 | A functional-annotation index needs a concise overview of a predeclared yeast gene panel without counting… |
| FLOW-0268 | 材料 | An open-reservoir phase screen proposes using the most B-rich allowed target phase as a dilute-defect ref… |
| FLOW-0269 | 化学 | A two-site sorbent is assigned a single preferred component from its dilute-limit affinity and a ratio of… |
| FLOW-0271 | 机器学习／数理 | Determine whether a regularly sampled two-component instrument transient identifies its continuous-time l… |
| FLOW-0272 | 生物／生态 | Evaluate whether the two supplied coordinate files support a comparison of the declared full-reference pr… |
| FLOW-0273 | 材料 | A thermal-laminate summary averages the two free expansions to predict a flat,stress-free strip. Reconstr… |
| FLOW-0274 | 材料 | Infer the attached collinear magnetic Hamiltonian and audit its predictive scope. Reconcile edge identiti… |
| FLOW-0275 | 生物／生态 | Audit how the observation-error assumptions affect latent occupancy inference in the attached archived re… |
| FLOW-0278 | 机器学习／数理 | A calibration team must release a response envelope and select a conservative detector setting without tr… |
| FLOW-0281 | 生物／生态 | A comparative-trait report would average descendant observations and then treat its estimated root trait … |
| FLOW-0282 | 生物／生态 | An annotation handoff would copy two reference residue labels through the first best alignment returned b… |
| FLOW-0283 | 机器学习／数理 | A crossover report reads the period2A-minus-Bcontrast as the current treatment effect and says a rank-def… |
| FLOW-0284 | 机器学习／数理 | An instrument comparison reports the regression of a response on noisy predictors as if it were a relatio… |
| FLOW-0285 | 生物／生态 | An archived-count analysis is being handed to a collaborator. Audit whether the attached pasilla-derived … |
| FLOW-0287 | 生物／生态 | A seasonal population report averages two stage projections and assumes every initial population eventual… |
| FLOW-0288 | 生物／生态 | A stage-demography report would identify the strongest local growth leverage by choosing the largest fecu… |
| FLOW-0289 | 生物／生态 | Two half-occupancy titrations at different nominal protein totals are treated as direct Kdreadings. Recon… |
| FLOW-0290 | 生物／生态 | Prepare an auditable evidence handoff for the precisely scoped functional claim in the frozen yeast GO an… |
| FLOW-0291 | 生物／生态 | A historical bulk-count study needs a cautious reporting panel under the attached association-and-point-e… |
| FLOW-0292 | 生物／生态 | A collaborator claims the nominated historical count contrast demonstrates a positive effect above the de… |
| FLOW-0299 | 生物／生态 | An ecologist is preparing a two-axis descriptive plot of the archived site communities under the explicit… |
| FLOW-0300 | 生物／生态 | Audit a proposed identification of four exploratory vegetation groups with four management categories in … |
| FLOW-0301 | 生物／生态 | A plant-physiology archive asks whether a treatment-associated change in CO2 responsiveness looks the sam… |
| FLOW-0302 | 生物／生态 | Quantify sampling uncertainty for a fixed-composition mean uptake target in the historical CO2 plant pane… |
| FLOW-0304 | 生物／生态 | Assess which scientific comparisons are identifiable in the archived six-block pea factorial example when… |
| FLOW-0305 | 生物／生态 | Audit a proposed report that would highlight one favorable plant dry-weight comparison after examining bo… |
| FLOW-0309 | 生物／生态 | A structural archive needs an orientation-independent size-and-shape summary of its explicitly stated coo… |
| FLOW-0311 | 生物／生态 | A forest-understorey report related plant cover to soil chemistry after two tables had been exported in d… |
| FLOW-0312 | 生物／生态 | Audit a proposed forest-community report that would use stem-count dissimilarity to answer a composition-… |
| FLOW-0313 | 生物／生态 | Audit a proposed soil-community report that would treat distinct sample locations as sufficient evidence … |
| FLOW-0314 | 生物／生态 | Audit a proposed growth summary that would pool repeated weighings and treat the day21 comparison as full… |
| FLOW-0315 | 生物／生态 | A longitudinal growth archive needs a cumulative, baseline-referenced summary over a common observation w… |
| FLOW-0318 | 生物／生态 | Audit a proposed forest comparison that would rank plots by observed species totals without accounting fo… |
| FLOW-0319 | 生物／生态 | Audit a proposed ordinal-cover survey summary that would compare pooled species lists across strata with … |
| FLOW-0320 | 化学 | A charge-state report substitutes a single neutral structure for an entire buffered ampholyte ensemble. R… |
| FLOW-0321 | 化学 | An oxidation mass balance reports one organic Faradaic efficiency from consumed ethanol,CO2and total char… |
| FLOW-0322 | 生物／生态 | A population-growth report treats an offspring mean above one as guaranteed persistence and assumes equal… |
| FLOW-0323 | 生物／生态 | A finite protein-identification assay is being reduced to a cheaper mass-channel panel. Derive the actual… |
| FLOW-0324 | 生物／生态 | Assess whether the sign of the supplied morphology association is robust to its declared ancestry-correla… |
| FLOW-0325 | 生物／生态 | Select archived panels for digitization under the attached controlled ancestry-coverage policy. Choose at… |
| FLOW-0326 | 生物／生态 | Audit whether a local coordinate-variability conclusion is robust to the declared alignment convention in… |
| FLOW-0327 | 生物／生态 | Prepare a contact-preserving two-module handoff for the four explicitly supplied deposited protein chains… |
| FLOW-0328 | 化学 | A regioselectivity summary ranks intrinsic reactivity directly from class peak fractions,ignoring that so… |
| FLOW-0329 | 生物／生态 | Assess whether the selected four-chain geometry difference between two deposited hemoglobin structures is… |
| FLOW-0330 | 生物／生态 | A stage-demography report uses a dominant projection factor below one to assert that every early census m… |
| FLOW-0331 | 生物／生态 | A two-species competition report finds positive equilibrium densities and therefore promises stable coexi… |
| FLOW-0334 | 生物／生态 | A flux-balance report treats a single growth-optimal solver witness as the identified metabolic route spl… |
| FLOW-0335 | 生物／生态 | A steady-state network exports ATPfrom a closed substrate cycle and calls the linear-program optimum a fe… |
| FLOW-0338 | 生物／生态 | A diversity report promotes a single observed-richness ranking as an order-independent conclusion about c… |
| FLOW-0344 | 化学 | A two-exponential NMRdecay fit is interpreted as a unique exchange rate and two intrinsic relaxation time… |
| FLOW-0349 | 生物／生态 | A two-capture survey reports one population size while its scientific protocol permits dependent capture.… |
| FLOW-0351 | 化学 | A solvatochromic analysis reports the square root of a calibrated Stokes slope as the absolute excited-st… |
| FLOW-0352 | 化学 | A composite kinetic isotope effect is assigned to a single pathway and averaged arithmetically over route… |
| FLOW-0353 | 生物／生态 | A mark-history summary calls disappearance from an observation region death and reports one true-survival… |
| FLOW-0358 | 生物／生态 | A coarse-grained structural report uses marginal node fluctuations as though they directly measured pair … |
| FLOW-0366 | 生物／生态 | A two-resource competition analysis labels a positive coexistence solution stable because both resource-b… |
| FLOW-0367 | 化学 | Two kinetic probes are used to characterize a reactor with a possible bypass,but the report replaces its … |
| FLOW-0373 | 化学 | A two-spin spectral assignment uses independent first-order doublets despite a coupling comparable to the… |
| FLOW-0376 | 机器学习／数理 | A proposed longitudinal reanalysis needs to distinguish precision of the shared mean change from heteroge… |
| FLOW-0377 | 机器学习／数理 | Using archived morphology measurements, select a measurement protocol under the supplied acquisition-acco… |
| FLOW-0378 | 机器学习／数理 | A morphology calibration fitted on sex-identified M/F archive records is proposed for I-coded records. Qu… |
| FLOW-0379 | 机器学习／数理 | Audit an inference report for the attached controlled bench-unit study. Use the instrument records and in… |
| FLOW-0380 | 机器学习／数理 | Audit a proposed wind-tunnel prediction report that would treat a random-row holdout as validation at uns… |
| FLOW-0381 | 机器学习／数理 | A digit-archive researcher needs the class mixture of an unlabelled batch while reusing an existing recog… |
| FLOW-0382 | 机器学习／数理 | An atmospheric-data analyst must choose a compact historical trend representation for a genuinely future … |
| FLOW-0383 | 机器学习／数理 | Prepare a conditional performance profile for a fixed historical census classifier on the attached heldou… |
| FLOW-0384 | 机器学习／数理 | A researcher needs a compact association display for an archived paired father–son occupational table. Qu… |
| FLOW-0385 | 机器学习／数理 | A model-comparison study needs uncertainty for the heldout loss improvement of one frozen fuel-consumptio… |
| FLOW-0387 | 机器学习／数理 | A proposed reanalysis of archived data would present a fitted model's point RMSE as a calibrated uncertai… |
| FLOW-0388 | 机器学习／数理 | A diagnostic-model study is deciding which additional binary measurement would reduce uncertainty about i… |
| FLOW-0389 | 机器学习／数理 | A methodological comparison needs performance evidence for its complete data-adaptive hull predictor,incl… |
| FLOW-0391 | 化学 | A powder-averaged diffusion measurement reports nonzero kurtosis as evidence of non-Gaussian motion withi… |
| FLOW-0395 | 生物／生态 | A niche-width summary ranks habitats by the product of their two marginal widths while ignoring covarianc… |
| FLOW-0396 | 化学 | A reversible-exchange report reads the measured decay constant of enantiomeric excess as the rate on a si… |
| FLOW-0398 | 生物／生态 | A community energy budget applies an individual body-mass allometry directly to total biomass. Use the ex… |
| FLOW-0399 | 机器学习／数理 | A chemical-analysis archive must select an auditable predictor for the stated prediction time,not whichev… |
| FLOW-0400 | 机器学习／数理 | Reconstruct a heldout alcohol-column prediction analysis under the attached Wine data-availability protoc… |
| FLOW-0401 | 生物／生态 | A filament-orientation report calls a zero mean of its arbitrarily signed axis vectors isotropic and sele… |
| FLOW-0402 | 生物／生态 | A coordinate-ensemble report multiplies two alternate-position occupancies to report a contact probabilit… |
| FLOW-0403 | 机器学习／数理 | A researcher must set a reporting decision cutoff for an archived Iris morphology classifier. Use the sup… |
| FLOW-0404 | 化学 | A binding report interprets a shallow Hill slope as proof of negative cooperativity and uses that slope a… |
| FLOW-0410 | 机器学习／数理 | Evaluate the archived Longley measurements under the supplied proposed forecast-origin, embargo and stand… |
| FLOW-0411 | 机器学习／数理 | A particle-based scientific simulation resets every child weight to the same value and reports that its f… |
| FLOW-0415 | 机器学习／数理 | A chemical archive needs a compact representation that preserves training variation and reconstructs genu… |
| FLOW-0423 | 机器学习／数理 | Audit a proposed extension of a reliability test using only the inspection counts and surviving units in … |
| FLOW-0427 | 机器学习／数理 | Two analysts report power-law calibrations of the same lamp measurements using different error scales. Re… |
| FLOW-0431 | 机器学习／数理 | Audit a proposed optical summary that would conflate fitted total line-shape area and measurement-grid-su… |
| FLOW-0432 | 机器学习／数理 | Audit a controlled reporting-table scenario that confuses fitted-mean uncertainty with uncertainty for on… |
| FLOW-0433 | 机器学习／数理 | An ultrasonic calibration reviewer asks how much its requested prediction depends on the two declared res… |
| FLOW-0434 | 机器学习／数理 | An image-based permeability predictor must be assessed without sharing a reference-outcome group between … |
| FLOW-0439 | 机器学习／数理 | Audit a proposed reanalysis that would report the best validation result as untouched final assessment an… |
| FLOW-0440 | 机器学习／数理 | A proposed timber-volume summary would give every sampled tree equal weight despite a disproportionate sa… |
| FLOW-0441 | 机器学习／数理 | A predictor-combination study must decide whether two frozen exports can be combined usefully without tun… |
| FLOW-0442 | 机器学习／数理 | An encouragement-study analysis proposes interpreting an exact-exclusion instrument estimate as a uniquel… |
| FLOW-0443 | 机器学习／数理 | A prediction-reporting proposal pools calibration errors from two prespecified scientific instrument grou… |
| FLOW-0444 | 机器学习／数理 | Plan one additional relative clock-calibration measurement for the supplied network. Each pair measures t… |
| FLOW-0445 | 机器学习／数理 | Compare the predictive uncertainty of two prospective equal-dry-mass pooled soil-composite assays under t… |
| FLOW-0446 | 机器学习／数理 | Choose a two-readout follow-up program for the archived adsorption calibration under the attached prospec… |
| FLOW-0447 | 机器学习／数理 | Audit an illustrative measurement-agreement report using the attached 17-subject published demonstration.… |
| FLOW-0448 | 机器学习／数理 | Choose among the attached industrial sensor classifiers when the joint operating-environment mixture is u… |
| FLOW-0449 | 机器学习／数理 | Audit relative classifier performance when the available labels are weak. The attachment supplies the exa… |
| FLOW-0450 | 机器学习／数理 | Determine what a randomized process encouragement identifies when actual setting uptake is imperfect. The… |
| FLOW-0451 | 机器学习／数理 | Audit and select a two-stage binary process-qualification design from the attached candidates. Each plan … |
| FLOW-0452 | 生物／生态 | Assess a prespecified global arm-effect claim in the attached blocked plant-readout study. Pair records b… |
| FLOW-0453 | 化学 | Audit whether a two-level digital observation preserves an exact Markov description of the attached four-… |
| FLOW-0454 | 机器学习／数理 | Calibrate the structural relationship between two fallible instrument coordinates using the attached inde… |
| FLOW-0455 | 化学 | Four fully specified stereochemical records are counted as four compounds,and a zero-rotation mixture is … |
| FLOW-0456 | 化学 | A nominal-mass formula screen uses carbon count alone and ignores heteroatom and hydrogen isotope contrib… |
| FLOW-0460 | 化学 | A molecular-curation report collapses every graph with cycle rank two into one ring architecture and trea… |
| FLOW-0461 | 化学 | An analytical-standard handoff discards every component except the largest connected fragment before assi… |
| FLOW-0463 | 化学 | A Raman assignment treats equal powder activity and depolarization as proof that two candidate tensors di… |
| FLOW-0464 | 化学 | A mass-spectrum interpretation reads a binomial total-label histogram as proof of independent labeling at… |
| FLOW-0465 | 机器学习／数理 | A two-compartment measurement study proposes recovering an absolute inventory by adding more time samples… |
| FLOW-0466 | 机器学习／数理 | Choose an operating policy for the attached defect detector under a conditional-sensitivity requirement, … |
| FLOW-0467 | 机器学习／数理 | A stratified reporting example claims that any gap between the common within-stratum odds ratio and the p… |
| FLOW-0468 | 机器学习／数理 | A calibration plan proposes maximizing overall information as a universal way to measure curvature precis… |
| FLOW-0469 | 材料 | A NaCl density interpretation assigns the entire density decrease to regular-site vacancies and concludes… |
| FLOW-0471 | 机器学习／数理 | A two-channel instrument must report a region for the complete next object. Its draft independently calib… |
| FLOW-0472 | 机器学习／数理 | An archive uses an augmented inverse-response estimator to recover a mean from selective recording. Audit… |
| FLOW-0473 | 机器学习／数理 | A historical-count report treats the absence of a strong phenotype association as proof of exact independ… |
| FLOW-0474 | 机器学习／数理 | Audit a proposed defect-monitoring error-control claim when the same accumulating observations are tested… |
| FLOW-0475 | 机器学习／数理 | Assess which scientific quantities are identifiable from the supplied controlled iron-oxide inventory. Ca… |
| FLOW-0476 | 机器学习／数理 | Two multi-channel instruments are proposed to share their strongest variation in the direction with large… |
| FLOW-0477 | 机器学习／数理 | A station-grouping report treats the second eigenvector of the attached coupling graph as one uniquely de… |
| FLOW-0478 | 机器学习／数理 | A measurement archive would estimate the latent mean using only values above its reporting limit, or inse… |
| FLOW-0479 | 机器学习／数理 | A time-resolved inventory report treats cyclic two-bin averages as four independent point observations. A… |
| FLOW-0480 | 机器学习／数理 | A screening report selects its most favorable signed Gaussian observation and reuses an ordinary one-test… |
| FLOW-0481 | 机器学习／数理 | An incomplete-data report averages four properly imputed estimates and divides their complete-data uncert… |
| FLOW-0482 | 机器学习／数理 | Two pairwise correlation exports are to be combined into a three-variable scientific calibration. A colla… |
| FLOW-0483 | 机器学习／数理 | A calibration report measures model complexity by the two nominal coefficient slots and treats the smalle… |
| FLOW-0484 | 机器学习／数理 | An instrument report would use its largest observed-variance principal direction as the strongest physica… |
| FLOW-0485 | 机器学习／数理 | A simulation plan proposes a zero-variance proposal proportional to each signed target contribution. Desi… |
| FLOW-0486 | 材料 | Two finite shears are reported as interchangeable because each has determinant one. Audit the actual sequ… |
| FLOW-0487 | 材料 | A coarse transport report averages two state diffusivities and calls that the long-time particle diffusiv… |
| FLOW-0488 | 化学 | A gas-association calculation carries the same equilibrium composition and heat between a constant-pressu… |
| FLOW-0489 | 机器学习／数理 | A nonlinear scientific surrogate substitutes the mean measured input coordinate into its Gaussian-process… |
| FLOW-0490 | 机器学习／数理 | A response-calibration report selects an interpolating polynomial because its fitted error is zero and re… |
| FLOW-0491 | 机器学习／数理 | A clustered study randomly assigns an equal number of clusters to each arm and assumes that the differenc… |
| FLOW-0492 | 机器学习／数理 | A model-comparison report treats perfect training fit as sufficient evidence for one scientific pattern a… |
| FLOW-0493 | 机器学习／数理 | An ecological site map proposes interpreting shortest-route distances as an exact Cartesian ordination be… |
| FLOW-0494 | 机器学习／数理 | An adaptively stopped Bernoulli measurement report calls its ordinary sample mean unbiased because each i… |
| FLOW-0495 | 机器学习／数理 | A released-table report would generalize an association from retained records to its complete census popu… |
| FLOW-0496 | 机器学习／数理 | An instrument log proposes locating a sustained level shift at the largest adjacent jump. Under the attac… |
| FLOW-0497 | 机器学习／数理 | A scientific-instrument scheduler regards two protocols as equivalent because their mean service time and… |
| FLOW-0498 | 机器学习／数理 | A model comparison would transport its equal-stratum risk ranking to a target population whose compositio… |
| FLOW-0499 | 机器学习／数理 | Combine the attached three voltage reports under their known shared-calibration error model. Find the min… |
| FLOW-0500 | 材料 | A finite-alloy report would collapse rotationally equivalent occupancy patterns to two equally weighted s… |
