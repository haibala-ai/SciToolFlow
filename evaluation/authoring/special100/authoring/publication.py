"""Individually reviewed public wording: scientific targets, not execution plans.

These descriptions retain the specified computational experiment and answer
contract while removing tool identifiers, procedural ordering and conclusions.
"""
from copy import deepcopy

TEXT={
8:('Compound-space neighborhoods under two fingerprint representations',
'''The supplied molecular records have fixed order: reference benzene, then candidates a,b,c. Graphs, tautomers and stereo are preserved. The two representations are connectivity Morgan (radius2,2048bits,chirality=false,features=false) and default MACCS, both with Tanimoto similarity. Report canonical_smiles and the full morgan_matrix and maccs_matrix. neighbor_k_a,b,c means similarity to record0>=0.30 for representation k. Each representation also defines an undirected compound graph: off-diagonal similarities are edge weights and the diagonal is zero. Its unnormalized Laplacian is L=degree-adjacency; spectrum_k is its ascending spectrum, heat_k=exp(-L)[1,0,0,0], and mass_k is the state sum. isolated_candidate_k_c concerns zero off-diagonal degree of c within1e-12. The graph is an informatics model, not molecular kinetics or an identity assertion.'''),
40:('Transient responses on a weighted sensor network',
'''A sensor network has the supplied symmetric adjacency and initial state. The physical model is unnormalized graph diffusion, L=degree-adjacency, with edge weights in inverse-time units. The candidate times a,b,c are0.2,0.8,1.6 in the matching time unit. Required quantities are the ascending spectrum of L (spectrum), each state exp(-tL)initial (state_a,b,c), and its squared Euclidean discrepancy from target (error_a,b,c). selected contains every minimum-discrepancy time ID. All candidates use the same network and initial condition.'''),
55:('Hydrogen representations, isotope inventory and charge conservation',
'''Controls a,b,c are supplied as molecular graphs. added_k denotes the standard RDKit explicit-hydrogen expansion of graph k; removed_k is the isotope-preserving standard RDKit removable-hydrogen reduction of that expanded graph. For [original,added,removed], counts_k contains explicit as_parsed/all atom counts, masses_k contains average molar masses in g/mol, and charges_k contains total formal charges. mass_conserved_k uses max(masses_k)-min(masses_k)<=1e-6. Report all representations and quantities for every control. Isotope-labelled hydrogen and formal charge retain their supplied identity.'''),
59:('Molecular serialization fidelity under two representation standards',
'''Three supplied graphs retain all fragments, their tautomer representation and stereo. The experimental conditions are a SELFIES round trip and a standard-InChI round trip. For each k=a,b,c report selfies_k, its SELFIES symbol count token_count_k, decoded_k, inchi_k and recovered_inchi_k. canonical_k,canonical_selfies_k,canonical_inchi_k are canonical isomeric SMILES of the original and the two recovered graphs under keep_all/preserve/keep_stereo=true. self_same_k and inchi_same_k are exact canonical-identity comparisons with the original. masses_k is the [original,SELFIES-recovered,InChI-recovered] average-molar-mass vector in g/mol. Changed recovered representations remain part of the report; graph fidelity and mass agreement are separate questions.'''),
60:('Element-constrained blend optimization and inventory audit',
'''Three graph-defined stocks a,b,c are theoretical elemental inventory controls. Their reported formula_k, average mass_k(g/mol), and formula-based CNO_k mass fractions in[C,N,O] describe different declared readouts. A blend totals100g, each stock contributes between0and70g, oxygen mass is at least15g and nitrogen mass at most12g. The objective is maximum carbon mass under these constraints. allocation_g is a feasible optimum in[a,b,c]order; carbon_g,nitrogen_g,oxygen_g,total_g describe that allocation. An independent elemental matrix-balance witness for the reported allocation is required. This is a continuous inventory model, not a reaction, yield prediction or preparation instruction.'''),
63:('Phase proportions and bulk density of an additive-volume mixture',
'''Three crystalline controls a=NaCl,b=KCl,c=NaF have supplied geometries and stated chemical formulas. Report density_k(g/cm^3),formula_mass_k(u) and mass_fractions_k in[Na,K,F,Cl]order. The mixture's observed Na,K,F mass fractions are supplied. Under conservation of element masses and additive phase volumes, determine phase mass_weights, phase volume_weights and mixture_density, all with phase order[a,b,c]. elemental_check is an independent prediction of all four mixture elemental mass fractions for the inferred amounts. Each phase retains its supplied density; no reaction or new single phase is assumed.'''),
71:('Pressure and surface-state dependence of a molecular reservoir model',
'''Three hypothetical water-binding surface states have supplied electronic adsorption energies delta_e_eV per water relative to the gas electronic energy. The completed298.15K source defines water's translational,rotational,vibrational H_parts(kcal/mol) and S_parts(cal/(mol K)); printed vibrational enthalpy includes zero point. The reservoir model is mu0_thermal=H_eV-T*S_eV_per_K. Use1kcal=4184J,1eV/molecule=96485.33212331002J/mol,and k_B=8.617333262145e-5eV/K. At each supplied pressure ratio p/p0,delta_g=delta_e-mu0_thermal-k_B*T*ln(p/p0); adsorbed-state thermal corrections are neglected. Report the source components,converted H_eV and S_eV_per_K,mu0_thermal,and delta_g with pressure rows and state columns. favorable_i_j means delta_g[i][j]<0,with0-based indices. The exercise uses an existing computed record and a stipulated finite model.'''),
72:('Calibrated-band mixture inference and identifiability audit',
'''The completed water calculation supplies three ordered vibrational frequencies and IR intensities. Each mode has an independent five-point instrument calibration in calibration_x/calibration_y. Its response family is gaussian_peak(height,center,width),with initial[printed intensity,printed frequency,15],height bounds[0,10000],center bounds[printed frequency-10,printed frequency+10],width bounds[1,100],linear loss,max_evaluations2000. parameters_a,b,c describe these three calibrated responses. The measurement model has ordered columns[calibrated band a,calibrated band b,calibrated band c,1,(x-2500)/1000] on measurement_x. Report that model matrix's singular_values,ordinary-least-squares coefficients for measurement_y,and independently verified predicted and rmse. Calibration observations and mixture observations have distinct roles; mode order remains fixed.'''),
76:('Distance geometry of community observations',
'''Four communities share five ordered taxon columns. The three dissimilarity conventions are raw-count Bray-Curtis,binary-presence Jaccard,and Euclidean distance between square-root relative-abundance vectors(Hellinger). Report D_bray,D_jaccard,D_hellinger in community order. For each convention k,gram_k is the centered Gram matrix of classical metric multidimensional scaling with uniform object weights,and spectrum_k is its ascending spectrum. euclidean_k means the smallest eigenvalue is at least-1e-8. The matrices must retain their actual values,including numerical or substantive negative eigenvalues; no PSD repair is part of this experiment. Communities are objects and taxa are features.'''),
82:('Diversity partitioning under two target-population definitions',
'''Three stands have four ordered taxa and unequal census totals. Report local_shannon(natural logarithms) and local_effective=exp(local_shannon) in stand order. The target populations are equal_stand(weights1/3each) and individual(weights proportional to stand census totals). For target k,pooled_proportions_k is the weighted mixture of stand-level relative abundances; H_alpha_k is weighted local Shannon entropy and H_gamma_k is Shannon entropy of that pooled mixture. effective_alpha_k,effective_gamma_k are their exponentials; effective_beta_k=exp(H_gamma_k-H_alpha_k). arithmetic_local_effective_k is the weighted arithmetic mean of local effective diversities. Every reported quantity retains its target-population identity.'''),
85:('Pulse responses and norm amplification in ecological linear models',
'''The supplied matrices J define three stipulated linearized ecological models. At times0.5and2, response_short_k and response_long_k are exp(tJ_k) times the supplied pulse. gain_short_k and gain_long_k are the worst-case Euclidean response gains at those times,the spectral norms of exp(tJ_k). symmetric_spectrum_k is the ascending spectrum of(J_k+J_k^T)/2. amplifies_short_k means gain_short_k>1+1e-8. Time uses the inverse-rate unit of these matrices. These finite responses concern controlled linear models,not an inferred real ecosystem or intervention.'''),
88:('Future prediction with cutoff-specific temporal embargoes',
'''Fifteen ordered measurements have times0..14. Cutoffs a,b,c are5,8,11. Training comprises times<=cutoff; test comprises times>cutoff+1; remaining rows are embargoed. Report train_k,test_k,gap_k indices. Each experiment uses population feature means/scales determined solely by its own training rows and ridge regression with alpha1 and an unpenalized intercept. mean_k and scale_k identify that training population; predictions_k and rmse_k refer to its test rows in original order. Future and embargoed rows are excluded from both fitting and preprocessing. The finite experiment does not establish temporal independence.'''),
89:('Residual and solution-size admissibility of truncated inverse models',
'''The supplied A,b define a near-singular inverse problem. The estimators r1,r2,r3 are the rank1,2,3 truncated-SVD minimum-norm solutions using the complete retained singular subspaces of one economy decomposition of A. Required quantities are singular_values,solution_r1..r3,the corresponding predicted_r1..r3=A*solution,and rmse_r1..r3 against b. norm_squared_r is squared Euclidean solution norm. admissible_r requires BOTH RMSE<=0.02 and norm_squared<=9. Singular-vector signs do not define different estimators. All forward predictions require independent numerical witnesses.'''),
90:('Identifiability of contrasts in a rank-deficient model',
'''The supplied A,y define an unweighted linear model with minimum-norm least-squares convention. Numerical right-singular directions are retained when their singular values exceed1e-8. Report singular_values,rank,projector(the orthogonal projector onto that numerical row space),and fitted_y. Contrast rows a,b,c are supplied in C. projection_residual_squared_k is||P*c-c||^2; estimable_k uses a threshold<=1e-16. estimate_k is c dot the minimum-norm least-squares coefficient vector for estimable contrasts,and null otherwise. The requested fitted response and contrast-identifiability evidence must each be supported by actual computations.'''),
91:('Named-positive policies across two held-out cohorts',
'''Training data define a standardized logistic model with C=1,max_iterations300. The positive scientific label is affected and the negative label healthy. Report fitted classes. For held-out cohorts a,b,positive_probabilities_k refers to the positive label and brier_k to its Brier score. The declared policies low/high have thresholds0.4/0.7,with positive classification at probability>=threshold. Report labels_k_low/high and total_cost_k_low/high under false-positive cost3 and false-negative cost8. Both cohorts and all declared policies belong to the report; test labels are excluded from model fitting,calibration and policy selection.'''),
92:('Common-matrix and direct-solve consistency across several forcings',
'''A is a supplied symmetric positive-definite control; columns of B are three right-hand sides. The experiment compares a common inverse-based solution with separately computed direct linear-system solutions. Report spectrum of A,batched_solutions=A^-1*B,direct_a,b,c,and independently verified forward_B=A*batched_solutions. residual_squared_k is the squared Euclidean forward residual for column k. agreement_k compares its direct solution with the corresponding batched column within1e-6. RHS identity and order remain fixed; these checks do not imply an unconditional forward-error guarantee.'''),
95:('Analytic response models and numerical tabulation diagnostics',
'''Each sensor a,b,c has a gaussian_peak(height,center,width) calibration on x,y,with initial[2,3,1],bounds height[0,10],center[0,6],width[0.2,3],linear loss,max_evaluations2000. Report parameters_k and grid_prediction_k at the original integer knots. gradient_k follows numpy.gradient with edge_order1 on those fitted knot values. hermite_k is the cubic Hermite approximation at the supplied half-integer queries using those knot values and gradients; direct_k is the fitted analytic response at the same queries. interpolation_rmse_k compares the two query readouts. closure_error_k is the trapezoidal integral of the estimated knot gradient minus the fitted endpoint response difference. These quantities characterize numerical tabulation,not experimental confidence intervals.'''),
97:('Density partition quality and retained-sample coverage',
'''Euclidean DBSCAN models a,b,c have eps0.12,0.35,10 and min_samples2 on the same supplied rows. Report labels_k(numeric-1 means noise),cluster_count_k and retained_fraction_k=(n-noise_count)/n. silhouette_k is Euclidean silhouette on nonnoise observations when there are at least2 nonnoise clusters,and null otherwise. raw_best contains all maximum-silhouette model IDs with defined quality; coverage_best applies the additional retained_fraction>=0.8 requirement. An empty eligible set has an empty ID list. Nonnoise label renaming is equivalent only when memberships and noise positions are preserved.'''),
98:('Population forecasts at several horizons and stationary balance',
'''P is a supplied row-stochastic transition matrix. Report matrix powers P2,P4,P8,P16. For each initial ROW distribution a,b,c,dist4_k and dist16_k are its horizon4and16 distributions,and l1_to_stationary_k is its horizon16 L1 distance from the stationary distribution. Report stationary and stationary_check=stationary^T*P expressed as a row vector. The stationary distribution is determined by nonnegativity,total mass1 and stationarity under P,and requires an independent linear-system balance witness. These finite-horizon comparisons do not prove a mixing-time bound.'''),
100:('Smoothing and conservation under two weighting conventions',
'''Three response signals are columns on a five-node graph and a nonuniform physical grid x. The graph model has unnormalized L=degree-adjacency and heat operator H=exp(-0.4L). smoothed is H applied to all signal columns in supplied order. For k=a,b,c report raw_sum,smoothed_sum,raw_integral,smoothed_integral and gradient of the smoothed signal. Integrals are trapezoidal on x; gradients follow numpy.gradient with edge_order1. sum_preserved_k uses absolute sum difference<=1e-8. The discrete graph model and physical-grid quadrature are separate measurement conventions; neither is asserted to be a fitted PDE.''')}

