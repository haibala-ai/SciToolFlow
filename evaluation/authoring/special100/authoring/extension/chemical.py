"""Twelve individually designed chemistry workflows; distinct scientific objects and joins."""
from .common import *


def registry():
    c=Case(51,'Chemical','advanced','Registry reconciliation with charged-parent witnesses',
      'Four raw registry records describe neutral, salt and charged forms. For each a,b,c,d select largest_organic, preserve tautomer and stereo without neutralization. Report parent_a etc., parent_charge_a etc., standard inchi_a etc. and inchikey_a etc. from that selected parent. Independently report parent_mass_a etc. (g/mol) and parent_tpsa_a etc. (angstrom^2). Report same_key_a_b and same_key_c_d, and mass_gap_c_a = parent c minus parent a. Keys and scalar equality are different identity claims: retain every record even when a key repeats.',
      {'records':['CC(=O)O','OC(C)=O','CC(=O)[O-].[Na+]','CC(=O)[O-]']},
      'charged_registry_reconciliation','Each selected parent identity anchors registration and both scalar witness branches.',
      ['Independent parent records','InChI/key chain versus mass and polar surface witnesses'],
      'Reconcile duplicate registration without conflating a neutral acid and its anion.',
      'No neutralization, pH speciation, experimental registry identity or bioactivity is inferred.')
    for i,k in enumerate('abcd'):
        n=c.add('parent_'+k,'CanonicalMolecularIdentity',{'smiles':I(f'/records/{i}'),'fragment_policy':V('largest_organic'),'tautomer_policy':V('preserve'),'keep_stereo':V(True)})
        h=c.add('inchi_'+k,'SMILESToInChI',{'smiles':N(n,'/canonical_smiles')});key=c.add('key_'+k,'InChIToInChIKey',{'inchi':N(h,'/inchi')})
        m=c.add('mass_'+k,'SMILESToWeight',{'smiles':N(n,'/canonical_smiles')});p=c.add('tpsa_'+k,'CalculateTPSA',{'smiles':N(n,'/canonical_smiles')})
        for field,target,typ in [('parent',N(n,'/canonical_smiles'),'string'),('parent_charge',N(n,'/formal_charge'),'number'),('inchi',N(h,'/inchi'),'string'),('inchikey',N(key,'/inchikey'),'string'),('parent_mass',N(m,'/molar_mass'),'number'),('parent_tpsa',N(p,'/value'),'number')]:c.out(field+'_'+k,target,typ)
    for a,b in [('a','b'),('c','d')]:c.flag('same_key_'+a+'_'+b,N('key_'+a,'/inchikey'),'eq',N('key_'+b,'/inchikey'))
    c.out('mass_gap_c_a',E('subtract',N('mass_c','/molar_mass'),N('mass_a','/molar_mass')))
    return c.emit()


def atom_diffusion():
    c=Case(52,'Chemical','intermediate','Atom-index graph heat versus molecular branching',
      'The three four-carbon graphs a,b,c are molecular graph controls. Use each hydrogen-suppressed binary bond adjacency in its original parsed atom order. Report adjacency_a etc., Laplacian spectrum spectrum_a etc., and graph-heat states heat_short_a etc. at t=0.2 and heat_long_a etc. at t=1.2: exp(-t L) times [1,0,0,0], with unnormalized L=degree-adjacency. Report mass_short_a etc. and mass_long_a etc. as sums of those states. Times are dimensionless graph parameters, not physical diffusion times. Do not rematch atom indices across graphs.',
      {'smiles':['CCCC','CC(C)C','C1CCC1'],'initial':[1,0,0,0]},
      'indexed_molecular_graph_propagation','One atom-index graph per record feeds its shared Laplacian.',
      ['Three independent molecular graph chains','Spectrum and two heat propagators from each common Laplacian'],
      'Compare topology-sensitive responses while checking conservation and source atom order.')
    for i,k in enumerate('abc'):
        a=c.add('adj_'+k,'GetAdjacencyMatrix',{'smiles':I(f'/smiles/{i}')});l=c.add('lap_'+k,'GraphLaplacian',{'adjacency':N(a,'/matrix')});e=c.add('eig_'+k,'SymmetricEigenDecomposition',{'values':N(l,'/laplacian')})
        c.out('adjacency_'+k,N(a,'/matrix'),'array');c.out('spectrum_'+k,N(e,'/eigenvalues'),'array')
        for label,t in [('short',.2),('long',1.2)]:
            scaled=matrix([[E('multiply',V(-t),N(l,f'/laplacian/{r}/{s}')) for s in range(4)] for r in range(4)])
            ex=c.add('exp_'+label+'_'+k,'MatrixExponential',{'values':scaled});p=c.add('heat_'+label+'_'+k,'MatrixMultiply',{'left':N(ex,'/exponential'),'right':I('/initial')})
            c.out('heat_'+label+'_'+k,N(p,'/product'),'array');c.out('mass_'+label+'_'+k,E('sum',N(p,'/product')))
    return c.emit()


