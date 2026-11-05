"""Hand-authored benign observational biology studies; fixtures are synthetic.

No reference answers are calculated here. Evaluators compare answers to trusted
scientific observations, never to an author-generated numerical answer table.
"""
import json


def build():
    specs = []

    def study(number, title, question, data, calls, case=False, repair='None required; malformed values must not be silently imputed.'):
        if any(c[1] in ('BootstrapMeanInterval', 'GroupedBootstrapMeanInterval') for c in calls):
            data = dict(data, bootstrap_settings={'confidence': 0.95, 'resamples': 1000, 'seed': 17, 'interval': 'central percentile'})
        sid = f'SMAS-{number:04d}'
        basename = sid + '_study.json'
        nodes = [{'id':'records','required':False,'alternatives':[{'tools':['ParseJSONDocument'], 'output_rules':[{'path':'/document','op':'eq','value':data}]}]}]
        properties, outcomes = {}, []
        instructions = []
        for name, tool, arguments, reports in calls:
            deps = []
            rules = []
            for key, value in arguments.items():
                if isinstance(value, tuple):
                    source, path = value
                    deps.append(source)
                    rules.append({'left':{'source':'call_arguments','path':'/'+key},'op':'eq','right':{'source':'node','node':source,'path':path},'atol':1e-12,'rtol':1e-10})
                else:
                    rules.append({'path':'/'+key,'op':'eq','value':value})
            output_rules=[]
            for field, typ in reports.items():
                answer_key = name + '_' + field
                properties[answer_key] = {'type':typ}
                output_rules.append({'path':'/'+field,'op':'type','value':typ})
                outcomes.append({'id':answer_key,'left':{'source':'answer','path':'/'+answer_key},'op':'eq','right':{'source':'node','node':name,'path':'/'+field},'atol':1e-8,'rtol':1e-6,'evidence_nodes':[name]})
            nodes.append({'id':name,'depends_on':list(dict.fromkeys(deps)),'alternatives':[{'tools':[tool],'input_rules':rules,'output_rules':output_rules}]})
            instructions.append(name + ': ' + ', '.join(reports))
        branches = []
        def observed(node, field):
            return {'source': 'node', 'node': node, 'path': '/' + field}
        def operation(name, *args):
            return {'operation': name, 'args': list(args)}
        def decision(name, left, op, right, evidence):
            properties[name] = {'type': 'boolean'}
            opposite = {'lt':'ge', 'gt':'le'}[op]
            for value, test in ((True, op), (False, opposite)):
                branch = name + ('_yes' if value else '_no')
                branches.append({'id': branch, 'when': {'left': left, 'op': test, 'right': right}})
                outcomes.append({'id': branch, 'branch': branch, 'left': {'source':'answer','path':'/'+name}, 'op':'eq', 'value':value, 'evidence_nodes':evidence})
        if number == 27:
            question += ' Decide whether the taxon trait association meets the prespecified unadjusted two-sided permutation threshold p<0.05; report taxon_trait_permutation_supported as a boolean. Also report plot2_more_even_than_plot4 as a boolean using Shannon diversity, since both plots contain all four taxa.'
            decision('taxon_trait_permutation_supported', observed('phylo_trait','p_value'), 'lt', {'value':0.05}, ['phylo_trait'])
            decision('plot2_more_even_than_plot4', observed('plot2','shannon_nats'), 'gt', observed('plot4','shannon_nats'), ['plot2','plot4'])
        if number == 28:
            question += ' Report plot_change_interval_above_zero as a boolean indicating whether the lower grouped-bootstrap bound is strictly positive. Report naive_change_interval_narrower as a boolean comparing the naive and grouped change interval widths. Neither decision validates independence of quadrats.'
            decision('plot_change_interval_above_zero', observed('change_plot','interval/0'), 'gt', {'value':0}, ['change_plot'])
            naive_width = operation('subtract', observed('change_quadrat','upper'), observed('change_quadrat','lower'))
            plot_width = operation('subtract', observed('change_plot','interval/1'), observed('change_plot','interval/0'))
            decision('naive_change_interval_narrower', naive_width, 'lt', plot_width, ['change_quadrat','change_plot'])
        schema={'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
        inputs={'study_file':'asset://'+basename}
        task={'id':sid,'domain':'Biology','question':title+'. '+question+' The attachment is a deliberately synthetic observational fixture, not a field dataset. Preserve its stated object/category order and units. Return a flat JSON object using the following named analyses and fields (prefix each field with the analysis name and underscore): '+ '; '.join(instructions)+'. '+'Use the declared seed and resampling conventions. No external information is needed.', 'inputs':inputs,'files':list(inputs.values()),'answer_schema':schema,'question_language':'en','Parameter':json.dumps(inputs,sort_keys=True),'unit_annotations':[]}
        specs.append({'task':task,'evaluation':{'schema_version':'workflow.v1','nodes':nodes,'outcomes':outcomes,'branches':branches,'efficiency':{'free_recovery_calls':2,'free_disambiguation_calls':2}},'design':{'scientific_goal':title,'parallel_branches':[n['id'] for n in nodes if n['id']!='records' and not n['depends_on']],'shared_preprocessing':'Read one study document by any legitimate route and preserve named rows, sampling units and taxon order; JSON parsing is optional evidence and literal scientific arguments independently pin fixture identity.','early_stop_logic':'No expensive predictive follow-up is warranted; all requested descriptive branches remain reportable. '+('QC failures screen only the affected record; unaffected records and original QC must still be reported.' if 'QC' in title else 'Do not convert negative association or a broad interval into missing evidence.'),'repair_opportunity':repair,'case_study':case,'source_notes':'All numerical, abundance, sequence, and Newick fixtures are synthetic teaching data. Sequence strings have no asserted natural origin or biological function. Methods follow the local documented tool contracts; no external factual claims.'},'assets':{basename:data}})

    def call(name, tool, args, **reports): return (name,tool,args,reports)
    def div(name, counts): return call(name,'DiversityIndices',{'counts':counts},total='number',richness='number',shannon_nats='number',gini_simpson='number')
    def dist(name, rows, metric): return call(name,'PairwiseNumericDistances',{'values':rows,'metric':metric},distances='array')
    def boot(name, values, grouped=None):
        args={'values':values,'confidence':0.95,'resamples':1000,'seed':17}
        if grouped is None: return call(name,'BootstrapMeanInterval',args,mean='number',lower='number',upper='number')
        args['groups']=grouped
        return call(name,'GroupedBootstrapMeanInterval',args,mean='number',interval='array',group_count='number')
    def mantel(name,a,b): return call(name,'MantelCorrelation',{'distance_a':(a,'/distances'),'distance_b':(b,'/distances'),'permutations':199,'seed':17,'alternative':'two-sided'},correlation='number',p_value='number',object_count='number')

    abundance=[[18,2,0,0],[5,5,5,5],[0,0,9,11],[9,1,8,2]]
    tree='((A:0.2,B:0.3):0.4,(C:0.1,D:0.5):0.6);'
    traits=[[1,2],[1.4,2.2],[3.2,1],[2.9,0.6]]
    calls=[div('plot'+str(i+1),v) for i,v in enumerate(abundance)]
    calls += [call('tree','ParseNewickTreeDistances',{'newick_text':tree},patristic_distances='array',total_branch_length='number'),dist('traits',traits,'euclidean'),dist('composition',abundance,'braycurtis'),call('phylo_trait','MantelCorrelation',{'distance_a':('tree','/patristic_distances'),'distance_b':('traits','/distances'),'permutations':199,'seed':17,'alternative':'two-sided'},correlation='number',p_value='number')]
    study(27,'Taxonomic evenness versus phylogenetic trait structure','Four equal-effort plots contain counts of taxa A–D. Separately, assess trait divergence among those taxa using their supplied rooted tree in arbitrary branch units and two dimensionless standardized traits. Plot rows and taxon rows represent different objects: do not correlate the plot composition matrix with the taxon tree. Report plug-in diversity for every plot, between-plot Bray–Curtis dissimilarity, the taxon tree distances and total edge length, Euclidean trait distances, and the taxon-level Pearson triangle correlation with 199 unrestricted label draws. Exchangeability is stipulated only for this synthetic taxon comparison; it is not a causal model.',{'taxa':['A','B','C','D'],'plot_counts':abundance,'newick':tree,'traits':traits,'permutations':199,'seed':17},calls,True)

    v=[3,4,5,12,14,8,9,10,11,2,3,4];g=['P1']*3+['P2']*2+['P3']*4+['P4']*3
    b=[2,3,4,9,10,6,7,8,8,1,2,3];delta=[x-y for x,y in zip(v,b)]
    study(28,'Sampling uncertainty with unequal within-plot effort','Plant cover changes are recorded at repeated quadrats nested within four independent plots. Quadrats within a plot are dependent. Estimate the equal-plot-weight mean and percentile bootstrap interval for before, after, and paired change by resampling plot means. As an explicitly labelled sensitivity analysis also calculate the naive equal-quadrat bootstrap for these same three vectors. Use 1000 resamples, seed 17, central 95% intervals. Summarize each plot’s supplied species counts. The naive result does not substitute for the declared plot-level estimand.',{'before':b,'after':v,'change':delta,'plot':g,'species_counts':[[2,3,1],[5,0,1]],'resamples':1000,'seed':17},[boot('before_plot',b,g),boot('after_plot',v,g),boot('change_plot',delta,g),boot('before_quadrat',b),boot('after_quadrat',v),boot('change_quadrat',delta),div('upland',[2,3,1]),div('lowland',[5,0,1])],True)

    rows=[[8,2,0,0],[0,3,7,0],[1,1,2,6],[4,4,1,1]]; binary=[[int(x>0) for x in r] for r in rows]
    study(29,'Detection turnover versus dominance','Compare four equal-area insect observation lists. Report each list’s diversity, Bray–Curtis dissimilarities from counts, Jaccard dissimilarities from presence indicators, and the two-sided triangle association between these two matrices. Also report Euclidean distances between supplied sampling-hour and temperature standardized covariates. Presence is observed detection, not verified absence; no occupancy correction is available.',{'counts':rows,'presence':binary,'covariates':[[0,1],[1,0],[2,0],[0,2]],'permutations':199,'seed':17},[*[div('list'+str(i+1),r) for i,r in enumerate(rows)],dist('abundance',rows,'braycurtis'),dist('presence',binary,'jaccard'),mantel('agreement','abundance','presence'),dist('conditions',[[0,1],[1,0],[2,0],[0,2]],'euclidean')])

    rows=[[20,4,1],[17,6,2],[10,10,5],[5,12,8]];relative=[[x/sum(r) for x in r] for r in rows]
    study(30,'Seasonal composition under changing observation totals','Four seasonal bird censuses are repeated observations of one marsh. Report each census diversity, Bray–Curtis distances using raw counts and using each row divided by its total, the matrix association as descriptive only (zero permutations), and bootstrap intervals for the supplied independent observer calibration counts. Do not treat seasons as independent randomized sites.',{'counts':rows,'relative':relative,'calibration':[8,11,9,12,10,7,13,10]},[*[div('season'+str(i+1),r) for i,r in enumerate(rows)],dist('raw',rows,'braycurtis'),dist('relative',relative,'braycurtis'),call('agreement','MantelCorrelation',{'distance_a':('raw','/distances'),'distance_b':('relative','/distances'),'permutations':0,'seed':17,'alternative':'two-sided'},correlation='number'),boot('calibration',[8,11,9,12,10,7,13,10])])

    guild=[[4,3,1],[2,7,1],[0,2,8],[5,1,4]];env=[[0,1],[1,0],[2,2],[3,1]]
    study(31,'Guild composition and environmental geometry','Four independent synthetic ponds have three feeding-guild counts and standardized depth and canopy values. Report diversity per pond, Bray–Curtis guild differences, Euclidean environmental differences, their unrestricted two-sided label association, and cityblock environmental distances as a geometric sensitivity analysis. This is an association check without causal attribution.',{'guild_counts':guild,'environment':env,'permutations':199,'seed':17},[*[div('pond'+str(i+1),r) for i,r in enumerate(guild)],dist('guild',guild,'braycurtis'),dist('environment',env,'euclidean'),mantel('association','guild','environment'),dist('cityblock',env,'cityblock')])

    trees=['((A:1,B:2):3,(C:2,D:4):1);','(A:1,B:2,(C:2,D:4):4);']
    study(32,'Root placement and path-length invariance','Two serializations describe the same unrooted weighted taxon tree with different serialization roots. Report each patristic matrix, root-to-tip vector and total nonroot edge length. Compare each tree matrix with Euclidean leaf-trait distances using zero-permutation triangle correlations. Also report diversity of two supplied specimen counts and cityblock trait distances. A changed root-to-tip vector alone is not evidence of evolutionary rate change.',{'trees':trees,'traits':traits,'specimen_counts':[[4,2,1,3],[1,1,7,1]]},[call('root1','ParseNewickTreeDistances',{'newick_text':trees[0]},patristic_distances='array',root_to_tip_lengths='array',total_branch_length='number'),call('root2','ParseNewickTreeDistances',{'newick_text':trees[1]},patristic_distances='array',root_to_tip_lengths='array',total_branch_length='number'),dist('traits',traits,'euclidean'),*[call('association'+str(i+1),'MantelCorrelation',{'distance_a':('root'+str(i+1),'/patristic_distances'),'distance_b':('traits','/distances'),'permutations':0,'seed':17,'alternative':'two-sided'},correlation='number') for i in range(2)],div('sample1',[4,2,1,3]),div('sample2',[1,1,7,1]),dist('cityblock',traits,'cityblock')])

    study(33,'Spatial distance and habitat confounding','Four synthetic meadow quadrats supply standardized coordinates, soil properties, and plant counts. Report pairwise Euclidean geography and soil distances, Bray–Curtis composition distance, diversity per quadrat, and descriptive zero-permutation triangle correlations of composition with geography and with soil. Spatial structure prevents an unrestricted permutation inference here; neither correlation isolates an environmental effect.',{'coordinates':[[0,0],[1,0],[2,1],[4,1]],'soil':[[0,1],[0.5,1],[2,0],[3,0]],'counts':rows},[*[div('quadrat'+str(i+1),r) for i,r in enumerate(rows)],dist('geography',[[0,0],[1,0],[2,1],[4,1]],'euclidean'),dist('soil',[[0,1],[0.5,1],[2,0],[3,0]],'euclidean'),dist('composition',rows,'braycurtis'),*[call('association_'+x,'MantelCorrelation',{'distance_a':('composition','/distances'),'distance_b':(x,'/distances'),'permutations':0,'seed':17,'alternative':'two-sided'},correlation='number') for x in ['geography','soil']]])

    study(34,'Community pooling and local diversity','Three equally sampled tree stands share four taxon columns. Report local diversity, pooled diversity from the column sums, raw Bray–Curtis and binary Jaccard distances among stands, and bootstrap intervals for independent seed-trap totals in each of two separately sampled regions. Pooling changes the observational unit and does not estimate mean local diversity.',{'stand_counts':[[9,1,0,0],[0,5,5,0],[1,0,1,8]],'pooled_counts':[10,6,6,8],'presence':[[1,1,0,0],[0,1,1,0],[1,0,1,1]],'north_traps':[1,2,4,3,5,2],'south_traps':[0,1,2,1,7,1]},[div('stand1',[9,1,0,0]),div('stand2',[0,5,5,0]),div('stand3',[1,0,1,8]),div('pooled',[10,6,6,8]),dist('counts',[[9,1,0,0],[0,5,5,0],[1,0,1,8]],'braycurtis'),dist('presence',[[1,1,0,0],[0,1,1,0],[1,0,1,1]],'jaccard'),boot('north',[1,2,4,3,5,2]),boot('south',[0,1,2,1,7,1])])

    seqs=['ACGTACGTNN--','GGCCATAT','ACGT?ACG','AAAAACCC']
    study(35,'Environmental barcode QC with an incomplete record','Four synthetic DNA fragments are observational QC controls. Report each original record’s length, canonical fraction, ambiguity and gap positions, and invalid symbols. R3 contains a transcription placeholder ?. The supplied verified source correction replaces that symbol by T, yielding ACGTTACG; report QC and composition of the corrected record as separate results. Report canonical composition of R2 and R4. R1 must retain uncertainty: do not replace N or gaps, and report its GC bounds over all nongap positions. No taxonomic identification is supported.',{'records':dict(zip(['R1','R2','R3','R4'],seqs)),'verified_R3':'ACGTTACG'},[*[call('R'+str(i+1),'SequenceQualityMetrics',{'sequence':s,'molecule_type':'DNA'},length='number',canonical_fraction='number',ambiguous_positions='array',gap_positions='array',invalid_symbols='array',**({'gc_percent_bounds_all_nongap':'array'} if i==0 else {})) for i,s in enumerate(seqs)],call('R3_corrected','SequenceQualityMetrics',{'sequence':'ACGTTACG','molecule_type':'DNA'},canonical_fraction='number',invalid_symbols='array'),*[call(n,'SequenceComposition',{'sequence':s,'molecule_type':'DNA'},length='number',fractions='object') for n,s in [('R2_composition',seqs[1]),('R3_composition','ACGTTACG'),('R4_composition',seqs[3])]]],repair='Only the documented R3 source correction ?->T is authorized. Preserve original QC evidence, ambiguity and gap coordinates; invalid text is not a negative ecological result.')

    proteins=['ACDEFGHIKLMNPQRSTVWY','AAAAAVVVVILILGG','DEDEKKRRGSTNQ','GGGSSSTTTAAAPP']
    study(36,'Benign protein composition inventory','Four short artificial canonical protein strings are measurement controls with no asserted function. For every control report sequence length, Kyte–Doolittle mean hydropathy, Ikai aliphatic index, and theoretical pI using the local Biopython method. These are sequence descriptors rather than experimental solubility, thermostability or titration measurements. Do not propose mutations or biological uses.',{'controls':dict(zip(['C1','C2','C3','C4'],proteins))},[c for i,s in enumerate(proteins) for c in [call('C'+str(i+1)+'_hydropathy','ProteinGRAVY',{'sequence':s},gravy='number',sequence_length='number'),call('C'+str(i+1)+'_aliphatic','ProteinAliphaticIndex',{'sequence':s},aliphatic_index='number'),call('C'+str(i+1)+'_pI','ProteinIsoelectricPointCalculator',{'sequence':s,'method':'biopython'},pI='number')]])

    rna=['ACGUACGU','GGCCNNRY','AAAAUUUU','CCGG--NN']
    study(37,'RNA fragment uncertainty and denominator audit','Four artificial RNA fragment controls vary in ambiguity and gaps. For each report normalized length, nongap length, canonical fraction and all-nongap GC bounds. For canonical controls U1 and U3 also report full canonical symbol fractions. Report Euclidean and cityblock distances between the supplied two-feature canonical AU-count and GC-count summaries in record order; these summaries are illustrative and their distances do not incorporate ambiguity bounds. Avoid treating known-base GC as total-fragment GC.',{'records':dict(zip(['U1','U2','U3','U4'],rna)),'known_base_summaries':[[4,4],[0,4],[8,0],[0,4]]},[*[call('U'+str(i+1),'SequenceQualityMetrics',{'sequence':s,'molecule_type':'RNA'},length='number',nongap_length='number',canonical_fraction='number',gc_percent_bounds_all_nongap='array') for i,s in enumerate(rna)],*[call(n,'SequenceComposition',{'sequence':s,'molecule_type':'RNA'},fractions='object') for n,s in [('U1_composition',rna[0]),('U3_composition',rna[2])]],dist('euclidean',[[4,4],[0,4],[8,0],[0,4]],'euclidean'),dist('cityblock',[[4,4],[0,4],[8,0],[0,4]],'cityblock')])

    study(38,'Independent plot growth and rank sensitivity','Eight independently sampled seedling plots have standardized moisture and measured annual height increment in cm. Report Pearson and Spearman correlations between moisture and growth, and between moisture and the prespecified monotone growth score; bootstrap mean intervals for growth and score using 1000 resamples and seed 17; and diversity for each of two nursery source-count vectors. The score is ordinal and its arithmetic mean is only a scale-specific description. Correlations do not establish a moisture intervention effect.',{'moisture':[1,2,3,4,5,6,7,8],'growth_cm':[1,2,2,3,4,5,7,15],'ordinal_score':[1,2,2,3,4,5,6,7],'nursery_counts':[[5,3,2],[8,1,1]]},[*[call(label+'_'+method.lower(),method+'Correlation',{'x':[1,2,3,4,5,6,7,8],'y':y},correlation='number',p_value='number',count='number') for label,y in [('growth',[1,2,2,3,4,5,7,15]),('score',[1,2,2,3,4,5,6,7])] for method in ['Pearson','Spearman']],boot('growth',[1,2,2,3,4,5,7,15]),boot('score',[1,2,2,3,4,5,6,7]),div('nursery1',[5,3,2]),div('nursery2',[8,1,1])])
    return specs