TEXT[99]=('Joint calibration bounds and independent geometric certificates',
'''Unknown signal s and bias b satisfy0<=s,b<=8,9.8<=s+b<=10.2,and13.7<=2s+b<=14.3. Queries a,b,c are s,b,s+b. Report bounds_k=[minimum,maximum] for each query over this single feasible set. An optimization witness and an independently obtained geometric certificate are required for these bounds. Report the feasible polygon vertices in any row order,its area,and vertex_bounds_a,b,c from its query projections. sum_of_marginal_widths is width(s)+width(b),whereas joint_sum_width is width(s+b). These are deterministic tolerance bounds,not confidence intervals. Report both audits without assuming their agreement.''')

TEXT.update({
14:('Repository audit of three labelled crystal records',
"""Three Cs/Cl geometry records carry repository labels primitive_B2,doubled_B2,tetragonal_B2. These labels and any proposed structural relationship are hypotheses to audit,not certified comparison results. Report density_g_cm3,supercell_to_primitive_density_ratio,matches_to_primitive for candidates[doubled_B2,tetragonal_B2],first_powder_angle_deg and space_group_numbers. Matching uses the declared geometric tolerances with primitive reduction allowed and isotropic rescaling disabled. Sample order and all symmetry/powder settings are in inputs.conditions. Powder lines are ideal nonanomalous kinematic readouts without broadening or texture. The supplied structures are synthetic controls,not evidence of stability or an experimental phase assignment."""),
16:('Occupancy and geometric-method eligibility in supplied structure records',
"""The three supplied cation models have repository labels ordered_A,ordered_B,average_disorder. Labels are unverified metadata; actual site occupancies determine method eligibility. Report density_g_cm3,the three <sample_id>_element_amounts_per_cell objects,and disordered_first_site_species with parsed occupancies. ordered_directed_edge_counts concerns records[ordered_A,ordered_B]at4.3A,and ordered_geometric_equivalence concerns that pair under the declared geometric conditions. excluded_from_ordered_geometry_ids identifies models outside the full-occupancy-only local/geometric methods' domain. The actual input cell and occupancy-weighted amounts remain the inventory basis; no missing order is invented. All settings and sample order are supplied. These are static synthetic controls,not thermodynamic phase claims."""),
17:('Density and structural evidence for two labelled iron records',
"""Two supplied Fe geometries have repository labels bcc_Fe and fcc_Fe. Their labels and proposed equal atomic volume are hypotheses for quantitative audit. Report density_g_cm3,space_group_numbers,directed_edges_within_2_7_A,first_powder_angle_deg and geometric_equivalence under inputs.conditions. Each readout uses the actual supplied cell and sample order. Powder lines are ideal nonanomalous kinematic readouts,with no broadening or texture. The exercise concerns static geometry; magnetic order,free energy and experimental phase identity are outside its scope."""),
20:('Periodic endpoint comparison under two coordinate records',
"""A reference and two candidate endpoint records are supplied,with repository labels wrapped_mobile and unwrapped_mobile. Whether their displacement evidence agrees is to be determined from the data; names do not certify equivalence. Atom correspondence is the fixed species order[Na,Ti,O],and every cell is unchanged. Report wrapped_mobile_minimum_distances_A,unwrapped_mobile_minimum_distances_A,wrapped_mobile_Na_displacement_A and unwrapped_mobile_Na_displacement_A. Cartesian displacements are mobile-image minus reference under exact minimum-image geometry. parsed_site_counts and directed_edges_within_3_A concern every sample in sample_ids order. These are synthetic endpoints,not a diffusion path or diffusion coefficient."""),
21:('Minimum-image distances and directional uniqueness of endpoint records',
"""A fixed cubic reference and two candidate endpoint files are supplied,with repository labels half_cell and near_half_cell. These names are hypotheses,not a statement of their computed image multiplicity or uniqueness. Atom correspondence is[Cs,Cl]. Report each endpoint's minimum distances,image tie counts and unique flags in that atom order,using the named answer fields. Images within1e-8A of the minimum distance count as tied. Also report density_g_cm3 and parsed_site_counts for every supplied sample. A returned deterministic representative vector is not itself evidence of unique direction. The source cell,identity and endpoint geometry are fixed controls,without a pathway inference."""),
22:('Geometric audit of two proposed periodic-basis representations',
"""Two one-site He geometry records carry repository labels oblique_basis and reduced_basis. Their proposed periodic equivalence must be assessed from actual observations,not presumed from these labels. Report density_g_cm3,directed_edges_within_1_A,space_group_numbers,same_periodic_structure and cell_volumes_A3 under inputs.conditions. oblique_basis_edges and reduced_basis_edges contain the complete directed periodic edge records: center_index,neighbor_index,image_shift,distance_angstrom,displacement_angstrom,edge_id. Each integer image is expressed in its own supplied basis; nonzero self images within the cutoff are included. These compressed synthetic controls are a geometry experiment,not stable helium phases."""),
23:('Scale-dependent geometric comparisons of three supplied records',
"""A reference and two candidate geometry files are labelled isotropic_compression and orthorhombic_strain in the repository. These labels propose relationships rather than certifying any match. Report density_g_cm3,density_relative_to_reference,and directed_edges_within_3_A for all samples. For candidates in that stated order,report matches_without_rescaling and matches_allowing_isotropic_rescaling under the supplied lattice,site and angle tolerances. The two comparisons have distinct physical-length conventions; all requested evidence is required. No thermodynamic state or experimental property is inferred from these synthetic records."""),
32:('Weighted-tree comparison with trait observations',
"""Two weighted-tree serializations root1,root2 and a numerical trait table share fixed taxon identities. Their proposed relationship is not a certified equality claim. Report root1_patristic_distances,root2_patristic_distances,the two root_to_tip_lengths vectors and total_branch_length values,traits_distances(Euclidean),and association1_correlation,association2_correlation between each tree distance matrix and trait geometry with zero permutations. pairwise_invariant and root_to_tip_invariant compare the corresponding matrices/vectors with absolute+relative1e-9 tolerance. All quantities retain the same taxon order. The experiment does not infer an evolutionary rate."""),
37:('RNA record uncertainty and denominator conventions',
"""Four artificial RNA records have supplied symbols and gaps. For every U1..U4 report length,nongap_length,canonical_fraction,and gc_percent_bounds_all_nongap. For the requested records U1 and U3 also report their composition_fractions. width_U1..width_U4 is upper minus lower all-nongap GC bound in percentage points; selected contains all maximum-width record IDs with absolute tie tolerance1e-9. Original ambiguity remains part of the observation; there is no imputation or replacement of the requested denominator. No biological function is inferred."""),
54:('Geometry and shape readouts of labelled molecular records',
"""The four SDF records and coordinate_sets are ordered a,b,c,d with the same five atom labels and fixed correspondence. Relationships among their geometries are to be assessed from the observations,not assumed from a construction label. Coordinates are preserved without re-embedding,H addition,rescaling or atom rematching. Report centroids(unweighted,as_parsed),atom_counts,within_a,b,c,d Euclidean distance matrices,the proper-rigid equal-point-weight rmsd_matrix,and preserved-coordinate USRCAT shape_similarity. mirror_distance_invariant compares the a/c distance matrices within1e-6; mirror_proper_equivalent compares their proper-fit RMSD with1e-6. These named fields state comparison targets,not their truth values. The records are synthetic geometry controls,not experimentally assigned conformers.""")})