def tautomer_queries():
    c=Case(53,'Chemical','intermediate','Literal versus tautomer-aware carbonyl evidence',
      'For a,b,c use their original graphs without protonation or fragment changes. Inspect each tautomer query and report tautomers_a etc., modified_atoms_a etc. and modified_bonds_a etc. Compare ordinary and tautomer-aware substructure queries using query SMILES CC(=O)C, query_format=smiles, max_matches=100 and use_chirality=true; report literal_a etc. and aware_a etc. as matched booleans. Independently report donors_a etc. and tpsa_a etc. (angstrom^2) for each ORIGINAL graph, not for a canonical tautomer. A tautomer-aware match does not authorize replacing the descriptor graph.',
      {'smiles':['CC(=O)C','CC(O)=C','CCCO']},
      'query_semantics_vs_property_state','The original graph is the common identity; query equivalence and original-state descriptors have separate roles.',
      ['Per-record tautomer inspection and two matching protocols','Original-graph donor and polarity measurements'],
      'Distinguish a match convention from the molecular state used to measure properties.')
    for i,k in enumerate('abc'):
        q=c.add('query_'+k,'InspectTautomerQuery',{'smiles':I(f'/smiles/{i}')})
        for key,port in [('tautomers','tautomers'),('modified_atoms','modified_atom_indices'),('modified_bonds','modified_bond_indices')]:c.out(key+'_'+k,N(q,'/'+port),'array')
        for label,aware in [('literal',False),('aware',True)]:
            n=c.add(label+'_'+k,'SubstructureQuery',{'smiles':I(f'/smiles/{i}'),'query':V('CC(=O)C'),'query_format':V('smiles'),'tautomer_aware':V(aware),'use_chirality':V(True),'max_matches':V(100)});c.out(label+'_'+k,N(n,'/matched'),'boolean')
        for label,tool in [('donors','GetHBDNum'),('tpsa','CalculateTPSA')]:c.out(label+'_'+k,molecular(c,label+'_'+k,tool,c.inputs['smiles'][i]))
    return c.emit()




def rigid_shape():
    c=Case(54,'Chemical','advanced','Reflection-blind shape scores versus proper rigid fits',
      'The four SDF records and coordinate_sets describe the same five labelled atoms in fixed order: original, rigidly moved, mirrored, and uniformly dilated. Preserve supplied coordinates: no re-embedding, H addition, rescaling or atom rematching. Report centroids (unweighted, as_parsed) and atom_counts for every SDF record. Independently report within_a,b,c,d Euclidean atom-distance matrices from coordinate_sets, the full proper-rigid equal-point-weight rmsd_matrix, and preserved-SDF USRCAT shape_similarity. Report mirror_distance_invariant by all original/mirror distances equal within 1e-6; mirror_proper_equivalent iff proper-fit RMSD(original,mirror)<=1e-6. Do not conclude chirality equivalence from an invariant shape score.',
      {},'shape_invariants_vs_handed_correspondence','Fixed atom correspondence and a byte-pinned four-record geometry source.',
      ['Source centroids/count inventory','Pairwise distance invariants, proper rigid fits and shape moments'],
      'Distinguish reflection invariance, proper rotational equivalence and scale changes.',
      'Artificial coordinate controls, not optimized conformers or experimental stereochemical assignment.')
    from rdkit import Chem
    xyz=[[1.,0.,0.],[0.,0.,0.],[0.,1.2,0.],[0.,0.,1.3],[-.6,-.7,-.8]]
    sets=[xyz,[[-y+2,x-1,z+3] for x,y,z in xyz],[[-x,y,z] for x,y,z in xyz],[[1.2*x,1.2*y,1.2*z] for x,y,z in xyz]]
    mol=Chem.MolFromSmiles('NC(F)(Cl)O');blocks=[]
    for coords in sets:
        m=Chem.Mol(mol);conf=Chem.Conformer(5)
        for i,p in enumerate(coords):conf.SetAtomPosition(i,p)
        m.AddConformer(conf);blocks.append(Chem.MolToMolBlock(m)+'\n$$$$\n')
    path=c.asset('controls.sdf',''.join(blocks));c.inputs={'coordinate_sets':sets,'set_ids':['a','b','c','d'],'sdf':path['value']}
    centers=[];counts=[]
    for i,k in enumerate('abcd'):
        n=c.add('center_'+k,'MolecularCentroid',{'source':I('/sdf'),'source_format':V('sdf'),'record_index':V(i),'hydrogen_policy':V('as_parsed'),'atom_scope':V('all')});centers.append(N(n,'/centroid'))
        count=c.add('count_'+k,'CountMolecularAtoms',{'source':I('/sdf'),'source_format':V('sdf'),'record_index':V(i),'hydrogen_policy':V('as_parsed'),'atom_scope':V('all'),'count_kind':V('all')});counts.append(N(count,'/count'))
        d=c.add('distance_'+k,'PairwiseNumericDistances',{'values':I(f'/coordinate_sets/{i}'),'metric':V('euclidean')});c.out('within_'+k,N(d,'/distances'),'array')
    fit=c.add('fit','RigidSuperposition',{'coordinate_sets':I('/coordinate_sets'),'set_ids':I('/set_ids')});shape=c.add('shape','CompareMolecularShapes',{'source':I('/sdf'),'source_format':V('sdf'),'conformer_policy':V('preserve'),'hydrogen_policy':V('as_parsed'),'optimization':V('none')})
    c.out('centroids',E('numeric_rows',*centers),'array');c.out('atom_counts',vector(*counts),'array');c.out('rmsd_matrix',N(fit,'/rmsd_matrix'),'array');c.out('shape_similarity',N(shape,'/similarity_matrix'),'array')
    c.flag('mirror_distance_invariant',N('distance_a','/distances'),'eq',N('distance_c','/distances'),atol=1e-6)
    c.flag('mirror_proper_equivalent',N(fit,'/rmsd_matrix/0/2'),'le',V(1e-6))
    return c.emit()


