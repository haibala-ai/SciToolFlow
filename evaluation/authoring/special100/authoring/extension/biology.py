"""Benign, controlled ecology and measurement workflows with explicit scientific units."""
from .common import *


def stratified_endpoints():
    c=Case(75,'Biology','advanced','Restoration endpoints under a fixed target-habitat mixture',
      'Three before/after endpoints are observed in quadrats nested in four independent plots, two plots per habitat. Target habitat weights are0.3(lowland),0.7(upland), not observed quadrat frequencies. For cover(percent points),height(cm),biomass(g/m^2), form paired within-row after-minus-before changes. Report weighted_mean_k,weighted_interval_k from stratified cluster resampling and unweighted_mean_k,unweighted_interval_k from equal-plot grouped resampling, k=cover,height,biomass. Use1000 resamples,seed19,central95% intervals. In parallel report naive_mean_k and naive_interval_k from equal-quadrat percentile bootstrap. Report weighted_positive_k iff weighted lower bound>0. Each interval is marginal, not a simultaneous95% region; neither a narrow interval nor resampling establishes independent quadrats.',
      {'groups':['L1','L1','L2','L2','L2','U1','U1','U2','U2','U2','U2'],'strata':['lowland']*5+['upland']*6,'weights':[{'stratum':'lowland','weight':.3},{'stratum':'upland','weight':.7}],
       'before':{'cover':[10,11,8,10,9,20,18,15,16,17,15],'height':[4,5,6,5,7,9,8,6,7,6,8],'biomass':[20,21,15,16,18,30,31,25,24,23,26]},
       'after':{'cover':[8,10,9,11,10,25,24,19,20,21,20],'height':[3,5,6,6,7,12,12,9,11,10,11],'biomass':[17,19,16,17,19,42,43,32,31,33,34]}},
      'stratified_target_population_estimands','Paired changes and independent plot identity are shared across target-weight, equal-plot and naive analyses.',
      ['Three endpoint chains','Three distinct resampling estimands per endpoint'],
      'Keep target habitat weights, plot independence and endpoint units separate when comparing conclusions.')
    for k in ['cover','height','biomass']:
        diff=vector(*[E('subtract',I(f'/after/{k}/{i}'),I(f'/before/{k}/{i}')) for i in range(11)])
        common={'values':diff,'confidence':V(.95),'resamples':V(1000),'seed':V(19)}
        w=c.add('weighted_'+k,'StratifiedClusterMeanInterval',{**common,'groups':I('/groups'),'strata':I('/strata'),'stratum_weights':I('/weights')});g=c.add('unweighted_'+k,'GroupedBootstrapMeanInterval',{**common,'groups':I('/groups')});n=c.add('naive_'+k,'BootstrapMeanInterval',common)
        for label,node,interval in [('weighted',w,N(w,'/interval')),('unweighted',g,N(g,'/interval')),('naive',n,vector(N(n,'/lower'),N(n,'/upper')))]:c.out(label+'_mean_'+k,N(node,'/mean'));c.out(label+'_interval_'+k,interval,'array')
        c.flag('weighted_positive_'+k,N(w,'/interval/0'),'gt',V(0))
    return c.emit()