# The single-source population exercise is replaced by a genuine independent
# multi-record transcription audit; its answer values are not stated here.
TEXT[73]=('Population-accounting audit across three supplied records',
    'Three controlled transcription-audit records a,b,c share atom order[Mg,O,C,C] and nuclear charges[12,8,6,6]. Each record has its own source values and combined,alpha,beta channel metadata. For k=a,b,c,electron_totals_k gives the three channel Total sums. charge_residual_k=abs(32-sum(combined Total)-sum(combined Charge)); spin_residual_k is the maximum atomic absolute difference between alpha Total-beta Total and combined Density; component_residual_k is the maximum atomic absolute difference between Core+Valence+Rydberg and combined Total. accounting_residual_k is the maximum of those three residuals,and consistent_k means accounting_residual_k<=5e-5. largest_violation_ids contains every record ID with maximum accounting residual,using absolute tie tolerance1e-9. Preserve recorded values and atom/channel identities; do not repair or combine records. All three are explicitly controlled transcription-audit fixtures derived from a bundled output,not different physical states,new calculations or evidence that any record passes these checks.')

TITLES={28:'Paired cover observations with unequal within-plot sampling effort',34:'Local and pooled community diversity',32:'Comparing two weighted-tree serializations with trait observations',
54:'Geometry and shape readouts of labelled molecular controls',64:'Held-out assessment of volume-density calibrations',
68:'Composition and occupancy in density-model transfer',73:'Audit of printed spin-resolved population tables',
78:'Weighted-tree distances and trait geometries',80:'Sample means and future growth under a plug-in model',
84:'Ecological trait relations and enrichment families',86:'Community trait distributions and taxonomic composition',
87:'Four uncertainty specifications for an allometric calibration',96:'Correlation-matrix admissibility under different missing-data cohorts',
99:'Bounds and geometry of a joint calibration feasible set'}