def hydrogen_inventory():
    c=Case(55,'Chemical','intermediate','Hydrogen expansion and isotope-sensitive removal audit',
      'For each a,b,c report added_a etc. from AddHydrogens and removed_a etc. from RemoveHydrogens applied to that added graph. For original, added and removed representations report explicit atom counts counts_a etc. as [original,added,removed] under as_parsed/all, average masses masses_a etc. (g/mol), and total formal charges charges_a etc. Report mass_conserved_a etc. when max(masses)-min(masses)<=1e-6. Keep labelled deuterium and graph charge; an apparent H-count reduction does not authorize removing isotope information.',
      {'smiles':['CCO','[2H]O[2H]','[NH4+]']},'hydrogen_and_isotope_bookkeeping','The expanded graph is shared by removal, count, mass and charge witnesses.',
      ['Independent input molecules','Each representation has independent atom-inventory and mass/charge witnesses'],
      'Separate explicit atom count changes from conservation of isotope-sensitive chemical mass and charge.')
    for i,k in enumerate('abc'):
        a=c.add('add_'+k,'AddHydrogens',{'smiles':I(f'/smiles/{i}')});r=c.add('remove_'+k,'RemoveHydrogens',{'smiles':N(a,'/canonical_smiles')})
        c.out('added_'+k,N(a,'/canonical_smiles'),'string');c.out('removed_'+k,N(r,'/canonical_smiles'),'string');counts=[];masses=[];charges=[]
        for tag,sm in [('original',I(f'/smiles/{i}')),('added',N(a,'/canonical_smiles')),('removed',N(r,'/canonical_smiles'))]:
            n=c.add('count_'+tag+'_'+k,'CountMolecularAtoms',{'source':sm,'source_format':V('smiles'),'hydrogen_policy':V('as_parsed'),'count_kind':V('all'),'atom_scope':V('all'),'record_index':V(0)})
            if tag=='removed':
                branch='changed_removed_'+k;c.branches.append({'id':branch,'when':{'left':N(r,'/canonical_smiles'),'op':'ne','right':I(f'/smiles/{i}')}});c.nodes[-1]['branch']=branch
                counts.append(E('select_if_text_equal',N(r,'/canonical_smiles'),I(f'/smiles/{i}'),N('count_original_'+k,'/count'),N(n,'/count')))
            else:counts.append(N(n,'/count'))
            m=c.add('mass_'+tag+'_'+k,'SMILESToWeight',{'smiles':sm});masses.append(N(m,'/molar_mass'))
            q=c.add('charge_'+tag+'_'+k,'MolecularFormalCharges',{'smiles':sm});charges.append(N(q,'/total_formal_charge'))
        c.out('counts_'+k,vector(*counts),'array',evidence=['count_original_'+k,'count_added_'+k,r]);c.out('masses_'+k,vector(*masses),'array');c.out('charges_'+k,vector(*charges),'array')
        c.flag('mass_conserved_'+k,E('subtract',E('max',vector(*masses)),E('min',vector(*masses))),'le',V(1e-6))
    return c.emit()