def distance_embeddability():
    c=Case(76,'Biology','advanced','Community dissimilarities and Euclidean embedding admissibility',
      'Four communities share five taxon columns. Compute full raw-count Bray-Curtis D_bray and binary-presence Jaccard D_jaccard. Separately row-normalize counts, take elementwise square roots and compute Euclidean D_hellinger. For each metric construct B=-0.5 J(D elementwise squared)J, J=I-11^T/4. Report gram_k and ascending spectrum_k, k=bray,jaccard,hellinger. Report euclidean_k iff smallest eigenvalue>=-1e-8. Keep genuine negative eigenvalues; do not project a non-Euclidean matrix to PSD or treat a small numerical negative as scientific indefiniteness. Taxa are features; communities are the distance objects.',
      {'counts':[[8,0,0,0,0],[0,8,0,0,0],[8,8,0,0,0],[4,4,2,1,1]]},'dissimilarity_embedding_domain','A single row/taxon order feeds three incompatible dissimilarity constructions and one centering convention.',
      ['Bray-Curtis and Jaccard branches','Hellinger transform and metric-specific Gram/spectrum chains'],
      'Test the Euclidean embedding assumption rather than silently equating all distance matrices.')
    b=c.add('bray','PairwiseNumericDistances',{'values':I('/counts'),'metric':V('braycurtis')});j=c.add('jaccard','PairwiseNumericDistances',{'values':V([[int(v>0) for v in row] for row in c.inputs['counts']]),'metric':V('jaccard')});p=c.add('relative','NormalizeNumericRows',{'matrix':I('/counts')});h=c.add('sqrt','ElementwiseNumericOperations',{'operation':V('sqrt'),'values':N(p,'/proportions')});d=c.add('hellinger','PairwiseNumericDistances',{'values':N(h,'/values'),'metric':V('euclidean')});J=V([[float(i==j)-.25 for j in range(4)] for i in range(4)])
    for label,node in [('bray',b),('jaccard',j),('hellinger',d)]:
        sq=c.add('square_'+label,'ElementwiseNumericOperations',{'operation':V('multiply'),'values':N(node,'/distances'),'other':N(node,'/distances')});left=c.add('left_'+label,'MatrixMultiply',{'left':J,'right':N(sq,'/values')});both=c.add('center_'+label,'MatrixMultiply',{'left':N(left,'/product'),'right':J});right_rule=next(r for r in c.nodes[-1]['alternatives'][0]['input_rules'] if r.get('path')=='/right');right_rule.pop('right');right_rule.update(op='one_of',value=[J['value'],[[-.5*x for x in row] for row in J['value']]]);factor=E('divide',V(-.375),{'source':'node_arguments','node':both,'path':'/right/0/0'});B=matrix([[E('multiply',factor,N(both,f'/product/{i}/{j}')) for j in range(4)] for i in range(4)]);e=c.add('eigen_'+label,'SymmetricEigenDecomposition',{'values':B})
        c.out('D_'+label,N(node,'/distances'),'array');c.out('gram_'+label,B,'array');c.out('spectrum_'+label,N(e,'/eigenvalues'),'array');c.flag('euclidean_'+label,N(e,'/eigenvalues/0'),'ge',V(-1e-8))
    return c.emit()


def rarefaction():
    c=Case(77,'Biology','intermediate','Observed richness versus equal-effort finite rarefaction',
      'Three finite census controls have different total effort. For each a,b,c report observed_total,observed_richness,observed_shannon and expected_richness_k at sample sizes[4,8,12], computed by uniform sampling WITHOUT replacement from that community. Also report absent_at_8_k per taxon in original column order. Return raw_richest_ids by observed richness and rarefied_richest_ids by expected richness at n8, retaining ties within1e-9. In parallel compute n8 with-replacement zero-hit probabilities for the rarest present taxon in each community using its census proportion; report replacement_absence_k. A zero census taxon is not a rare present taxon, and rarefaction does not correct detection bias.',
      {'counts':[[4,4,4,4,0],[32,2,2,2,2],[20,20,20,20,0]],'sizes':[4,8,12]},'effort_standardized_richness','Each finite census establishes total size, nonzero taxa and the shared sampling-size convention.',
      ['Independent communities','Raw diversity, finite sampling and replacement counterfactuals'],
      'Compare equal-effort estimates rather than letting the largest raw census define richness.')
    raw=[];rare=[]
    for i,k in enumerate('abc'):
        counts=c.inputs['counts'][i];d=c.add('div_'+k,'DiversityIndices',{'counts':I(f'/counts/{i}')});f=c.add('finite_'+k,'FinitePopulationCoverage',{'population_size':V(sum(counts)),'feature_success_counts':I(f'/counts/{i}'),'sample_sizes':I('/sizes')});b=c.add('replacement_'+k,'BinomialProbabilityTable',{'n':V(8),'p':V(min(x for x in counts if x>0)/sum(counts))})
        c.out('observed_total_'+k,N(d,'/total'));c.out('observed_richness_'+k,N(d,'/richness'));c.out('observed_shannon_'+k,N(d,'/shannon_nats'));c.out('expected_richness_'+k,vector(*[N(f,f'/analyses/{j}/expected_detected_features') for j in range(3)]),'array');c.out('absent_at_8_'+k,N(f,'/analyses/1/feature_absence_probabilities'),'array');c.out('replacement_absence_'+k,N(b,'/pmf/0'));raw.append(N(d,'/richness'));rare.append(N(f,'/analyses/1/expected_detected_features'))
    c.selection('raw_richest_ids',list('abc'),raw,maximize=True);c.selection('rarefied_richest_ids',list('abc'),rare,maximize=True);return c.emit()


