"""Individually revised orchestration studies; no numerical answers or fake calls.

All targets remain expressions over real registered scientific observations.
"""
from copy import deepcopy
from machine_learning import Study, V, I, N, E, refs

REVISED_IDS={f'SMAS-{n:04d}' for n in [4,5,6,7,8,9,10,11,30,31,32,33,34,37,38]}


def boolean(s,key,left,operator,right,evidence=None,atol=1e-9):
    inverse={'eq':'ne','ne':'eq','gt':'le','ge':'lt','lt':'ge','le':'gt'}
    for suffix,op,value in [('yes',operator,True),('no',inverse[operator],False)]:
        branch=key+'_'+suffix
        s.branches.append({'id':branch,'when':{'left':left,'op':op,'right':right,'atol':atol,'rtol':atol}})
        s.out(key,V(value),'boolean',evidence or sorted(set(refs([left,right]))),branch)


def finish(s,domain,shared,parallel,stop='All requested evidence branches must be completed.',repair='None required.'):
    row=s.finish(shared,parallel,stop,repair);row['task']['domain']=domain
    row['design']['source_notes']='Explicit synthetic computational fixture; targets derive from actual local registered observations. No empirical or causal property claims. Individually reviewed scientific purpose and fork/join structure.'
    return row


def identity(s,label,path,fragment='keep_all',tautomer='preserve'):
    return s.add(label,'CanonicalMolecularIdentity',{'smiles':I(path),'fragment_policy':V(fragment),'tautomer_policy':V(tautomer),'keep_stereo':V(True)})


def descriptor(s,label,tool,identity_node,field='value',**kwargs):
    return s.add(label,tool,{'smiles':N(identity_node,'/canonical_smiles')},**kwargs)