def scaffold_panel():
    c=Case(56,'Chemical','intermediate','Scaffold-equivalent records can occupy distinct property neighborhoods',
      'Six graph records form a controlled library. Report Murcko scaffolds scaffold_a..f and original-graph TPSA tpsa_a..f (angstrom^2). Compute the full radius2/2048-bit/connectivity/nonchiral Morgan Tanimoto similarity_matrix in record order. Independently form two-dimensional [TPSA,average molar mass] descriptors, population-standardize on this same exploratory library, and report standardized_features and property_distances (Euclidean). Report same_scaffold_a_b and same_scaffold_a_f by exact extracted scaffold equality. Do not treat shared scaffold as equality of the original graph or experimental behavior.',
      {'smiles':['Cc1ccccc1','Oc1ccccc1','Nc1ccccc1','c1ccncc1','CCO','c1ccc2ccccc2c1']},'scaffold_vs_property_geometry','The fixed record order anchors scaffold identity, structural similarities and shared descriptor scaling.',
      ['Scaffolds and original-graph mass/polarity measurements','Fingerprint similarity versus standardized property-space geometry'],
      'Compare common scaffold families with two genuinely different notions of library proximity.')
    ps=[];ms=[]
    for i,k in enumerate('abcdef'):
        sc=c.add('scaffold_'+k,'MurckoDecompose',{'smiles':I(f'/smiles/{i}')});c.out('scaffold_'+k,N(sc,'/canonical_smiles'),'string')
        p=molecular(c,'tpsa_'+k,'CalculateTPSA',c.inputs['smiles'][i]);m=molecular(c,'mass_'+k,'SMILESToWeight',c.inputs['smiles'][i],'molar_mass');ps.append(p);ms.append(m);c.out('tpsa_'+k,p)
    f=c.add('fp','CompareMolecularFingerprints',{'smiles_list':I('/smiles'),'algorithm':V('morgan'),'options':V({'radius':2,'bits':2048,'features':False,'chirality':False}),'metric':V('tanimoto'),'distance':V(False)})
    features=matrix([[p,m] for p,m in zip(ps,ms)]);s=c.add('scale','StandardizeNumericFeatures',{'training_features':features,'features':features});d=c.add('property_distance','PairwiseNumericDistances',{'values':N(s,'/features'),'metric':V('euclidean')})
    c.out('similarity_matrix',N(f,'/matrix'),'array');c.out('standardized_features',N(s,'/features'),'array');c.out('property_distances',N(d,'/distances'),'array')
    for k in ['b','f']:c.flag('same_scaffold_a_'+k,N('scaffold_a','/canonical_smiles'),'eq',N('scaffold_'+k,'/canonical_smiles'))
    return c.emit()


def hydrogen_bond_conventions():
    c=Case(57,'Chemical','foundation','Hydrogen-bond counting conventions in a control panel',
      'For a,b,c,d keep their given graph and charge without protonation changes. Report formal_charge_a etc. and the four counts rdkit_donors_a,rdkit_acceptors_a,lipinski_donors_a,lipinski_acceptors_a etc. using the corresponding local RDKit and Lipinski tools. Report delta_donors_a etc. and delta_acceptors_a etc. = Lipinski minus RDKit. Report donor_convention_agrees_a etc. and acceptor_convention_agrees_a etc. by exact count equality. A different counting convention is not evidence of an experimental hydrogen bond or pH equilibrium.',
      {'smiles':['NC(=O)N','CS(=O)(=O)N','C[N+](C)(C)C','n1ccccc1']},'descriptor_definition_audit','One unchanged molecular record anchors both explicitly different descriptor definitions.',
      ['Four independent molecular controls','RDKit and Lipinski donor/acceptor conventions with a formal-charge witness'],
      'Collect protocol-consistent differences rather than mixing descriptor families.')
    for i,k in enumerate('abcd'):
        q=c.add('charge_'+k,'MolecularFormalCharges',{'smiles':I(f'/smiles/{i}')});c.out('formal_charge_'+k,N(q,'/total_formal_charge'));v={}
        for tag,tool in [('rdkit_donors','GetHBDNum'),('rdkit_acceptors','GetHBANum'),('lipinski_donors','GetLipinskiHBDNum'),('lipinski_acceptors','GetLipinskiHBANum')]:v[tag]=molecular(c,tag+'_'+k,tool,c.inputs['smiles'][i]);c.out(tag+'_'+k,v[tag])
        for tag in ['donors','acceptors']:
            c.out('delta_'+tag+'_'+k,E('subtract',v['lipinski_'+tag],v['rdkit_'+tag]));c.flag(tag[:-1]+'_convention_agrees_'+k,v['lipinski_'+tag],'eq',v['rdkit_'+tag])
    return c.emit()