def tree_scale():
    c=Case(78,'Biology','intermediate','Branch-length scale is invisible to a correlation-only tree test',
      'Three weighted tree hypotheses share fixed taxa[A,B,C,D]: a, a uniformly rescaled version b, and topology-altered c. Report patristic_a,b,c and total_length_a,b,c. Compute raw_trait_distances (Euclidean) and standardized_trait_distances after population scaling across the same four taxa. For EACH tree and EACH trait geometry report Pearson upper-triangle correlation raw_corr_a etc. and scaled_corr_a etc. with zero permutations. Report length_ratio_b_a and distance_b_over_a for pair[A,B]. Correlation invariance must not be taken as equality of branch units, topology or evolutionary rates.',
      {'trees':['((A:1,B:2):1,(C:1,D:3):2);','((A:2,B:4):2,(C:2,D:6):4);','((A:1,C:1):2,(B:2,D:3):1);'],'traits':[[1,10],[2,11],[4,7],[5,8]]},'tree_scale_vs_trait_metric','Taxon identities and branch-unit conventions are shared by all comparisons.',
      ['Three independent tree parsers','Raw versus standardized trait geometry and six correlation joins'],
      'Separate a scale-insensitive association statistic from an absolute tree-distance claim.')
    scale=c.add('scale','StandardizeNumericFeatures',{'training_features':I('/traits'),'features':I('/traits')});raw=c.add('traits_raw','PairwiseNumericDistances',{'values':I('/traits'),'metric':V('euclidean')});std=c.add('traits_scaled','PairwiseNumericDistances',{'values':N(scale,'/features'),'metric':V('euclidean')});c.out('raw_trait_distances',N(raw,'/distances'),'array');c.out('standardized_trait_distances',N(std,'/distances'),'array')
    for i,k in enumerate('abc'):
        t=c.add('tree_'+k,'ParseNewickTreeDistances',{'newick_text':I(f'/trees/{i}')});aligned=matrix([[E('matrix_value_by_ids',N(t,'/patristic_distances'),N(t,'/tip_ids'),V(a),V(b)) for b in 'ABCD'] for a in 'ABCD']);c.out('patristic_'+k,aligned,'array');c.out('total_length_'+k,N(t,'/total_branch_length'))
        for label,node in [('raw',raw),('scaled',std)]:
            m=c.add(label+'_'+k,'MantelCorrelation',{'distance_a':aligned,'distance_b':N(node,'/distances'),'permutations':V(0)});c.out(label+'_corr_'+k,N(m,'/correlation'))
    c.out('length_ratio_b_a',E('divide',N('tree_b','/total_branch_length'),N('tree_a','/total_branch_length')));c.out('distance_b_over_a',E('divide',N('tree_b','/patristic_distances/0/1'),N('tree_a','/patristic_distances/0/1')));return c.emit()


def complete_case():
    c=Case(79,'Biology','intermediate','One complete-case ecological cohort must anchor every comparison',
      'Observational rows contain moisture,growth and nutrient, with explicit nulls. Restrict ALL analyses to their joint complete-case cohort, preserving row order, and report cohort_ids. On that SAME cohort report Pearson and Spearman correlations for moisture-growth and moisture-nutrient (mg_pearson,mg_spearman,mn_pearson,mn_spearman), each as [correlation,p_value,count]. Also report mean_growth,interval_growth,mean_nutrient,interval_nutrient from separate percentile bootstraps (1000 resamples,seed23,95%). Do not perform pairwise deletion, turn null into zero or imply missingness is random or a causal effect is identified.',
      {'rows':[{'id':'p'+str(i+1),'moisture':x,'growth':g,'nutrient':n} for i,(x,g,n) in enumerate([(1,2,7),(2,3,None),(3,None,8),(4,6,5),(5,4,4),(6,8,3),(7,9,2),(8,None,None),(None,5,6),(10,12,1)])]},'joint_complete_case_cohort','One explicit joint cohort is shared by both response geometries and uncertainty branches.',
      ['Three variable-extraction branches after shared filtering','Four associations and two marginal bootstrap summaries'],
      'Prevent separately filtered analyses from silently describing different scientific populations.')
    cohort=E('records_nonnull',I('/rows'),V(['moisture','growth','nutrient']))
    columns={col:E('column',E('records_columns',cohort,V([col])),V(0)) for col in ['moisture','growth','nutrient']}
    stats=[]
    c.out('cohort_ids',E('column',E('records_columns',cohort,V(['id'])),V(0)),'array',evidence=['mg_pearson','mg_spearman','mn_pearson','mn_spearman'])
    for tag,response in [('mg','growth'),('mn','nutrient')]:
        for method,tool in [('pearson','PearsonCorrelation'),('spearman','SpearmanCorrelation')]:
            n=c.add(tag+'_'+method,tool,{'x':columns['moisture'],'y':columns[response]});stats.append(n);c.out(tag+'_'+method,vector(N(n,'/correlation'),N(n,'/p_value'),N(n,'/count')),'array')
    for response in ['growth','nutrient']:
        b=c.add('bootstrap_'+response,'BootstrapMeanInterval',{'values':columns[response],'confidence':V(.95),'resamples':V(1000),'seed':V(23)});c.out('mean_'+response,N(b,'/mean'));c.out('interval_'+response,vector(N(b,'/lower'),N(b,'/upper')),'array')
    return c.emit()