def build_chemistry():
    out=[]
    # 4: a genuine two-stage structural gate, with cheap evidence retained for every record.
    s=Study(4,'Two-stage linker eligibility audit','Three synthetic linker candidates are supplied. Preserve all components, tautomers and stereo. For each record a,b,c report canonical_a etc., aromatic_rings_a etc. and strict rotatable_bonds_a etc. A linker is eligible iff aromatic rings >=2 AND strict rotatable bonds <=2. Report eligible_a etc. Only eligible graphs need average molar mass mass_a etc. (g/mol) and TPSA tpsa_a etc. (angstrom^2); report null for both follow-up fields for rejected candidates. This is a graph inventory rule, not a stiffness or permeability prediction.',{'smiles':['c1ccccc1CCc1ccccc1','c1ccc(-c2ccccc2)cc1','c1ccccc1CCO']})
    for i,k in enumerate('abc'):
        n=identity(s,'identity_'+k,f'/smiles/{i}');s.out('canonical_'+k,N(n,'/canonical_smiles'),'string')
        ring=descriptor(s,'rings_'+k,'GetAromaticRingsNum',n);rot=descriptor(s,'rot_'+k,'GetRotatableBondsNum',n)
        s.out('aromatic_rings_'+k,N(ring,'/value'));s.out('rotatable_bonds_'+k,N(rot,'/value'))
        gate=E('min',E('array',E('subtract',N(ring,'/value'),V(2)),E('subtract',V(2),N(rot,'/value'))))
        for suffix,op,value in [('yes','ge',True),('no','lt',False)]:
            b='eligible_'+k+'_'+suffix
            s.branches.append({'id':b,'when':{'left':gate,'op':op,'value':0}})
            s.out('eligible_'+k,V(value),'boolean',[ring,rot],b)
            if value:
                m=descriptor(s,'mass_'+k,'SMILESToWeight',n,parents=[ring,rot],branch=b);p=descriptor(s,'tpsa_'+k,'CalculateTPSA',n,parents=[ring,rot],branch=b)
                s.out('mass_'+k,N(m,'/molar_mass'),['number','null'],[n,ring,rot,m],b);s.out('tpsa_'+k,N(p,'/value'),['number','null'],[n,ring,rot,p],b)
            else:
                s.out('mass_'+k,V(None),['number','null'],[ring,rot],b);s.out('tpsa_'+k,V(None),['number','null'],[ring,rot],b)
    out.append(finish(s,'Chemical','Each preserved molecular identity feeds both independent gates and any accepted follow-up.','Different candidates and each candidate\'s two gate measurements can proceed independently.','After valid gate failure, omit that candidate\'s optional mass/TPSA; complete both gate measurements.'))
    # 5: policy comparison shares original graphs without conflating tautomer canonicalization with populations.
    s=Study(5,'Tautomer-policy identity reconciliation','For each submitted graph a,b,c compute canonical isomeric SMILES under two policies: tautomer preserve versus RDKit canonical tautomer; retain all fragments and stereo in both. Report preserve_a etc., tautomer_canonical_a etc., and the average molar masses mass_preserve_a etc. and mass_canonical_a etc. in g/mol. Report changed_a etc. indicating whether the two canonical SMILES differ exactly. Report preserved_pair_same comparing preserved a/b, and canonical_pair_same comparing canonical-tautomer a/b. These are representation-policy results, not solution tautomer abundances.',{'smiles':['CC(=O)CC(=O)C','CC(O)=CC(=O)C','CCCO']},True)
    saved={}
    for i,k in enumerate('abc'):
        for policy,tag in [('preserve','preserve'),('canonical','canonical')]:
            n=identity(s,tag+'_'+k,f'/smiles/{i}',tautomer=policy);saved[tag+k]=n
            s.out(('preserve_' if tag=='preserve' else 'tautomer_canonical_')+k,N(n,'/canonical_smiles'),'string')
            m=descriptor(s,'mass_'+tag+'_'+k,'SMILESToWeight',n);s.out('mass_'+tag+'_'+k,N(m,'/molar_mass'))
        boolean(s,'changed_'+k,N(saved['preserve'+k],'/canonical_smiles'),'ne',N(saved['canonical'+k],'/canonical_smiles'))
    for tag in ['preserve','canonical']:boolean(s,tag+'d_pair_same' if tag=='preserve' else 'canonical_pair_same',N(saved[tag+'a'],'/canonical_smiles'),'eq',N(saved[tag+'b'],'/canonical_smiles'))
    out.append(finish(s,'Chemical','Original records anchor two separate identity policies; each result is reused by mass and equality checks.','Policy-specific identity/mass chains and molecular records are independent; equality checks join them.'))
    # 6: a common baseline is scientifically shared rather than recalculated once per contrast.
    s=Study(6,'Matched functional-group contrast accounting','A common baseline and three replacements a,b,c are a graph-descriptor sensitivity panel. Retain all components, tautomers and stereo. Report canonical_base, canonical_a,b,c; average molar masses mass_base,mass_a,b,c (g/mol), TPSA tpsa_base,tpsa_a,b,c (angstrom^2). For each replacement report delta_mass_a etc. and delta_tpsa_a etc. = replacement minus the SAME baseline; select all largest delta_TPSA IDs as selected. This is a matched inventory contrast, not a prediction of absorption.',{'baseline':'CC(=O)NCC','smiles':['CCOC(=O)NCC','CCS(=O)(=O)NCC','CCNCC']})
    nodes={}
    for label,path in [('base','/baseline'),*[(k,f'/smiles/{i}') for i,k in enumerate('abc')]]:
        n=identity(s,'identity_'+label,path);m=descriptor(s,'mass_'+label,'SMILESToWeight',n);p=descriptor(s,'tpsa_'+label,'CalculateTPSA',n);nodes[label]=(m,p)
        s.out('canonical_'+label,N(n,'/canonical_smiles'),'string');s.out('mass_'+label,N(m,'/molar_mass'));s.out('tpsa_'+label,N(p,'/value'))
    changes=[]
    for k in 'abc':
        m,p=nodes[k];base_m,base_p=nodes['base'];s.out('delta_mass_'+k,E('subtract',N(m,'/molar_mass'),N(base_m,'/molar_mass')))
        change=E('subtract',N(p,'/value'),N(base_p,'/value'));changes.append(change);s.out('delta_tpsa_'+k,change)
    s.selection('selected',list('abc'),changes,maximize=True)
    out.append(finish(s,'Chemical','One measured baseline supports every replacement contrast.','Each distinct graph has independent mass and polarity measurements; contrasts join the shared baseline.'))
    # 7: formal charge applies to the selected fragment, not a neutralized invention.
    s=Study(7,'Charge-domain screening of submitted fragments','For each record a,b,c select the largest organic component, preserve tautomer/stereo and DO NOT neutralize. Report canonical_a etc., charge_a etc. and neutral_a etc. For selected fragments with formal charge exactly zero, report H-bond donor counts donors_a etc. and acceptor counts acceptors_a etc.; for nonzero charge report null for those two optional fields. This is an explicit neutral-graph descriptor panel, not a prediction of pH speciation.',{'smiles':['NCCO','C[NH2+]CCO.[Cl-]','CN(C)CCO']})
    for i,k in enumerate('abc'):
        n=identity(s,'identity_'+k,f'/smiles/{i}','largest_organic');s.out('canonical_'+k,N(n,'/canonical_smiles'),'string');s.out('charge_'+k,N(n,'/formal_charge'))
        for suffix,op,flag in [('yes','eq',True),('no','ne',False)]:
            b=s.branch('neutral_'+k+'_'+suffix,n,'/formal_charge',op,0);s.out('neutral_'+k,V(flag),'boolean',[n],b)
            for key,tool in [('donors','GetHBDNum'),('acceptors','GetHBANum')]:
                if flag:
                    d=descriptor(s,key+'_'+k,tool,n,branch=b);s.out(key+'_'+k,N(d,'/value'),['number','null'],[n,d],b)
                else:s.out(key+'_'+k,V(None),['number','null'],[n],b)
    out.append(finish(s,'Chemical','The same selected fragment establishes charge and feeds both valid descriptor branches.','Candidate identity checks are independent; accepted donor and acceptor analyses fork.','Nonzero selected-fragment charge stops both neutral-only follow-ups.'))
    # 8: alternate representations must be compared using identical molecular objects.
    s=Study(8,'Fingerprint-dependent neighborhood audit','Preserve every supplied graph, tautomer and stereo. Record order is reference benzene then candidates a,b,c. Report canonical_smiles in this order. Compute full Tanimoto SIMILARITY matrices morgan_matrix with radius=2,bits=2048,chirality=false,features=false and maccs_matrix using default MACCS settings. Return neighbor_morgan_a etc. and neighbor_maccs_a etc. indicating similarity to record 0 >=0.30, including equality. Do not equate fingerprint similarity with identity or experimental packing.',{'smiles':['c1ccccc1','c1ccncc1','c1ccc2ccccc2c1','C1CCNCC1']})
    ns=[identity(s,'identity_'+str(i),f'/smiles/{i}') for i in range(4)];graphs=E('scalar_array',*[N(n,'/canonical_smiles') for n in ns]);s.out('canonical_smiles',graphs,'array')
    for tag,options in [('morgan',{'radius':2,'bits':2048,'chirality':False,'features':False}),('maccs',{})]:
        n=s.add(tag,'CompareMolecularFingerprints',{'smiles_list':graphs,'algorithm':V(tag),'options':V(options),'metric':V('tanimoto'),'distance':V(False)})
        s.out(tag+'_matrix',N(n,'/matrix'),'array')
        for i,k in enumerate('abc',1):boolean(s,'neighbor_'+tag+'_'+k,N(n,f'/matrix/0/{i}'),'ge',V(.30))
    out.append(finish(s,'Chemical','Canonical graph order is shared by both incompatible fingerprint protocols.','Two fingerprint matrices are independent after identity collection; final neighborhoods are compared on the same objects.'))
    # 9: explicit topology categories, avoiding arbitrary descriptor arithmetic.
    s=Study(9,'Ring-junction topology classification','For each preserved graph a,b,c report canonical_a etc., spiro_atoms_a etc. and bridgehead_atoms_a etc. Independently report spiro_present_a etc. and bridgehead_present_a etc. using strictly positive respective counts. Categories are not assumed mutually exclusive. Return selected as all record IDs tied for maximum spiro count. These are RDKit graph-topology conventions, not conformational freedom or physical rigidity.',{'smiles':['C1CCC2(CC1)CCCC2','C1CC2CCC1C2','C1CCC2CCCCC2C1']})
    counts=[]
    for i,k in enumerate('abc'):
        n=identity(s,'identity_'+k,f'/smiles/{i}');s.out('canonical_'+k,N(n,'/canonical_smiles'),'string')
        for tag,tool in [('spiro','GetSpiroAtomsNum'),('bridgehead','GetBridgeheadAtomsNum')]:
            d=descriptor(s,tag+'_'+k,tool,n);s.out(tag+'_atoms_'+k,N(d,'/value'));boolean(s,tag+'_present_'+k,N(d,'/value'),'gt',V(0))
            if tag=='spiro':counts.append(N(d,'/value'))
    s.selection('selected',list('abc'),counts,maximize=True)
    out.append(finish(s,'Chemical','One molecular identity anchors both independent topology conventions.','Candidate graphs and spiro/bridgehead measurements can proceed independently before collection.'))
    # 10: same-object reuse is allowed by exact canonical graph identity, not by similar names.
    s=Study(10,'Duplicate-record identity and inventory audit','The submitted records a,b,c,d may encode repeated selected organic graphs. Select largest organic components, preserve tautomers/stereo and do not neutralize. For each record report canonical_a etc., average molar mass mass_a etc. (g/mol), TPSA tpsa_a etc. (angstrom^2). Report same_a_b and same_c_d by exact canonical-SMILES equality. Chemically identical selected graphs may share descriptor observations; different charged graphs may not. Whole-salt masses are not requested.',{'smiles':['CCO','OCC','CC(=O)[O-].[Na+]','CC(=O)[O-]']})
    ns={}
    for i,k in enumerate('abcd'):
        n=identity(s,'identity_'+k,f'/smiles/{i}','largest_organic');ns[k]=n;s.out('canonical_'+k,N(n,'/canonical_smiles'),'string')
        for tag,tool,port in [('mass','SMILESToWeight','molar_mass'),('tpsa','CalculateTPSA','value')]:
            d=descriptor(s,tag+'_'+k,tool,n);s.nodes[-1]['observation_reuse_group']='same_exact_graph_'+tag;s.out(tag+'_'+k,N(d,'/'+port))
    for a,b in [('a','b'),('c','d')]:boolean(s,'same_'+a+'_'+b,N(ns[a],'/canonical_smiles'),'eq',N(ns[b],'/canonical_smiles'))
    out.append(finish(s,'Chemical','Exact selected identity permits repeated records to consume the same validated mass/TPSA observation.','Distinct graph groups and mass/TPSA branches are independent; input-record outputs preserve their identities.'))
    # 11: a multi-hop interface chain plus an independent mass-conservation check.
    s=Study(11,'Representation round-trip with a mass witness','For each supplied neutral graph a,b,c first preserve all components, tautomers and stereo. Report canonical_a etc., standard InChI inchi_a etc., recovered canonical isomeric SMILES recovered_a etc. after InChI-to-SMILES, and exact-string roundtrip_same_a etc. Report average molar masses mass_before_a etc. and mass_after_a etc. (g/mol), plus delta_mass_a etc. = after minus before. Preserve all observations even if a round-trip representation differs; do not silently replace the input.',{'smiles':['CC(=O)NCC','CCOC(=O)NCC','CCNCCOCC']})
    for i,k in enumerate('abc'):
        n=identity(s,'identity_'+k,f'/smiles/{i}');inchi=s.add('inchi_'+k,'SMILESToInChI',{'smiles':N(n,'/canonical_smiles')});back=s.add('back_'+k,'InChIToSMILES',{'inchi':N(inchi,'/inchi')})
        before=descriptor(s,'mass_before_'+k,'SMILESToWeight',n);after=s.add('mass_after_'+k,'SMILESToWeight',{'smiles':N(back,'/smiles')})
        s.out('canonical_'+k,N(n,'/canonical_smiles'),'string');s.out('inchi_'+k,N(inchi,'/inchi'),'string');s.out('recovered_'+k,N(back,'/smiles'),'string')
        for tag,node in [('before',before),('after',after)]:s.out('mass_'+tag+'_'+k,N(node,'/molar_mass'))
        s.out('delta_mass_'+k,E('subtract',N(after,'/molar_mass'),N(before,'/molar_mass')));boolean(s,'roundtrip_same_'+k,N(n,'/canonical_smiles'),'eq',N(back,'/smiles'))
    out.append(finish(s,'Chemical','A preserved input identity anchors the conversion chain and the independent initial-mass witness.','Different records and each input-mass witness can progress while representation round-trips execute.'))
    return out