def partial_charge():
    c=Case(58,'Chemical','intermediate','Partial-charge sums versus formal graph charge',
      'For neutral controls a,b,c report formal_a etc. (integer graph-charge total), eem_a etc. (complete EEM charges) and eem_count_a etc. from the returned EEM atom inventory. EEM must use its documented explicit-H seed42/no-optimization conformer. Independently report explicit_count_a etc. from SMILES with hydrogen_policy=explicit and count_kind=all. Report sum_eem_a etc., residual_a etc.=sum(EEM)-formal total, and inventory_aligned_a etc. by exact EEM/explicit atom count equality. Do not compare partial-charge vectors to formal-charge atom vectors with different H inventories.',
      {'smiles':['CCO','CC(=O)N','O']},'partial_charge_inventory_alignment','The original chemical identity is shared, but EEM and graph-charge inventories have explicit distinct meanings.',
      ['Three independent conformer/EEM evaluations','Formal-charge totals and independently counted explicit-H inventories'],
      'Audit total charge and index-domain consistency before interpreting any atom charges.',
      'Single deterministic computational conformers; no experimental electrostatic potential or ensemble claim.')
    for i,k in enumerate('abc'):
        e=c.add('eem_'+k,'GetEEMCharges',{'smiles':I(f'/smiles/{i}')});q=c.add('formal_'+k,'MolecularFormalCharges',{'smiles':I(f'/smiles/{i}')});n=c.add('count_'+k,'CountMolecularAtoms',{'source':I(f'/smiles/{i}'),'source_format':V('smiles'),'hydrogen_policy':V('explicit'),'count_kind':V('all')})
        c.out('formal_'+k,N(q,'/total_formal_charge'));c.out('eem_'+k,N(e,'/value'),'array');c.out('eem_count_'+k,E('length',N(e,'/atom_inventory')));c.out('explicit_count_'+k,N(n,'/count'))
        total=E('sum',N(e,'/value'));c.out('sum_eem_'+k,total);c.out('residual_'+k,E('subtract',total,N(q,'/total_formal_charge')));c.flag('inventory_aligned_'+k,E('length',N(e,'/atom_inventory')),'eq',N(n,'/count'))
    return c.emit()


def representation_routes():
    c=Case(59,'Chemical','advanced','Competing SELFIES and standard-InChI round-trip routes',
      'For a,b,c preserve the given graph and stereo. Run two independent representation round trips: SMILES->SELFIES->SMILES and SMILES->standard InChI->SMILES. Report selfies_a etc., token_count_a etc. (InspectSELFIES symbol_count), decoded_a etc., inchi_a etc., and recovered_inchi_a etc. For original, SELFIES-decoded and InChI-recovered graphs report canonical_a etc., canonical_selfies_a etc., canonical_inchi_a etc. under keep_all/preserve/keep_stereo=true. Report self_same_a etc. and inchi_same_a etc. as exact canonical identity comparisons. Independently report masses_a etc. as [original,SELFIES,InChI] average molar masses in g/mol. Keep representations that change; do not overwrite source identities or infer that mass conservation proves graph fidelity.',
      {'smiles':['CC(=O)NCC','C[C@H](O)C(=O)O','CCOC(=O)NCC']},'two_representation_route_integrity','Both routes and the original mass witness share each original graph.',
      ['Independent molecules','SELFIES token/decoding chain versus standard-InChI chain and mass checks'],
      'Compare fidelity of two serialization systems without treating tautomer normalization or conserved mass as exact graph preservation.')
    for i,k in enumerate('abc'):
        sf=c.add('encode_'+k,'SMILEStoSELFIES',{'smiles':I(f'/smiles/{i}')});inspect=c.add('inspect_'+k,'InspectSELFIES',{'selfies':N(sf,'/selfies')});decode=c.add('decode_'+k,'SELFIEStoSMILES',{'selfies':N(sf,'/selfies')});h=c.add('inchi_'+k,'SMILESToInChI',{'smiles':I(f'/smiles/{i}')});back=c.add('back_'+k,'InChIToSMILES',{'inchi':N(h,'/inchi')})
        c.out('selfies_'+k,N(sf,'/selfies'),'string');c.out('token_count_'+k,N(inspect,'/symbol_count'));c.out('decoded_'+k,N(decode,'/smiles'),'string');c.out('inchi_'+k,N(h,'/inchi'),'string');c.out('recovered_inchi_'+k,N(back,'/smiles'),'string')
        ns={};masses=[]
        for tag,sm in [('original',I(f'/smiles/{i}')),('selfies',N(decode,'/smiles')),('inchi',N(back,'/smiles'))]:
            n=c.add('canonical_'+tag+'_'+k,'CanonicalMolecularIdentity',{'smiles':sm,'fragment_policy':V('keep_all'),'tautomer_policy':V('preserve'),'keep_stereo':V(True)});ns[tag]=n
            c.out(('canonical_' if tag=='original' else 'canonical_'+tag+'_')+k,N(n,'/canonical_smiles'),'string')
            m=c.add('mass_'+tag+'_'+k,'SMILESToWeight',{'smiles':sm});c.nodes[-1]['observation_reuse_group']='same_graph_mass';masses.append(N(m,'/molar_mass'))
        c.out('masses_'+k,vector(*masses),'array');c.flag('self_same_'+k,N(ns['original'],'/canonical_smiles'),'eq',N(ns['selfies'],'/canonical_smiles'));c.flag('inchi_same_'+k,N(ns['original'],'/canonical_smiles'),'eq',N(ns['inchi'],'/canonical_smiles'))
    return c.emit()