def detection_reliability():
    c=Case(80,'Biology','foundation','Positive plot-average growth is not reliable plot-level success',
      'Three sites supply independent signed annual growth increments (cm). As an explicitly assumed Gaussian plug-in model, estimate mean and sample standard deviation per site. Report mean_a etc.,sd_a etc., and95% percentile-bootstrap mean intervals interval_a etc. (1000 resamples,seed29). Compute p_positive_a etc.=P(X>0) under the fitted normal model. Then report p_at_least4_a etc. for at least4 positive increments among5 independent future plots under that plug-in probability. Keep parameter uncertainty distinct from these plug-in predictions; do not interpret a positive observed mean as certainty of plot-level success.',
      {'growth':[[1,2,2,3,2,1,3],[-2,5,-1,6,0,4,-1],[.1,.2,.15,.05,.3,.1,.2]]},'mean_uncertainty_vs_success_probability','Each site sample defines an estimated model and an independently reported sampling interval.',
      ['Site mean/SD descriptions and mean bootstrap intervals','Normal-tail then future-count probability chains'],
      'Compare an average estimand with predictive reliability under a clearly stated model assumption.')
    desc={};boots={}
    for i,k in enumerate('abc'):
        desc[k]=c.add('description_'+k,'DescribeNumericData',{'values':I(f'/growth/{i}')})
        boots[k]=c.add('bootstrap_'+k,'BootstrapMeanInterval',{'values':I(f'/growth/{i}'),'confidence':V(.95),'resamples':V(1000),'seed':V(29)})
    zs=vector(*[E('divide',N(desc[k],'/mean'),N(desc[k],'/sample_std')) for k in 'abc'])
    normal=c.add('normal_probabilities','StandardNormalDistribution',{'operation':V('cdf'),'values':zs})
    for i,k in enumerate('abc'):
        d=desc[k];b=boots[k];p=N(normal,f'/results/{i}');binom=c.add('future_'+k,'BinomialProbabilityTable',{'n':V(5),'p':p})
        c.out('mean_'+k,N(d,'/mean'));c.out('sd_'+k,N(d,'/sample_std'));c.out('interval_'+k,vector(N(b,'/lower'),N(b,'/upper')),'array');c.out('p_positive_'+k,p);c.out('p_at_least4_'+k,E('add',N(binom,'/pmf/4'),N(binom,'/pmf/5')))
    return c.emit()


def oriented_qc():
    c=Case(81,'Biology','intermediate','Orientation comparison after preserving original barcode QC',
      'The FASTA contains four artificial nonfunctional DNA QC controls with possible orientation differences. Parse records without merging headers. Report qc_a etc. as [length,canonical_fraction,number_of_invalid_symbols] for original sequences. A sequence is eligible iff canonical_fraction=1 and no invalid symbols; report eligible_a etc. Only eligible records need global DNA alignments against the supplied reference in their forward and reverse-complement orientations. Report forward_score_a etc.,reverse_score_a etc.,best_score_a etc.=max(forward,reverse),and score_gap_a etc.=abs(forward-reverse). A zero gap is a tied orientation. Rejected controls must have null in all four alignment fields. Do not repair ambiguity or infer organism identity/function.',
      {'fasta':'>a\nACGTAACCGTAA\n>b\nTTACGGTTACGT\n>c\nACGTNACCGNAA\n>d\nACGTAACCATAT\n','reference':'ACGTAACCGTAA'},'orientation_with_quality_domain','Original parsed record and quality identity gate all oriented alignment interpretations.',
      ['Four independent original-QC branches','Forward and reverse-complement alignment chains for eligible records'],
      'Do not turn failed/ambiguous input into a negative orientation result.',
      'Artificial observational controls only, without biological engineering, primers, taxonomic identification or functional inference.')
    p=c.add('parse','ParseFASTARecords',{'fasta_text':I('/fasta'),'molecule_type':V('DNA')})
    for i,k in enumerate('abcd'):
        q=c.add('qc_'+k,'SequenceQualityMetrics',{'sequence':N(p,f'/records/{i}/sequence'),'molecule_type':V('DNA')});c.out('qc_'+k,vector(N(q,'/length'),N(q,'/canonical_fraction'),E('length',N(q,'/invalid_symbols'))),'array')
        for label,op,flag in [('yes','eq',True),('no','ne',False)]:
            branch=c.branch('eligible_'+k+'_'+label,q,'/canonical_fraction',op,1.);c.out('eligible_'+k,V(flag),'boolean',[q],branch)
            if flag:
                r=c.add('reverse_'+k,'GetReverseComplement',{'sequence':N(p,f'/records/{i}/sequence')},checks=[{'path':'','op':'type','value':'string'}],parents=[q],branch=branch)
                # Reverse-complement legacy output is textual; its format is handled
                # by the evaluator only if a declared scientific string is available.
                f=c.add('forward_'+k,'PairwiseSequenceAlignment',{'sequence1':I('/reference'),'sequence2':N(p,f'/records/{i}/sequence'),'mode':V('global'),'molecule_type':V('DNA')},parents=[q],branch=branch)
                rev=c.add('reverse_align_'+k,'PairwiseSequenceAlignment',{'sequence1':I('/reference'),'sequence2':E('text_between',N(r,''),V('- **Reverse Complement**: `'),V('`')), 'mode':V('global'),'molecule_type':V('DNA')},parents=[q],branch=branch)
                c.out('forward_score_'+k,N(f,'/score'),['number','null'],[q,f],branch);c.out('reverse_score_'+k,N(rev,'/score'),['number','null'],[q,rev],branch)
                c.out('best_score_'+k,E('max',vector(N(f,'/score'),N(rev,'/score'))),['number','null'],[q,f,rev],branch)
                c.out('score_gap_'+k,E('abs',E('subtract',N(f,'/score'),N(rev,'/score'))),['number','null'],[q,f,rev],branch)
            else:
                for key in ['forward_score','reverse_score','best_score','score_gap']:c.out(key+'_'+k,V(None),['number','null'],[q],branch)
    return c.emit()