def build_biology(original):
    replacements=[]
    # Reuse legitimate local fixture/method definitions, remove unrelated panels,
    # then add scientifically meaningful joins checked against real observations.
    settings={
      30:({'calibration'},'Seasonal normalization sensitivity','Four bird censuses are repeated observations of one synthetic marsh. Report season1..season4 diversity fields (total,richness,shannon_nats,gini_simpson); raw_distances and relative_distances (Bray-Curtis using counts and row-total-normalized counts); agreement_correlation (zero permutations, descriptive). Also report relative_agrees_with_raw indicating agreement_correlation >=0.95, and season2_more_even_than_season4 comparing Shannon values strictly. Do not treat seasons as independent randomized sites or infer causality.'),
      31:(set(),'Guild-environment metric sensitivity','Four independent synthetic ponds have guild counts and standardized environmental covariates. Report pond1..pond4 diversity fields (total,richness,shannon_nats,gini_simpson); guild_distances (Bray-Curtis); environment_distances (Euclidean); cityblock_distances (Manhattan). For the two environmental metrics separately report association_correlation,p_value,object_count and association_cityblock_correlation,p_value,object_count against guild distances, using 199 two-sided unrestricted label draws and seed 17. Report supported_euclidean and supported_cityblock for unadjusted p<0.05. The permutation design is stipulated for this fixture; conclusions are metric sensitivity, not causal attribution.'),
      32:({'sample1','sample2','cityblock'},'Root-choice invariance with trait witnesses','Two serializations represent the same unrooted weighted taxon tree. For root1 and root2 report patristic_distances, root_to_tip_lengths,total_branch_length; report traits_distances (Euclidean) and association1_correlation,association2_correlation comparing each tree distance matrix with traits using zero permutations. Report pairwise_invariant by matrix equality within absolute+relative 1e-9 and root_to_tip_invariant by the same vector rule. Taxon order is fixed; a changed root distance does not establish evolutionary rate change.'),
      33:({'quadrat1','quadrat2','quadrat3','quadrat4'},'Descriptive spatial-confounding audit','Four synthetic meadow quadrats supply coordinates, soil properties and plant counts. Report geography_distances and soil_distances (Euclidean), composition_distances (Bray-Curtis), association_geography_correlation and association_soil_correlation (zero permutations). Report soil_association_stronger using strictly larger absolute triangle correlation. Report causal_effect_identified=false: neither descriptive comparison identifies a soil intervention effect in this spatially structured fixture. Do not produce unrestricted permutation p-values.'),
      34:({'north','south'},'Pooling changes the ecological estimand','Three equally sampled stands share four taxon columns. Report stand1,stand2,stand3 and pooled diversity fields (total,richness,shannon_nats,gini_simpson), counts_distances (Bray-Curtis) and presence_distances (binary Jaccard). Report mean_local_shannon = arithmetic mean of the three local Shannon values; pooled_exceeds_mean_local compares pooled Shannon strictly to that mean. Pooling uses column sums and changes the observational unit; pooled entropy is not the average local entropy.'),
      37:({'euclidean','cityblock'},'RNA ambiguity and denominator bounds','Four artificial RNA controls differ in ambiguity and gaps. For each U1..U4 report length,nongap_length,canonical_fraction,gc_percent_bounds_all_nongap. For canonical U1 and U3 also report U1_composition_fractions,U3_composition_fractions. Report width_U1..width_U4 as upper minus lower all-nongap GC bounds in percentage points, and selected as every U ID with the largest width (absolute tie tolerance 1e-9). Do not impute uncertain symbols or replace all-nongap bounds by known-base GC.'),
      38:({'nursery1','nursery2'},'Scale transformation and rank association','Eight independent seedling plots supply standardized moisture, annual height increment and a prespecified monotone ordinal growth score. Report growth_pearson, growth_spearman, score_pearson, score_spearman fields correlation,p_value,count; report growth_mean,lower,upper and score_mean,lower,upper from percentile mean bootstraps with 1000 resamples, seed17, confidence0.95. Report rank_correlation_invariant and linear_correlation_invariant using absolute+relative 1e-9 equality between growth and score Spearman and Pearson respectively. The ordinal mean is scale-dependent and neither association establishes an intervention effect.')}
    for old in original:
        num=int(old['task']['id'][-4:])
        if num not in settings:continue
        removed,title,question=settings[num];row=deepcopy(old);ev=row['evaluation'];inputs=next(iter(row['assets'].values()))
        # Keep only evidence required by the coherent scientific objective.
        ev['nodes']=[n for n in ev['nodes'] if n['id'] not in removed]
        ev['outcomes']=[o for o in ev['outcomes'] if not any(o['id'].startswith(n+'_') for n in removed)]
        s=Study(num,title,question,inputs,num in (32,33));s.nodes=ev['nodes'];s.outcomes=ev['outcomes'];s.branches=ev.get('branches',[])
        s.properties={k:v for k,v in row['task']['answer_schema']['properties'].items() if not any(k.startswith(n+'_') for n in removed)}
        if num==30:
            boolean(s,'relative_agrees_with_raw',N('agreement','/correlation'),'ge',V(.95));boolean(s,'season2_more_even_than_season4',N('season2','/shannon_nats'),'gt',N('season4','/shannon_nats'))
        elif num==31:
            n=s.add('association_cityblock','MantelCorrelation',{'distance_a':N('guild','/distances'),'distance_b':N('cityblock','/distances'),'permutations':V(199),'seed':V(17),'alternative':V('two-sided')})
            for key in ['correlation','p_value','object_count']:s.out('association_cityblock_'+key,N(n,'/'+key))
            boolean(s,'supported_euclidean',N('association','/p_value'),'lt',V(.05));boolean(s,'supported_cityblock',N(n,'/p_value'),'lt',V(.05))
        elif num==32:
            boolean(s,'pairwise_invariant',N('root1','/patristic_distances'),'eq',N('root2','/patristic_distances'));boolean(s,'root_to_tip_invariant',N('root1','/root_to_tip_lengths'),'eq',N('root2','/root_to_tip_lengths'))
        elif num==33:
            boolean(s,'soil_association_stronger',E('abs',N('association_soil','/correlation')),'gt',E('abs',N('association_geography','/correlation')))
            s.out('causal_effect_identified',V(False),'boolean',['association_soil','association_geography'])
        elif num==34:
            mean=E('mean',E('array',*[N('stand'+str(i),'/shannon_nats') for i in [1,2,3]]));s.out('mean_local_shannon',mean)
            boolean(s,'pooled_exceeds_mean_local',N('pooled','/shannon_nats'),'gt',mean)
        elif num==37:
            widths=[]
            for name in ['U1','U2','U3','U4']:
                width=E('subtract',N(name,'/gc_percent_bounds_all_nongap/1'),N(name,'/gc_percent_bounds_all_nongap/0'));widths.append(width);s.out('width_'+name,width)
            s.selection('selected',['U1','U2','U3','U4'],widths,maximize=True)
        elif num==38:
            boolean(s,'rank_correlation_invariant',N('growth_spearman','/correlation'),'eq',N('score_spearman','/correlation'))
            boolean(s,'linear_correlation_invariant',N('growth_pearson','/correlation'),'eq',N('score_pearson','/correlation'))
        result=finish(s,'Biology','A fixed study defines common object order, sampling units and data conventions for all evidence branches.','Independent methods or estimands progress separately; declared joins compare their scientific implications.')
        # Original raw matrices/trees are public inputs now, not hidden literal recipes.
        replacements.append(result)
    return replacements