def blend_inventory():
    c=Case(60,'Chemical','advanced','Element-constrained precursor blend with independent mass witnesses',
      'Three benign graph-defined stocks a,b,c are theoretical elemental inventory sources. Report formula_a etc., mass_a etc. (average g/mol), and CNO_a etc. = [C,N,O] mass fractions from each formula. A 100 g blend has each stock mass between 0 and 70 g and must contain at least 15 g oxygen and at most 12 g nitrogen. Maximize carbon mass. Report allocation_g [a,b,c], carbon_g, nitrogen_g and oxygen_g, and total_g. Solve the continuous linear model; independently validate all three elemental masses by matrix multiplication of the [C,N,O]-by-stock mass-fraction matrix with the allocation. Do not model reaction yield, hazards or actual preparation.',
      {'smiles':['OCCO','NCCN','OCCN'],'total_mass_g':100},'elemental_blend_optimization','Graph formula and mass fractions are shared between optimization and independent balance witnesses.',
      ['Per-stock formula, composition and molecular mass','Post-solve elemental and total-mass witnesses'],
      'Enforce physical inventory and capacity constraints while optimizing one element rather than an arbitrary graph score.')
    frac={};mass=[]
    for i,k in enumerate('abc'):
        f=c.add('formula_'+k,'GetMolFormula',{'smiles':I(f'/smiles/{i}')});n=c.add('fractions_'+k,'CompositionFractions',{'formula':N(f,'/value')});m=molecular(c,'mass_'+k,'SMILESToWeight',c.inputs['smiles'][i],'molar_mass')
        c.out('formula_'+k,N(f,'/value'),'string');c.out('mass_'+k,m)
        values=[]
        # N is absent in stock a and O absent in b; retain scientifically exact zeros.
        for element in ['C','N','O']:
            v=V(0.) if (k=='a' and element=='N') or (k=='b' and element=='O') else N(n,'/mass_fractions/'+element)
            frac[k,element]=v;values.append(v)
        c.out('CNO_'+k,vector(*values),'array')
    A=matrix([[frac[k,e] for k in 'abc'] for e in ['C','N','O']])
    lp=c.add('optimum','SolveLinearProgram',{'objective':vector(*[frac[k,'C'] for k in 'abc']),'bounds':V([[0,70]]*3),'equality_matrix':V([[1,1,1]]),'equality_rhs':V([100]),'inequality_matrix':matrix([[frac[k,'N'] for k in 'abc'],[E('multiply',V(-1),frac[k,'O']) for k in 'abc']]),'inequality_rhs':V([12,-15]),'direction':V('max')})
    witness=c.add('elements','MatrixMultiply',{'left':A,'right':N(lp,'/solution')})
    alt=c.nodes[-1]['alternatives'][0];left_rule=next(r for r in alt['input_rules'] if r.get('path')=='/left');left_rule.pop('path');left_rule['left']=E('slice',{'source':'call_arguments','path':'/left'},V(0),V(3));alt['input_rules'].append({'left':E('length',{'source':'call_arguments','path':'/left'}),'op':'one_of','value':[3,4]})
    c.out('allocation_g',N(lp,'/solution'),'array');c.out('carbon_g',N(witness,'/product/0'));c.out('nitrogen_g',N(witness,'/product/1'));c.out('oxygen_g',N(witness,'/product/2'));c.out('total_g',E('sum',N(lp,'/solution')))
    # This stock system can have nonunique optimal allocations. Grade feasible
    # optimum witnesses rather than one particular solver vertex.
    allocation=[{'source':'answer','path':f'/allocation_g/{i}'} for i in range(3)]
    c.properties['allocation_g'].update(minItems=3,maxItems=3)
    c.outcomes=[o for o in c.outcomes if o['id']!='allocation_g']
    for i,a in enumerate(allocation):
        for op,bound in [('ge',0.),('le',70.)]:c.outcomes.append({'id':f'bound_{i}_{op}','left':a,'op':op,'value':bound,'evidence_nodes':[lp],'atol':1e-6})
    c.outcomes.append({'id':'mass_balance','left':E('sum',vector(*allocation)),'op':'eq','value':100.,'evidence_nodes':[lp],'atol':1e-6,'rtol':1e-6})
    for element,field in [('C','carbon_g'),('N','nitrogen_g'),('O','oxygen_g')]:
        out=next(o for o in c.outcomes if o['id']==field)
        out['left']=E('subtract',out['left'],dot([frac[k,element] for k in 'abc'],allocation))
        out['right']=V(0.)
    c.outcomes += [{'id':'carbon_optimal','left':{'source':'answer','path':'/carbon_g'},'op':'eq','right':N(lp,'/objective_value'),'evidence_nodes':[lp],'atol':1e-6,'rtol':1e-6},
        {'id':'nitrogen_cap','left':{'source':'answer','path':'/nitrogen_g'},'op':'le','value':12.,'evidence_nodes':[lp],'atol':1e-6},
        {'id':'oxygen_floor','left':{'source':'answer','path':'/oxygen_g'},'op':'ge','value':15.,'evidence_nodes':[lp],'atol':1e-6}]
    return c.emit()