def diversity_partition():
    c=Case(82,'Biology','intermediate','Effective-diversity partition depends on the population weighting rule',
      'Three stands share four taxon columns and unequal observation totals. Report local_shannon and local_effective=exp(Shannon) in stand order. Row-normalize each stand. Compare two declared target mixtures: equal_stand weights[1/3,1/3,1/3] and individual weights proportional to stand totals. For each target report pooled_proportions_k,H_alpha_k=sum(weight*local Shannon),H_gamma_k=Shannon(pooled proportions),effective_alpha_k=exp(H_alpha),effective_gamma_k=exp(H_gamma),effective_beta_k=exp(H_gamma-H_alpha),and arithmetic_local_effective_k=sum(weight*exp(local Shannon)). Do not substitute the arithmetic mean of effective diversities for exp(mean entropy), or normalize all counts before defining the target weighting rule.',
      {'counts':[[8,2,0,0],[1,9,10,0],[0,0,5,35]]},'weighted_effective_diversity_partition','Local entropy and within-stand composition are shared between two different target-population mixtures.',
      ['Three local diversity calculations','Two independently weighted pooled-composition/gamma chains'],
      'Partition effective alpha/gamma/beta without mixing linear weights with nonlinear entropy transforms.')
    p=c.add('relative','NormalizeNumericRows',{'matrix':I('/counts')});hs=[];sizes=[]
    for i in range(3):
        n=c.add('local_'+str(i),'DiversityIndices',{'counts':I(f'/counts/{i}')});hs.append(N(n,'/shannon_nats'));sizes.append(N(n,'/total'))
    eff=[E('exponential',h) for h in hs];c.out('local_shannon',vector(*hs),'array');c.out('local_effective',vector(*eff),'array')
    policies=[('equal_stand',[V(1/3)]*3),('individual',[E('divide',v,E('sum',vector(*sizes))) for v in sizes])]
    pooled=c.add('pooled_both','MatrixMultiply',{'left':matrix([w for _,w in policies]),'right':N(p,'/proportions')})
    for index,(label,w) in enumerate(policies):
        g=c.add('gamma_'+label,'DiversityIndices',{'counts':N(pooled,f'/product/{index}')});ha=dot(w,hs);hg=N(g,'/shannon_nats')
        for key,value,typ in [('pooled_proportions',N(pooled,f'/product/{index}'),'array'),('H_alpha',ha,'number'),('H_gamma',hg,'number'),('effective_alpha',E('exponential',ha),'number'),('effective_gamma',E('exponential',hg),'number'),('effective_beta',E('exponential',E('subtract',hg,ha)),'number'),('arithmetic_local_effective',dot(w,eff),'number')]:c.out(key+'_'+label,value,typ)
    return c.emit()