def apply(rows):
    replacement={r['task']['id']:r for r in build_chemistry()+build_biology(rows)}
    assert set(replacement)==REVISED_IDS
    return [replacement.get(r['task']['id'],r) for r in rows]


def semantic_equivalences(row):
    """Keep molecular identity checks scientific, without forcing redundant adapters.

    Descriptor canonical SMILES and conversion metadata can establish an unchanged
    keep-all/preserve graph. Charged-fragment and tautomer-policy changes retain
    their explicit identity evidence. Alias generation does not supply answer golds.
    """
    from rdkit import Chem
    tid=row['task']['id'];ev=row['evaluation'];inputs=row['task']['inputs']
    if tid not in REVISED_IDS or row['task']['domain']!='Chemical':return
    by={n['id']:n for n in ev['nodes']}
    if tid=='SMAS-0005':
        for node in ev['nodes']:
            if node['id'].startswith('mass_'):node['observation_reuse_group']='same_exact_graph_mass'
        return
    if tid=='SMAS-0008':
        removed={n['id'] for n in ev['nodes'] if n['id'].startswith('identity_')}
        for n in ev['nodes']:
            if n['id'] in ['morgan','maccs']:
                n['depends_on']=[]
                for r in n['alternatives'][0]['input_rules']:
                    if r['path']=='/smiles_list':r['right']=I('/smiles')
                    if n['id']=='maccs' and r['path']=='/options':
                        r.pop('right',None);r['op']='one_of';r['value']=[None,{}]
        ev['nodes']=[n for n in ev['nodes'] if n['id'] not in removed]
        o=next(o for o in ev['outcomes'] if o['id']=='canonical_smiles')
        o['right']=E('scalar_array',*[N('morgan',f'/records/{i}/canonical_smiles') for i in range(4)]);o['evidence_nodes']=['morgan']
        return
    prefixes={'SMAS-0004':'rings_','SMAS-0006':'tpsa_','SMAS-0009':'spiro_','SMAS-0011':'inchi_'}
    if tid not in prefixes:return
    identities={n['id']:n for n in ev['nodes'] if n['id'].startswith('identity_')}
    mapping={n:prefixes[tid]+n.removeprefix('identity_') for n in identities}
    raw_paths={}
    for name,node in identities.items():
        r=next(r for r in node['alternatives'][0]['input_rules'] if r['path']=='/smiles')
        path=r['right']['path'];raw=inputs
        for key in path[1:].split('/'):raw=raw[int(key)] if isinstance(raw,list) else raw[key]
        canonical=Chem.MolToSmiles(Chem.MolFromSmiles(raw),isomericSmiles=True)
        raw_paths[name]=[raw] if canonical==raw else [raw,canonical]
    def replace(value):
        if isinstance(value,dict):
            if value.get('source')=='node' and value.get('node') in mapping:
                assert value.get('path')=='/canonical_smiles'
                return N(mapping[value['node']],'/canonical_smiles')
            return {k:replace(v) for k,v in value.items()}
        if isinstance(value,list):return [replace(v) for v in value]
        return value
    for node in ev['nodes']:
        if node['id'] in identities:continue
        node['depends_on']=[n for n in node.get('depends_on',[]) if n not in identities]
        for alt in node['alternatives']:
            for rule in alt.get('input_rules',[]):
                right=rule.get('right',{})
                if right.get('source')=='node' and right.get('node') in raw_paths:
                    aliases=raw_paths[right['node']];rule.pop('right');rule['op']='one_of';rule['value']=aliases
    ev['nodes']=[n for n in ev['nodes'] if n['id'] not in identities]
    ev['outcomes']=replace(ev['outcomes'])
    for outcome in ev['outcomes']:
        outcome['evidence_nodes']=list(dict.fromkeys(mapping.get(n,n) for n in outcome.get('evidence_nodes',[])))
    ev['branches']=replace(ev.get('branches',[]))