def property_structure():
    c=Case(61,'Chemical','intermediate','Property geometry versus structural neighborhood association',
      'The five neutral graphs define a finite exploratory panel. For each a..e report TPSA tpsa_a etc. (angstrom^2), mass_a etc. (g/mol) and donors_a etc. Form [TPSA,mass,donors] features in record order, population-standardize on the same panel and report standardized_features and property_distances (Euclidean). Independently compute structural_distances as Morgan radius2/2048-bit/connectivity/nonchiral Tanimoto distances. Report the zero-permutation Pearson upper-triangle property_structure_correlation. This is representation association, not a causal or predictive validation.',
      {'smiles':['CCO','CCCO','CC(=O)O','CC(=O)N','c1ccccc1O']},'molecular_feature_vs_graph_association','Each molecule supplies one common feature row; standardization is fitted once for the whole finite panel.',
      ['Independent molecule descriptor rows','Structural fingerprint geometry versus standardized property geometry'],
      'Correlate distances only after both branches preserve identical compound order.')
    features=[]
    for i,k in enumerate('abcde'):
        p=molecular(c,'tpsa_'+k,'CalculateTPSA',c.inputs['smiles'][i]);m=molecular(c,'mass_'+k,'SMILESToWeight',c.inputs['smiles'][i],'molar_mass');d=molecular(c,'donors_'+k,'GetHBDNum',c.inputs['smiles'][i]);features.append([p,m,d]);c.out('tpsa_'+k,p);c.out('mass_'+k,m);c.out('donors_'+k,d)
    f=matrix(features);scale=c.add('scale','StandardizeNumericFeatures',{'training_features':f,'features':f});pd=c.add('pd','PairwiseNumericDistances',{'values':N(scale,'/features'),'metric':V('euclidean')});sd=c.add('sd','CompareMolecularFingerprints',{'smiles_list':I('/smiles'),'algorithm':V('morgan'),'options':V({'radius':2,'bits':2048,'features':False,'chirality':False}),'metric':V('tanimoto'),'distance':V(True)});assoc=c.add('association','MantelCorrelation',{'distance_a':N(pd,'/distances'),'distance_b':N(sd,'/matrix'),'permutations':V(0)})
    c.out('standardized_features',N(scale,'/features'),'array');c.out('property_distances',N(pd,'/distances'),'array');c.out('structural_distances',N(sd,'/matrix'),'array');c.out('property_structure_correlation',N(assoc,'/correlation'))
    return c.emit()


def principal_moment_checks():
    c=Case(62,'Chemical','intermediate','Principal moment ratios with a controlled conformer protocol',
      'For each a,b,c use the local ETKDGv3 seed42 conformer, explicit hydrogens and no optimization. Report raw PMI moments pmi_a etc. as [I1,I2,I3] in RDKit inertia units and normalized_a etc. as [NPR1,NPR2] from the separate normalized-moments tool. Report ratio_a etc. = [I1/I3,I2/I3] and agrees_a etc. when both independent ratios agree within absolute+relative1e-6. In parallel compare the three molecules using USRCAT with the SAME seed42/explicit-H/no-optimization generation policy, reporting similarity_matrix. No ensemble average, experimental geometry or preferred conformer is inferred.',
      {'smiles':['CCO','c1ccccc1','C1CCCCC1']},'inertia_ratio_protocol_consistency','Every inertia and shape branch is tied to the same declared finite conformer protocol.',
      ['Raw moment components versus separately normalized moment outputs','Cross-molecule shape matrix'],
      'Check dimensionless ratio consistency without mixing geometry/H policies or confusing shape with identity.')
    for i,k in enumerate('abc'):
        moments=[]
        for j in [1,2,3]:moments.append(molecular(c,'pmi'+str(j)+'_'+k,'CalculatePMI'+str(j),c.inputs['smiles'][i]))
        n=c.add('normalized_'+k,'NormalizedPrincipalMoments',{'smiles':I(f'/smiles/{i}'),'seed':V(42),'optimization':V('none'),'hydrogen_policy':V('explicit')})
        ratio=vector(E('divide',moments[0],moments[2]),E('divide',moments[1],moments[2]));normalized=vector(N(n,'/npr1'),N(n,'/npr2'))
        c.out('pmi_'+k,vector(*moments),'array');c.out('ratio_'+k,ratio,'array');c.out('normalized_'+k,normalized,'array');c.flag('agrees_'+k,ratio,'eq',normalized,atol=1e-6)
    s=c.add('shape','CompareMolecularShapes',{'source':I('/smiles'),'source_format':V('smiles'),'seed':V(42),'optimization':V('none'),'hydrogen_policy':V('explicit'),'conformer_policy':V('generate')});c.out('similarity_matrix',N(s,'/similarity_matrix'),'array')
    return c.emit()