def common_core_geometry():
    c=Case(83,'Biology','advanced','Observed common-core correspondence versus whole-record centroid shifts',
      'Three artificial coarse protein coordinate controls contain observed CA sites, with one model missing a noncore residue and another deforming one core and one noncore site. No missing coordinates may be invented. Inspect each PDB and report observed_residue_ids_a,b,c. Extract chainA model0 CA coordinates for the explicit common core residue IDs[1,2,4,6], preserving that order, and report core_a,b,c. Independently report full-record unweighted centroids centroid_a,b,c using ALL parsed PDB atoms. Compute proper-rigid core_rmsd across the three matching core sets and separate within_core_a,b,c Euclidean distance matrices. Report core_equivalent_a_b and core_equivalent_a_c using core RMSD<=1e-6. A whole-record centroid shift is not evidence of a core deformation, and CA-only controls do not establish fold quality or biological function.',
      {'core_ids':['1','2','4','6']},'missing_residue_common_core_geometry','Source identity and explicit common residue correspondence anchor every core comparison.',
      ['Three source-quality/core-extraction chains','Full-record centroids and within-core distances versus proper-rigid core fits'],
      'Keep common-core atom identity and full-record inventory distinct.',
      'Artificial CA-only coordinate controls; no structure prediction, sequence design, atom completion or biological function inference.')
    coords=[[0,0,0],[1.2,0,0],[2,1,0],[1.1,1.2,.5],[0,1.5,1],[.4,.2,1.4]];panels=[coords,[[2-y,x-1,z+3] for x,y,z in coords],[[x+(1.1 if i==4 else .2 if i==3 else 0),y,z] for i,(x,y,z) in enumerate(coords)]];extract=[]
    for i,k in enumerate('abc'):
        lines=[]
        for j,(x,y,z) in enumerate(panels[i],1):
            if k=='b' and j==3:continue
            lines.append(f'ATOM  {j:5d}  CA  ALA A{j:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00           C  ')
        file=c.asset(k+'.pdb','\n'.join(lines)+'\nTER\nEND\n');q=c.add('quality_'+k,'InspectPDBQuality',{'file_name':file});e=c.add('core_'+k,'ExtractPDBCoordinates',{'file_name':file,'chain_id':V('A'),'model_id':V(0),'atom_name':V('CA'),'residue_ids':I('/core_ids')},parents=[q]);extract.append(e)
        center=c.add('centroid_'+k,'MolecularCentroid',{'source':file,'source_format':V('pdb'),'hydrogen_policy':V('as_parsed'),'atom_scope':V('all')});d=c.add('within_'+k,'PairwiseNumericDistances',{'values':N(e,'/coordinates'),'metric':V('euclidean')})
        c.out('observed_residue_ids_'+k,N(q,'/models/0/chains/0/residue_ids'),'array');c.out('core_'+k,N(e,'/coordinates'),'array');c.out('centroid_'+k,N(center,'/centroid'),'array');c.out('within_core_'+k,N(d,'/distances'),'array')
    fit=c.add('fit','RigidSuperposition',{'coordinate_sets':E('json_array',*[N(e,'/coordinates') for e in extract]),'set_ids':V(['a','b','c'])});c.out('core_rmsd',N(fit,'/rmsd_matrix'),'array');c.flag('core_equivalent_a_b',N(fit,'/rmsd_matrix/0/1'),'le',V(1e-6));c.flag('core_equivalent_a_c',N(fit,'/rmsd_matrix/0/2'),'le',V(1e-6));return c.emit()


def ontology_evidence():
    c=Case(84,'Biology','foundation','Trait ontology reachability is not an independent enrichment result',
      'Synthetic taxa have caller-supplied ecological trait memberships and a small child-to-parent is_a graph. Report ancestors_scraper,ancestors_shredder and descendants_feeding as order-independent sets of terms, excluding the query term itself. On the fixed universe and selected taxa, run one-sided hypergeometric enrichment for ALL supplied term memberships (deduplicate membership IDs). Report term_order,p_values,fold_enrichment and jointly adjusted q_bh and q_bonferroni in that same term order. Membership of a selected taxon in two descendant traits is not two selected taxa, and a reachable ancestor is not an independent experiment. No external ontology or organism function is inferred.',
      {'edges':[{'child':'scraper','parent':'grazer'},{'child':'grazer','parent':'feeding'},{'child':'shredder','parent':'detritivore'},{'child':'detritivore','parent':'feeding'}],'universe':['s'+str(i) for i in range(1,21)],'selected':['s1','s2','s3','s4','s5'],'members':{'scraper':['s1','s2','s3','s6'],'grazer':['s1','s2','s3','s6','s7'],'shredder':['s4','s5','s8'],'detritivore':['s4','s5','s8','s9'],'feeding':['s1','s2','s3','s4','s5','s6','s7','s8','s9']}},
      'ontology_scope_vs_familywise_evidence','One declared taxon universe and one statistical family are shared by all trait tests.',
      ['Independent ontology reachability queries','One enrichment family feeding two correction methods'],
      'Separate graph implication, unique taxon counts and multiplicity-adjusted evidence.')
    for label,term,direction in [('ancestors_scraper','scraper','ancestors'),('ancestors_shredder','shredder','ancestors'),('descendants_feeding','feeding','descendants')]:n=c.add(label,'TraverseOntologyRelations',{'edges':I('/edges'),'term':V(term),'direction':V(direction)});c.out(label,N(n,'/related_terms'),'array');c.outcomes[-1]['op']='set_equal'
    e=c.add('enrichment','HypergeometricEnrichment',{'universe_ids':I('/universe'),'selected_ids':I('/selected'),'term_members':I('/members')})
    c.out('term_order',E('scalar_array',*[N(e,f'/results/{i}/term_id') for i in range(5)]),'array');c.out('p_values',N(e,'/p_values'),'array');c.out('fold_enrichment',vector(*[N(e,f'/results/{i}/fold_enrichment') for i in range(5)]),'array')
    for method in ['bh','bonferroni']:a=c.add('adjust_'+method,'AdjustPValues',{'p_values':N(e,'/p_values'),'method':V(method)});c.out('q_'+method,N(a,'/adjusted_p_values'),'array')
    return c.emit()