def rewrite(task):
    number=int(task['id'][-4:]);result=deepcopy(task)
    if number in TEXT:
        title,body=TEXT[number]
        result['question']=title+'. '+body+' Return the named fields in the supplied JSON answer contract. Unless a field states otherwise,numeric tolerance is absolute1e-6 plus relative1e-6; selection ties use absolute1e-9. Array order follows the input order unless explicitly stated otherwise.'
    elif number in TITLES:
        result['question']=TITLES[number]+'. '+result['question'].split('. ',1)[1]
    if number==33:
        result['question']='Spatial pattern comparison in observational quadrats. '+result['question'].split('. ',1)[1]
        result['question']=result['question'].replace('Report causal_effect_identified=false: neither descriptive comparison identifies a soil intervention effect in this spatially structured fixture.','Report causal_effect_identified to assess whether the supplied observational design and descriptive associations identify a soil intervention effect.')
    return result

REVISED_IDS={f'SMAS-{n:04d}' for n in set(TEXT)|set(TITLES)|{33}}


def adjust_criteria(task, spec):
    """Accept equivalent finite systems without accepting unrelated witnesses.

    Every row remains paired with its RHS. Full-rank checks and the independent
    forward witness remain required; numerical and scientific tolerances do not
    change. This does not turn an unobserved answer into tool evidence.
    """
    from itertools import combinations, product
    def value(x):return {'value':x}
    def expr(op,*args):return {'operation':op,'args':list(args)}
    def observed(node,path):return {'source':'node','node':node,'path':path}
    def paired_rules(a,b):
        return [{'left':expr('paired_rows',{'source':'call_arguments','path':'/matrix_a'},
                             {'source':'call_arguments','path':'/vector_b'}),
                 'op':'multiset_equal','right':expr('paired_rows',a,b),'atol':1e-9,'rtol':1e-9}]
    if task['id']=='SMAS-0055':
        # The representation operations already report their actual explicit
        # atom inventories. Counting their resulting graphs again is redundant.
        inventories={n['id']:n['id'].replace('count_added_','add_').replace('count_removed_','remove_')
            for n in spec['nodes'] if n['id'].startswith(('count_added_','count_removed_'))}
        spec['nodes']=[n for n in spec['nodes'] if n['id'] not in inventories]
        def atoms(v):
            if isinstance(v,dict):
                if v.get('source')=='node' and v.get('node') in inventories:
                    return observed(inventories[v['node']],'/atom_count')
                return {key:atoms(x) for key,x in v.items()}
            if isinstance(v,list):return [atoms(x) for x in v]
            return v
        spec['outcomes']=atoms(spec['outcomes'])
        for outcome in spec['outcomes']:
            outcome['evidence_nodes']=list(dict.fromkeys(inventories.get(n,n)
                for n in outcome.get('evidence_nodes',[])))
    if task['id']=='SMAS-0089':
        # Associative SVD evaluation may avoid materializing a pseudoinverse.
        # All factors are bound to the actual decomposition and retained rank.
        def array(*v):return expr('array',*v)
        def matrix(rows):return expr('numeric_rows',*[array(*r) for r in rows])
        def svd(path):return observed('svd',path)
        spec['nodes']=[n for n in spec['nodes'] if not n['id'].startswith('inverse_')]
        for node in spec['nodes']:
            if not node['id'].startswith('solution_r'):continue
            r=int(node['id'][-1])
            V=matrix([[svd(f'/vt/{h}/{j}') for h in range(r)] for j in range(3)])
            scaled=matrix([[expr('divide',svd(f'/vt/{h}/{j}'),svd(f'/singular_values/{h}'))
                            for h in range(r)] for j in range(3)])
            ub=[expr('sum',array(*[expr('multiply',svd(f'/u/{j}/{h}'),
                    {'source':'inputs','path':f'/b/{j}'}) for j in range(3)])) for h in range(r)]
            ratios=array(*[expr('divide',ub[h],svd(f'/singular_values/{h}')) for h in range(r)])
            pseudo=matrix([[expr('sum',array(*[expr('divide',
                expr('multiply',svd(f'/vt/{h}/{j}'),svd(f'/u/{k}/{h}')),
                svd(f'/singular_values/{h}')) for h in range(r)])) for k in range(3)] for j in range(3)])
            pairs=[(pseudo,{'source':'inputs','path':'/b'}),(V,ratios),(scaled,array(*ub))]
            node['depends_on']=['svd'];node['alternatives']=[]
            for left,right in pairs:
                node['alternatives'].append({'tools':['MatrixMultiply'],'input_rules':[
                    {'path':'/left','op':'eq','right':left,'atol':1e-9,'rtol':1e-9},
                    {'path':'/right','op':'eq','right':right,'atol':1e-9,'rtol':1e-9}],
                    'output_rules':[{'path':'','op':'type','value':'object'}]})
    if task['id']=='SMAS-0090':
        # Row/column contrast notation must not mandate a particular second
        # matrix product. Scalar projection checks remain source-bound to P.
        spec['nodes']=[n for n in spec['nodes'] if n['id']!='contrasts']
        def contrast(v):
            if isinstance(v,dict):
                if v.get('source')=='node' and v.get('node')=='contrasts':
                    _,_,j,i=v['path'].split('/')
                    return expr('sum',expr('array',*[expr('multiply',
                        observed('projector',f'/product/{j}/{h}'),
                        {'source':'inputs','path':f'/C/{i}/{h}'}) for h in range(3)]))
                return {k:contrast(x) for k,x in v.items()}
            if isinstance(v,list):return [contrast(x) for x in v]
            return v
        spec.update(contrast(spec))
        for outcome in spec['outcomes']:
            outcome['evidence_nodes']=list(dict.fromkeys('projector' if n=='contrasts' else n
                for n in outcome.get('evidence_nodes',[])))
    if task['id']=='SMAS-0099' and any(n['id']=='vertex_projection' for n in spec['nodes']):
        # The three queries may be projected together or as independent vectors.
        original=next(n for n in spec['nodes'] if n['id']=='vertex_projection')
        spec['nodes']=[n for n in spec['nodes'] if n['id']!='vertex_projection']
        for i,k in enumerate('abc'):
            node=deepcopy(original);node['id']='vertex_projection_'+k
            single=deepcopy(node['alternatives'][0])
            for rule in single['input_rules']:
                if rule.get('path')=='/right':rule['right']={'source':'inputs','path':f'/queries/{i}'}
            node['alternatives'].append(single);spec['nodes'].append(node)
            outcome=next(o for o in spec['outcomes'] if o['id']=='vertex_bounds_'+k)
            def projection(v):
                if isinstance(v,dict):
                    if v.get('source')=='node' and v.get('node')=='vertex_projection':
                        j=v['path'].split('/')[2]
                        return expr('select_if_text_equal',observed(node['id'],'/operation'),value('matrix_vector'),
                            observed(node['id'],f'/product/{j}'),observed(node['id'],f'/product/{j}/{i}'))
                    return {key:projection(x) for key,x in v.items()}
                if isinstance(v,list):return [projection(x) for x in v]
                return v
            outcome.update(projection(outcome));outcome['evidence_nodes']=[node['id']]
    if task['id']=='SMAS-0088':
        # Transforming all rows with training-only statistics is equivalent to
        # separate train/test transforms. Evaluation rows never fit the scale.
        full=task['inputs']['features'];cuts=dict(zip('abc',[5,8,11]))
        scales={n['id']:n for n in spec['nodes'] if n['id'].startswith('scale_')}
        for name,node in scales.items():
            cut=cuts[name[-1]];subset=full[:cut+1] if name.startswith('scale_train_') else full[cut+2:]
            for alt in node['alternatives']:
                for rule in alt['input_rules']:
                    if rule.get('path')=='/features':
                        rule.pop('right',None);rule.update(op='one_of',value=[subset,full])
        def selected_rows(v):
            if isinstance(v,dict):
                if v.get('source')=='node' and v.get('node') in scales and v.get('path')=='/features':
                    name=v['node'];cut=cuts[name[-1]];raw=deepcopy(v)
                    if name.startswith('scale_train_'):return expr('slice',raw,value(0),value(cut+1))
                    return expr('select_if_boolean',expr('finite_ge',expr('length',raw),value(len(full))),
                                expr('slice',raw,value(cut+2),value(len(full))),raw)
                return {k:selected_rows(x) for k,x in v.items()}
            if isinstance(v,list):return [selected_rows(x) for x in v]
            return v
        spec.update(selected_rows(spec))
    if task['id']=='SMAS-0071':
        # Scalar bookkeeping on already observed source values is not a new
        # measurement. Preserve all predicates without forcing calculator calls.
        substitutions={};removed={'logp'}
        for i in range(len(task['inputs']['pressure_ratios'])):
            substitutions[('logp',f'/values/{i}')]=expr('natural_log',
                {'source':'inputs','path':f'/pressure_ratios/{i}'})
        def bookkeeping(v):
            if isinstance(v,dict):
                if v.get('source')=='node' and v.get('node') in removed:
                    return deepcopy(substitutions[(v['node'],v.get('path',''))])
                return {k:bookkeeping(x) for k,x in v.items()}
            if isinstance(v,list):return [bookkeeping(x) for x in v]
            return v
        spec['nodes']=[n for n in spec['nodes'] if n['id'] not in removed]
        spec.update(bookkeeping(spec))
        for outcome in spec['outcomes']:
            evidence=outcome.get('evidence_nodes',[])
            if set(evidence)&removed:
                outcome['evidence_nodes']=sorted(set(evidence)-removed)
    if task['id']=='SMAS-0054':
        # The coordinate-reader provenance already certifies the atom inventory
        # of the exact same source, record and H policy. An extra counter call
        # would measure the same capability twice.
        counts={n['id'] for n in spec['nodes'] if n['id'].startswith('count_')}
        spec['nodes']=[n for n in spec['nodes'] if n['id'] not in counts]
        def inventory(v):
            if isinstance(v,dict):
                if v.get('source')=='node' and v.get('node') in counts:
                    return {'source':'node','node':v['node'].replace('count_','center_'),
                            'path':'/provenance/atom_count'}
                return {k:inventory(x) for k,x in v.items()}
            if isinstance(v,list):return [inventory(x) for x in v]
            return v
        spec['outcomes']=inventory(spec['outcomes'])
        for outcome in spec['outcomes']:
            outcome['evidence_nodes']=[n.replace('count_','center_') if n in counts else n
                                       for n in outcome.get('evidence_nodes',[])]
    if task['id']=='SMAS-0059':
        # Inspection already returns the actual decoder output. Require that
        # observation, not a second call to the same decoder implementation.
        decode={n['id']:n['id'].replace('decode_','inspect_') for n in spec['nodes']
                if n['id'].startswith('decode_')}
        spec['nodes']=[n for n in spec['nodes'] if n['id'] not in decode]
        def decoded(v):
            if isinstance(v,dict):
                if v.get('source')=='node' and v.get('node') in decode:
                    return {'source':'node','node':decode[v['node']],'path':'/decoded_smiles'}
                return {k:decoded(x) for k,x in v.items()}
            if isinstance(v,list):return [decoded(x) for x in v]
            return v
        spec.update(decoded(spec))
        for node in spec['nodes']:
            if 'depends_on' in node:node['depends_on']=[decode.get(n,n) for n in node['depends_on']]
        for outcome in spec['outcomes']:
            outcome['evidence_nodes']=[decode.get(n,n) for n in outcome.get('evidence_nodes',[])]
    if task['id']=='SMAS-0098':
        P=task['inputs']['P']
        equations=[[P[j][i]-float(i==j) for j in range(3)] for i in range(3)]
        node=next(n for n in spec['nodes'] if n['id']=='stationary')
        alternatives=[]
        for size in (2,3):
            for chosen in combinations(range(3),size):
                for signs in product((-1,1),repeat=size):
                    A=[[sign*x for x in equations[i]] for i,sign in zip(chosen,signs)]+[[1.,1.,1.]]
                    rules=paired_rules(value(A),value([0]*size+[1]))
                    if size==2:
                        alternatives.append({'tools':['SolveLinearSystem'],'input_rules':rules,
                            'output_rules':[{'path':'','op':'type','value':'object'}]})
                    alternatives.append({'tools':['LinearLeastSquares'],'input_rules':deepcopy(rules),
                        'output_rules':[{'path':'/rank','op':'eq','value':3}]})
        node['alternatives']=alternatives
    if task['id']=='SMAS-0063':
        for node in spec['nodes']:
            for original in list(node['alternatives']):
                if original['tools']!=['SolveLinearSystem']:continue
                alt=deepcopy(original);alt['tools']=['LinearLeastSquares']
                alt['output_rules'].append({'path':'/rank','op':'eq','value':3})
                if alt not in node['alternatives']:node['alternatives'].append(alt)