def fingerprint_diffusion():
    c=Case(8,'Chemical','intermediate','Representation-dependent compound neighborhoods and graph propagation',
      'Preserve the supplied molecular graphs, tautomer and stereo. Record order is reference benzene then candidates a,b,c. Report canonical_smiles in this order. Construct full Tanimoto similarity matrices morgan_matrix (radius2,bits2048,chirality=false,features=false) and maccs_matrix (default MACCS). For each representation k=morgan,maccs report neighbor_k_a,b,c for similarity to record0>=0.30. Treat its off-diagonal similarities as undirected weighted COMPOUND-SPACE edges, with diagonal exactly0; construct unnormalized L=degree-adjacency. Report spectrum_k and heat_k=exp(-L)*[1,0,0,0], and mass_k=sum(heat_k). Report isolated_candidate_k_c iff candidate c has zero off-diagonal weighted degree within1e-12. Keep each propagation operator attached to its own fingerprint matrix. This graph propagation measures an informatics neighborhood convention; it is not atom-index diffusion, molecular identity, kinetics or experimental transport.',
      {'smiles':['c1ccccc1','c1ccncc1','c1ccc2ccccc2c1','C1CCNCC1']},
      'fingerprint_neighborhood_propagation','Each full fingerprint matrix is reused by its local neighbor audit and compound-space propagation operator.',
      ['Morgan and MACCS representation branches','Within each representation: local decisions, Laplacian spectrum and propagation chain'],
      'Compare representation-dependent local neighborhoods and distributed signal without mixing molecular and compound object spaces.')
    for k,fp in [('morgan','morgan'),('maccs','maccs')]:
        args={'smiles_list':I('/smiles'),'algorithm':V(fp),'options':V({}),'metric':V('tanimoto'),'distance':V(False)}
        if fp=='morgan':args['options']=V({'radius':2,'bits':2048,'chirality':False,'features':False})
        f=c.add('fingerprint_'+k,'CompareMolecularFingerprints',args)
        c.out(k+'_matrix',N(f,'/matrix'),'array')
        if k=='morgan':c.out('canonical_smiles',E('scalar_array',*[N(f,f'/records/{i}/canonical_smiles') for i in range(4)]),'array')
        for i,label in enumerate('abc',1):c.flag('neighbor_'+k+'_'+label,N(f,f'/matrix/0/{i}'),'ge',V(.30))
        a=matrix([[V(0.) if i==j else N(f,f'/matrix/{i}/{j}') for j in range(4)] for i in range(4)])
        l=c.add('lap_'+k,'GraphLaplacian',{'adjacency':a});s=c.add('spectrum_'+k,'SymmetricEigenDecomposition',{'values':N(l,'/laplacian')});scaled=matrix([[E('multiply',V(-1),N(l,f'/laplacian/{i}/{j}')) for j in range(4)] for i in range(4)])
        h=c.add('operator_'+k,'MatrixExponential',{'values':scaled});p=c.add('heat_'+k,'MatrixMultiply',{'left':N(h,'/exponential'),'right':V([1,0,0,0])})
        c.out('spectrum_'+k,N(s,'/eigenvalues'),'array');c.out('heat_'+k,N(p,'/product'),'array');c.out('mass_'+k,E('sum',N(p,'/product')))
        degree=E('sum',vector(*[N(f,f'/matrix/3/{j}') for j in range(3)]));c.flag('isolated_candidate_'+k+'_c',degree,'le',V(1e-12))
    return c.emit()


def build():return [fingerprint_diffusion(),registry(),atom_diffusion(),tautomer_queries(),rigid_shape(),hydrogen_inventory(),scaffold_panel(),hydrogen_bond_conventions(),partial_charge(),representation_routes(),blend_inventory(),property_structure(),principal_moment_checks()]