def transient_ecology():
    c=Case(85,'Biology','intermediate','Transient ecological amplification versus a chosen pulse response',
      'Three explicitly stipulated linearized ecological interaction matrices are stable upper-triangular toy models (their diagonal rates are negative). At times0.5 and2 report response_short_a etc. and response_long_a etc.=exp(tJ) times the supplied pulse, and gain_short_a etc.,gain_long_a etc. as the largest singular value of that propagator. Independently report symmetric_spectrum_a etc. for (J+J^T)/2. Report amplifies_short_a etc. iff gain_short>1+1e-8. A single pulse norm is not the worst-case gain, and stable diagonal eigenvalues do not rule out finite-time nonnormal amplification. Time uses the inverse-rate unit of these matrices.',
      {'jacobians':[[[-1,0,0],[0,-2,0],[0,0,-3]],[[-1,4,0],[0,-2,2],[0,0,-3]],[[-1,1,0],[0,-1.5,0],[0,0,-2]]],'pulse':[0,1,0]},
      'nonnormal_transient_response','Each interaction matrix shares its symmetric part and its two propagators across response and worst-case-gain witnesses.',
      ['Three independent model chains','At each time, one propagator feeds pulse multiplication and SVD gain'],
      'Distinguish asymptotic stability, initial energy growth and observed finite-time response.',
      'Controlled linear systems only; no real community equilibrium, intervention effect or species interaction is validated.')
    for i,k in enumerate('abc'):
        sym=matrix([[E('divide',E('add',I(f'/jacobians/{i}/{r}/{s}'),I(f'/jacobians/{i}/{s}/{r}')),V(2)) for s in range(3)] for r in range(3)]);e=c.add('symmetric_'+k,'SymmetricEigenDecomposition',{'values':sym});c.out('symmetric_spectrum_'+k,N(e,'/eigenvalues'),'array')
        for label,t in [('short',.5),('long',2.)]:
            M=matrix([[E('multiply',V(t),I(f'/jacobians/{i}/{r}/{s}')) for s in range(3)] for r in range(3)]);ex=c.add('propagator_'+label+'_'+k,'MatrixExponential',{'values':M});p=c.add('pulse_'+label+'_'+k,'MatrixMultiply',{'left':N(ex,'/exponential'),'right':I('/pulse')});svd=c.add('gain_'+label+'_'+k,'MatrixSVD',{'values':N(ex,'/exponential')});c.out('response_'+label+'_'+k,N(p,'/product'),'array');c.out('gain_'+label+'_'+k,N(svd,'/singular_values/0'))
            if label=='short':c.flag('amplifies_short_'+k,N(svd,'/singular_values/0'),'gt',V(1+1e-8))
    return c.emit()