# Parent-only, individually recorded reasons. These notes are never solver input.
PUBLICATION_NOTES={
8:'Editorial: replace imperative fingerprint-to-graph execution instructions with definitions of the two representations and requested propagation quantities.',
14:'Remove the certified structural relationships from the repository introduction; labels now denote hypotheses to audit.',
16:'Treat ordered/disordered repository names as unverified metadata so the eligibility answer must follow actual occupancies.',
17:'Remove the assertion of equal atomic volumes, which prejudged density agreement; assess the actual supplied cells.',
20:'Remove the assertion that both files are the same endpoint; the displacement agreement must be observed.',
21:'Remove the declared exact/near half-cell construction, which prejudged image multiplicity and uniqueness.',
22:'Remove the claim that both bases describe the same lattice; geometric equivalence remains an assessed result.',
23:'Treat the compression/strain labels as proposed relationships instead of certified matching results.',
28:'Editorial: use a neutral observational title; the sampling-unit and bootstrap experiment remain specified.',
32:'Remove both the invariance title and the assertion of the same unrooted weighted tree, which revealed the pairwise-invariance judgment.',
33:'Remove the explicitly supplied causal-identification Boolean answer; ask for a judgment from the observational design.',
34:'Replace a title that states pooling changes the estimand with a neutral local/pooled diversity question.',
37:'Remove the characterization of requested RNA records as canonical, so canonical fractions remain observed quantities.',
40:'Editorial: define the transient model, candidate times and target discrepancy without prescribing the execution order.',
54:'Remove construction labels declaring rigid motion, reflection and dilation; geometry comparisons now require observed evidence.',
55:'Remove registered hydrogen-operation tool names from the question; retain the scientific representation conventions.',
59:'Remove the registered inspection interface and imperative round-trip recipe; retain the two serialization experiments and graph-identity conventions.',
60:'Specify the blend constraints, objective and independent balance certificate without a prescribed tool sequence.',
63:'Specify phase fractions, additive volumes and the independent elemental check without prescribing a particular inverse-solver interface.',
64:'Remove a title that identified reciprocal-volume physics as the held-out winner.',
68:'Remove the title that attributed the discrepancy to hidden vacancy information before model comparison.',
71:'Editorial: retain reservoir equations and units while avoiding a prescribed shared-correction execution plan.',
72:'Editorial: retain the calibrated response family and reproducible fitting conditions, but describe estimands rather than ordered tool operations.',
73:'Replace the single-readout exercise with three controlled transcription audits; no public label identifies which records pass, and synthetic controls are not called new calculations.',
76:'Describe dissimilarity and embedding quantities without a tool-by-tool execution recipe; negative eigenvalues are not disclosed.',
78:'Remove the title stating correlation is blind to branch-length scaling; compare the actual tree and trait readouts.',
80:'Remove the title asserting a positive mean is unreliable before the conditional prediction is evaluated.',
82:'Use target-population definitions instead of a conclusion-leading title about weighting dependence.',
84:'Replace the title preannouncing the reachability/enrichment distinction with a neutral relation-and-family audit.',
85:'Remove qualitative amplification language from the title; pulse responses and worst-case gains are measured independently.',
86:'Remove the explicit claim of equal community centroids, which disclosed a scored equality judgment.',
87:'Use a neutral calibration title without preannouncing the uncertainty-scaling conclusion; retain the four sigma experiments.',
88:'Describe the cutoff-specific statistical experiment without prescribing separate train/test transformation calls; legitimate frozen-scale batches are accepted.',
89:'Remove the prescribed pseudoinverse materialization order; equivalent retained-SVD factorizations remain eligible.',
90:'Use a neutral estimation/contrast title; retain the scientific estimability definition without prescribing a second projector-product orientation.',
91:'Remove the title revealing that the positive class is not probability column one; the named label still defines the scientific target.',
92:'Specify independent linear-system witnesses without prescribing the order of inverse and direct computations.',
95:'Use a neutral tabulation-diagnostics title while retaining the analytic model, gradient and interpolation conventions.',
96:'Remove the title suggesting that a pairwise correlation matrix is inadmissible before its spectrum is evaluated.',
97:'Remove the named clustering-quality tool and express noise coverage, silhouette domain and selection conditions directly.',
98:'Remove the specific shared-squaring and first-two-stationary-equations recipe; accept equivalent balanced systems with paired rows/RHS.',
99:'Remove the title announcing the joint-versus-marginal conclusion and the ordered six-LP recipe; optimization and independent geometry remain scientific certificate requirements.',
100:'Remove the title stating which mass is conserved, so the conservation Booleans must follow actual results.'}