def functional_moments():
    c=Case(86,'Biology','advanced','Equal community trait centroids can hide different functional dispersion',
      'Four communities share four taxa with two numerical traits. Population-standardize the TRAIT rows across taxa once, and row-normalize each community abundance vector. Report standardized_traits and community_weights. Compute community_mean = weights times standardized traits and community_second = weights times elementwise squared standardized traits. Report community_variance=second-minus-mean^2 per trait, and centroid_distances between community means. Independently report taxonomic_distances using Bray-Curtis on original counts. Report same_centroid_a_b within1e-9 and larger_total_variance_a_b iff sum of a variances exceeds b. Taxa are trait rows, communities are weight rows; equal centroids do not establish equal distributions or biodiversity.',
      {'traits':[[-2,-1],[-1,-2],[1,2],[2,1]],'counts':[[10,0,0,10],[0,10,10,0],[5,10,0,5],[0,5,10,5]]},
      'community_trait_first_second_moments','One taxon trait standardization and one community weighting matrix feed both moment branches.',
      ['Taxonomic geometry versus functional geometry','Community first and second moments from shared scaled traits'],
      'Preserve object domains and distributional information when centroids coincide.')
    s=c.add('scale','StandardizeNumericFeatures',{'training_features':I('/traits'),'features':I('/traits')});w=c.add('weights','NormalizeNumericRows',{'matrix':I('/counts')});sq=c.add('trait_square','ElementwiseNumericOperations',{'operation':V('multiply'),'values':N(s,'/features'),'other':N(s,'/features')});mean=c.add('mean','MatrixMultiply',{'left':N(w,'/proportions'),'right':N(s,'/features')});second=c.add('second','MatrixMultiply',{'left':N(w,'/proportions'),'right':N(sq,'/values')});d=c.add('centroid_distance','PairwiseNumericDistances',{'values':N(mean,'/product'),'metric':V('euclidean')});tax=c.add('taxonomic','PairwiseNumericDistances',{'values':I('/counts'),'metric':V('braycurtis')});variance=[[E('subtract',N(second,f'/product/{i}/{j}'),E('multiply',N(mean,f'/product/{i}/{j}'),N(mean,f'/product/{i}/{j}'))) for j in range(2)] for i in range(4)]
    for key,value in [('standardized_traits',N(s,'/features')),('community_weights',N(w,'/proportions')),('community_mean',N(mean,'/product')),('community_second',N(second,'/product')),('community_variance',matrix(variance)),('centroid_distances',N(d,'/distances')),('taxonomic_distances',N(tax,'/distances'))]:c.out(key,value,'array')
    c.flag('same_centroid_a_b',N(mean,'/product/0'),'eq',N(mean,'/product/1'));c.flag('larger_total_variance_a_b',E('sum',vector(*variance[0])),'gt',E('sum',vector(*variance[1])));return c.emit()


def allometry_uncertainty():
    c=Case(87,'Biology','intermediate','Allometric fit uncertainty depends on the meaning of sigma',
      'Positive size and biomass observations define a synthetic power-law calibration. Fit four power_law models y=a*x^b, initial[1,1], bounds a[0,20],b[0,4],linear loss,max_evaluations2000: unweighted; absolute sigma; absolute doubled sigma; relative doubled sigma. Report parameters_k,parameter_covariance_k and predictions_k at query_x for k=unweighted,absolute,doubled_absolute,doubled_relative. Report absolute_scale_ratios as the two diagonal entries of doubled_absolute covariance divided by absolute covariance. Scaling known absolute measurement SD differs from a relative weighting convention; convergence and tiny residuals do not prove biological generality. Do not pool query rows into fitting.',
      {'x':[1,2,3,4,5,6],'y':[1.4,3.2,5.7,8.1,11.9,15.7],'sigma':[.1,.2,.25,.4,.6,.8],'query_x':[1.5,3.5,5.5]},
      'allometric_weight_vs_absolute_noise','One training/query split and physical noise convention anchor four estimation branches.',
      ['Four independent fits with explicitly different sigma semantics','Each fitted artifact feeds query prediction and covariance interpretation'],
      'Keep point predictions, relative weights and absolute uncertainty calibration separate.',
      'Synthetic regression calibration only; no organism growth law or confidence-interval coverage is established.')
    for label,sigma,absolute in [('unweighted',None,False),('absolute',c.inputs['sigma'],True),('doubled_absolute',[2*v for v in c.inputs['sigma']],True),('doubled_relative',[2*v for v in c.inputs['sigma']],False)]:
        f=c.add('fit_'+label,'FitParametricCurve',{'x':I('/x'),'y':I('/y'),'model_type':V('power_law'),'initial_parameters':V([1.,1.]),'lower_bounds':V([0.,0.]),'upper_bounds':V([20.,4.]),'sigma':V(sigma),'absolute_sigma':V(absolute),'loss':V('linear'),'max_evaluations':V(2000)});p=c.add('predict_'+label,'EvaluateParametricCurve',{'model':N(f,'/model'),'x':I('/query_x')});c.out('parameters_'+label,N(f,'/model/parameters'),'array');c.out('parameter_covariance_'+label,N(f,'/parameter_covariance'),'array');c.out('predictions_'+label,N(p,'/predictions'),'array')
    c.out('absolute_scale_ratios',vector(*[E('divide',N('fit_doubled_absolute',f'/parameter_covariance/{i}/{i}'),N('fit_absolute',f'/parameter_covariance/{i}/{i}')) for i in range(2)]),'array');return c.emit()


def build():return [stratified_endpoints(),distance_embeddability(),rarefaction(),tree_scale(),complete_case(),detection_reliability(),oriented_qc(),diversity_partition(),common_core_geometry(),ontology_evidence(),transient_ecology(),functional_moments(),allometry_uncertainty()]
