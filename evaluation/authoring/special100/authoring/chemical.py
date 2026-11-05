"""Individually specified local chemistry case designs; no reference answers."""
import json
from evaluation.workflow.schema import validate_workflow


def src(n,p): return {'source':'node','node':n,'path':p}
def op(n,*a,**k): return {'operation':n,'args':list(a),**k}
def val(x): return {'value':x}

def build():
    # Each decision is a small explicit model, not a claim about experimental performance.
    cases = [
      ('Salt-form inventory for a gravimetric assay', ['CC(=O)[O-].[Na+]','CC(=O)O','CCC(=O)O'], [('SMILESToWeight','molar_mass','g/mol'),('CalculateTPSA','value','angstrom^2')], 'divide', 'Minimize average molecular mass divided by topological polar surface area. This is a stated assay inventory heuristic, not a solubility prediction.', 'largest_organic', False),
      ('Isotope standard mass-defect audit', ['CCO','[13CH3]CO','CC[18OH]'], [('SMILESToWeight','molar_mass','g/mol'),('GetExactMolceularWeight','value','Da')], 'subtract', 'Maximize the numerical difference average molecular mass minus monoisotopic exact molecular mass, using the convention that their numerical values are compared on the molar-mass scale. Preserve isotopes.', 'keep_all', True),
      ('Hydroxyl masking and donor efficiency', ['OCCO','COCCO','COCCOC'], [('GetHBDNum','value','count'),('SMILESToWeight','molar_mass','g/mol')], 'divide', 'Maximize donor count divided by average molecular mass to choose the greatest donor density. Do not infer measured hydrogen bonding or permeability.', 'keep_all', True),
      ('Rigid linker replacement', ['c1ccccc1CCc1ccccc1','c1ccc(-c2ccccc2)cc1','c1ccc(CCOc2ccccc2)cc1'], [('GetRotatableBondsNum','value','count'),('GetAromaticRingsNum','value','count')], 'divide', 'Minimize strict RDKit rotatable-bond count per aromatic ring for a rigid two-aromatic-ring linker study.', 'keep_all', False),
      ('Saturated scaffold enrichment', ['c1ccncc1','C1CCNCC1','C1COCCN1'], [('GetFractionCSP3','value','fraction'),('GetHBANum','value','count')], 'multiply', 'Maximize fraction of sp3 carbon times hydrogen-bond acceptor count as the explicitly defined saturation-and-acceptor design score.', 'keep_all', False),
      ('Amide replacement polarity cost', ['CC(=O)NCC','CCOC(=O)NCC','CCS(=O)(=O)NCC'], [('CalculateTPSA','value','angstrom^2'),('SMILESToWeight','molar_mass','g/mol')], 'divide', 'Minimize topological polar surface area per average molecular mass for a matched functional-group replacement study. Report only this descriptor decision; do not claim oral absorption.', 'keep_all', False),
      ('Acceptor versus donor balance in buffers', ['NCCO','CNCCO','CN(C)CCO'], [('GetHBANum','value','count'),('GetHBDNum','value','count')], 'subtract', 'Maximize acceptor count minus donor count in the submitted neutral graphs. Do not protonate structures or infer pH behavior.', 'keep_all', False),
      ('Aromatic heterocycle packing proxy', ['c1ccncc1','c1nccnc1','c1ccc2ncccc2c1'], [('GetAromaticHeterocyclesNum','value','count'),('GetExactMolceularWeight','value','Da')], 'divide', 'Maximize aromatic heterocycle count divided by exact molecular mass as a heteroaromatic ring density proxy.', 'keep_all', False),
      ('Ring topology versus flexibility', ['C1CCC2CCCCC2C1','C1CCC(CC1)C2CCCCC2','C1CC2CCC1C2'], [('GetBridgeheadAtomsNum','value','count'),('GetRotatableBondsNum','value','count')], 'subtract', 'Maximize bridgehead atom count minus strict rotatable-bond count when selecting a constrained bicyclic building block.', 'keep_all', False),
      ('Spiro library normalization', ['C1CCC2(CC1)CCCC2','C1CCC2CCCCC2C1','C1CC2CCC1C2'], [('GetSpiroAtomsNum','value','count'),('GetRingsNum','value','count')], 'divide', 'Maximize spiro atom count divided by ring count. Use the RDKit ring-count convention consistently; no geometric shape claim is implied.', 'keep_all', False),
      ('Amide burden in short linkers', ['CC(=O)NCCNC(C)=O','CC(=O)NCCOCC','CCNCCOCC'], [('GetAmideBondsNum','value','count'),('GetRotatableBondsNum','value','count')], 'divide', 'Minimize amide-bond count divided by strict rotatable-bond count to select the least amide-constrained linker by this stated proxy.', 'keep_all', False),
      ('Stereochemical specification audit', ['C[C@H](O)C(=O)O','CC(O)C(=O)O','C[C@@H](O)C(=O)O'], [('GetAtomStereoCentersNum','value','count'),('GetUnspecifiedAtomStereoCentersNum','value','count')], 'subtract', 'Maximize total potential atom stereocenters minus unspecified atom stereocenters. Preserve supplied stereo. This selects completely specified records, including ties; it does not select a preferred enantiomer.', 'keep_all', True),
      ('Fragment library polar surface budget', ['c1ccccc1O','Oc1ccncc1','OC1CCCCC1'], [('CalculateTPSA','value','angstrom^2'),('GetLabuteASA','value','angstrom^2')], 'divide', 'Minimize topological polar surface area divided by Labute approximate surface area as an explicit fragment-library polarity budget score. Both quantities are graph descriptors.', 'keep_all', False),
    ]
    specs=[]
    for index,(title,smiles,metrics,operation,goal,fragment,maximize) in enumerate(cases,1):
        tid=f'SMAS-{index:04d}'
        records=[{'id':f'r{i+1}','smiles':s} for i,s in enumerate(smiles)]
        repair=index in (3,12)
        if repair:
            records[1]['alternate_smiles']=records[1]['smiles']
            records[1]['smiles']='C1CC' if index==3 else 'CC(O)C(=O)O)'
        nodes=[]; outcomes=[]; scores=[]; props={}; branch_notes=[]
        for i,record in enumerate(records):
            nid=f'identity_{i}'
            input_path=f'/records/{i}/'+('alternate_smiles' if repair and i==1 else 'smiles')
            rules=[{'path':'/smiles','op':'eq','right':{'source':'inputs','path':input_path}}, {'path':'/fragment_policy','op':'eq','value':fragment}, {'path':'/tautomer_policy','op':'eq','value':'preserve'},{'path':'/keep_stereo','op':'eq','value':True}]
            nodes.append({'id':nid,'alternatives':[{'tools':['CanonicalMolecularIdentity'],'input_rules':rules,'output_rules':[{'path':'/canonical_smiles','op':'type','value':'string'}]}]})
            props[record['id']]={'type':'object','properties':{'canonical_smiles':{'type':'string'}},'required':['canonical_smiles'],'additionalProperties':False}
            outcomes.append({'id':nid,'left':{'source':'answer','path':f'/records/{record["id"]}/canonical_smiles'},'op':'eq','right':src(nid,'/canonical_smiles'),'evidence_nodes':[nid]})
            terms=[]
            for j,(tool,field,unit) in enumerate(metrics):
                mid=f'metric_{i}_{j}'; terms.append(src(mid,'/'+field))
                nodes.append({'id':mid,'depends_on':[nid],'bindings':[{'argument':'/smiles','source_node':nid,'output':'/canonical_smiles'}], 'alternatives':[{'tools':[tool],'output_rules':[{'path':'/'+field,'op':'finite'}]}]})
                label=f'm{j+1}'; props[record['id']]['properties'][label]={'type':'number'}; props[record['id']]['required'].append(label)
                outcomes.append({'id':mid,'left':{'source':'answer','path':f'/records/{record["id"]}/{label}'},'op':'eq','right':src(mid,'/'+field),'atol':1e-6,'rtol':1e-6,'evidence_nodes':[nid,mid]})
            score=op(operation,*terms); scores.append(score)
            props[record['id']]['properties']['score']={'type':'number'}; props[record['id']]['required'].append('score')
            outcomes.append({'id':f'score_{i}','left':{'source':'answer','path':f'/records/{record["id"]}/score'},'op':'eq','right':score,'atol':1e-6,'rtol':1e-6,'evidence_nodes':[nid,f'metric_{i}_0',f'metric_{i}_1']})
        ranked=op('paired_rows',val([r['id'] for r in records]),op('array',*scores))
        outcomes.append({'id':'decision','left':{'source':'answer','path':'/selected'},'op':'set_equal','right':op('argmax' if maximize else 'argmin',ranked,id_path='/0',value_path='/1',tie_atol=1e-9),'evidence_nodes':[n['id'] for n in nodes]})
        answer_schema={'type':'object','properties':{'records':{'type':'object','properties':props,'required':list(props),'additionalProperties':False},'selected':{'type':'array','items':{'type':'string'},'uniqueItems':True}},'required':['records','selected'],'additionalProperties':False}
        metric_text='; '.join(f'm{j+1}: '+ {'SMILESToWeight':'RDKit average molecular mass','GetExactMolceularWeight':'RDKit exact molecular mass','CalculateTPSA':'RDKit topological polar surface area','GetRotatableBondsNum':'strict RDKit rotatable bonds','GetHBANum':'RDKit hydrogen-bond acceptors','GetHBDNum':'RDKit hydrogen-bond donors','GetFractionCSP3':'fraction of sp3 carbons','GetAromaticRingsNum':'RDKit aromatic rings','GetAromaticHeterocyclesNum':'RDKit aromatic heterocycles','GetBridgeheadAtomsNum':'RDKit bridgehead atoms','GetSpiroAtomsNum':'RDKit spiro atoms','GetRingsNum':'RDKit rings','GetAmideBondsNum':'RDKit amide bonds','GetAtomStereoCentersNum':'potential atom stereocenters','GetUnspecifiedAtomStereoCentersNum':'unspecified atom stereocenters','GetLabuteASA':'Labute approximate surface area'}[m[0]]+f' ({m[2]})' for j,m in enumerate(metrics))
        question=f'{title}. {goal} First standardize each supplied graph: '+('retain only the largest organic component' if fragment=='largest_organic' else 'retain every disconnected component')+', preserve tautomer representation and retain stereochemical information. Calculate '+metric_text+'. Report each normalized canonical isomeric SMILES, m1, m2 and the specified score. Return every tied winning record ID; ties mean absolute score difference at most 1e-9. Numeric answers must agree within absolute 1e-6 plus relative 1e-6. Use the normalized graphs for both measurements.'
        if repair: question+=' One record has a transcription error in its primary SMILES. If it cannot be parsed and sanitized, use its explicitly supplied alternate representation, never guess a structure. A preliminary failed parse is optional; report values for the usable representation.'
        filename=f'{tid}-records.json'
        public={'id':tid,'domain':'Chemical','question':question,'inputs':{'records':records},'files':[f'asset://{filename}'],'answer_schema':answer_schema,'question_language':'en','Parameter':{},'unit_annotations':{'m1':metrics[0][2],'m2':metrics[1][2],'score':(metrics[0][2]+' / '+metrics[1][2] if operation=='divide' else metrics[0][2]+' * '+metrics[1][2] if operation=='multiply' else 'g/mol (exact mass converted to molar-mass scale)' if index==2 else metrics[0][2])}}
        evaluation={'schema_version':'workflow.v1','nodes':nodes,'outcomes':outcomes,'efficiency':{'free_recovery_calls':1 if repair else 0,'free_disambiguation_calls':1}}
        validate_workflow(evaluation)
        specs.append({'task':public,'evaluation':evaluation,'design':{'scientific_goal':goal,'parallel_branches':'Three independent molecular records; two independent measurements after each shared representation step; decision joins all scores.','shared_preprocessing':f'Explicit {fragment}, preserve-tautomer, preserve-stereo identity per record reused for both measurements.','early_stop_logic':'No unjustified descriptor stop: all records require two measurements; all tied optima are retained.','repair_opportunity':'Invalid primary has explicit authoritative alternate representation.' if repair else 'None required.','case_study':index in (1,2,12),'source_notes':'Local catalog contracts and tools.execute preflight; numerical targets derive from observations, never manually authored. Proxy objectives are supplied rules, not empirical property claims.'},'assets':{filename:{'records':records}}})
    _strengthen(specs)
    return specs


def _strengthen(specs):
    # Inventory case measures the submitted salts separately from their selected
    # parent graphs: normalization has an observable gravimetric consequence.
    case=specs[0]; ev=case['evaluation']; schema=case['task']['answer_schema']
    for i in range(3):
        nid=f'as_received_mass_{i}'
        ev['nodes'].append({'id':nid,'alternatives':[{'tools':['SMILESToWeight'],'input_rules':[{'path':'/smiles','op':'eq','right':{'source':'inputs','path':f'/records/{i}/smiles'}}],'output_rules':[{'path':'/molar_mass','op':'finite'}]}]})
        # One unchanged whole/parent graph may legitimately reuse the same measured mass.
        ev['nodes'][-1]['observation_reuse_group']=f'mass_inventory_{i}'
        next(n for n in ev['nodes'] if n['id']==f'metric_{i}_0')['observation_reuse_group']=f'mass_inventory_{i}'
        obj=schema['properties']['records']['properties'][f'r{i+1}']
        for key in ('as_received_mass','removed_mass'):
            obj['properties'][key]={'type':'number'};obj['required'].append(key)
        for key,target in [('as_received_mass',src(nid,'/molar_mass')),('removed_mass',op('subtract',src(nid,'/molar_mass'),src(f'metric_{i}_0','/molar_mass')))]:
            ev['outcomes'].append({'id':f'{key}_{i}','left':{'source':'answer','path':f'/records/r{i+1}/{key}'},'op':'eq','right':target,'atol':1e-6,'rtol':1e-6,'evidence_nodes':[nid,f'identity_{i}',f'metric_{i}_0']})
    case['task']['unit_annotations'].update(as_received_mass='g/mol',removed_mass='g/mol')
    case['task']['question']+=' Additionally report as_received_mass (g/mol) for each complete submitted graph, and removed_mass = as_received_mass minus m1 (g/mol). Quantify the gravimetric counterion burden without neutralizing the selected organic fragment.'
    case['design']['parallel_branches']='Submitted whole-graph mass and selected-parent identity run independently; parent mass and polarity reuse the identity, then mass subtraction joins submitted and parent branches.'
    # Stereo case adds an orthogonal graph-neighborhood sensitivity experiment.
    case=specs[11]; ev=case['evaluation']; task=case['task']
    list_expr=op('scalar_array',*[src(f'identity_{i}','/canonical_smiles') for i in range(3)])
    for chirality,label in [(False,'achiral_matrix'),(True,'chiral_matrix')]:
        node={'id':label,'depends_on':[f'identity_{i}' for i in range(3)],'alternatives':[{'tools':['CompareMolecularFingerprints'],'input_rules':[{'path':'/smiles_list','op':'eq','right':list_expr},{'path':'/algorithm','op':'eq','value':'morgan'},{'path':'/metric','op':'eq','value':'tanimoto'},{'path':'/distance','op':'eq','value':False},{'path':'/options/radius','op':'eq','value':2},{'path':'/options/bits','op':'eq','value':2048},{'path':'/options/chirality','op':'eq','value':chirality},{'path':'/options/features','op':'eq','value':False}], 'output_rules':[{'path':'/matrix','op':'type','value':'array'}]}]}
        ev['nodes'].append(node)
        task['answer_schema']['properties'][label]={'type':'array','items':{'type':'array','items':{'type':'number'}},'minItems':3,'maxItems':3};task['answer_schema']['required'].append(label)
        ev['outcomes'].append({'id':label,'left':{'source':'answer','path':'/'+label},'op':'eq','right':src(label,'/matrix'),'atol':1e-6,'rtol':1e-6,'evidence_nodes':[node['id'],*[f'identity_{i}' for i in range(3)]]})
    task['unit_annotations'].update(achiral_matrix='dimensionless similarity',chiral_matrix='dimensionless similarity')
    task['question']+=' Also report complete 3 by 3 Tanimoto similarity matrices in supplied record order for radius-2, 2048-bit connectivity Morgan fingerprints, feature invariants disabled: achiral_matrix excludes chirality and chiral_matrix includes chirality. These comparisons test representation sensitivity and do not imply biological equivalence.'
    case['design']['parallel_branches']='Per-record stereo completeness and two independent batch fingerprint protocols reuse normalized graphs; the matrices expose whether stereochemical distinctions survive the selected fingerprint convention.'
    # Replace the last descriptor panel with a genuine graph-gated triage.
    case=specs[12]; task=case['task']; old=case['evaluation']; nodes=[n for n in old['nodes'] if n['id'].startswith('identity_')]; outcomes=[o for o in old['outcomes'] if o['id'].startswith('identity_')]; branches=[]
    record_props={}
    for i in range(3):
        identity=f'identity_{i}'; query=f'phenolic_oxygen_{i}'; measure=f'polar_area_{i}'; yes=f'eligible_{i}'; no=f'ineligible_{i}'
        nodes.append({'id':query,'depends_on':[identity],'bindings':[{'argument':'/smiles','source_node':identity,'output':'/canonical_smiles'}],'alternatives':[{'tools':['SubstructureQuery'],'input_rules':[{'path':'/query','op':'eq','value':'[OX2H][c]'},{'path':'/query_format','op':'eq','value':'smarts'},{'path':'/tautomer_aware','op':'eq','value':False}], 'output_rules':[{'path':'/matched','op':'type','value':'boolean'},{'path':'/truncated','op':'eq','value':False}]}]})
        for b,value in [(yes,True),(no,False)]: branches.append({'id':b,'when':{'left':src(query,'/matched'),'op':'eq','value':value}})
        nodes.append({'id':measure,'branch':yes,'depends_on':[identity,query],'bindings':[{'argument':'/smiles','source_node':identity,'output':'/canonical_smiles'}],'alternatives':[{'tools':['CalculateTPSA'],'output_rules':[{'path':'/value','op':'finite'}]}]})
        for key,target,branch,evidence in [('eligible',src(query,'/matched'),None,[query]),('tpsa',src(measure,'/value'),yes,[query,measure]),('tpsa',val(None),no,[query])]:
            o={'id':f'{key}_{branch or i}','left':{'source':'answer','path':f'/records/r{i+1}/{key}'},'op':'eq','right':target,'evidence_nodes':evidence}
            if key=='tpsa' and branch==yes:o.update(atol=1e-6,rtol=1e-6)
            if branch:o['branch']=branch
            outcomes.append(o)
        record_props[f'r{i+1}']={'type':'object','properties':{'canonical_smiles':{'type':'string'},'eligible':{'type':'boolean'},'tpsa':{'type':['number','null']}},'required':['canonical_smiles','eligible','tpsa'],'additionalProperties':False}
    task['question']='Triage a phenolic fragment library for a follow-up polar-surface study. Retain all components, preserve tautomers and stereo, and report canonical isomeric SMILES. A graph is eligible exactly when it contains a neutral divalent hydroxyl oxygen bonded directly to an aromatic carbon (ordinary SMARTS [OX2H][c], no tautomer-aware matching). Report eligible for every record. Only eligible records need RDKit topological polar surface area in angstrom^2; report null tpsa for an ineligible record and stop its descriptor branch. Numeric tolerance is absolute 1e-6 plus relative 1e-6. This is structural triage, not a potency prediction.'
    task['answer_schema']={'type':'object','properties':{'records':{'type':'object','properties':record_props,'required':list(record_props),'additionalProperties':False}},'required':['records'],'additionalProperties':False}
    task['unit_annotations']={'tpsa':'angstrom^2'}
    case['evaluation']={'schema_version':'workflow.v1','nodes':nodes,'branches':branches,'outcomes':outcomes}
    case['design'].update(scientific_goal='Structural phenol triage with conditional polarity measurement.',parallel_branches='Independent graph eligibility checks; accepted records have independent polarity branches.',shared_preprocessing='Each canonical graph is reused for eligibility and eligible-record polarity.',early_stop_logic='A negative graph match terminates that record with null polarity; no polarity measurement is required or rewarded for it.',case_study=True)
    for case in specs:
        task=case['task']; task['Parameter']=json.dumps(task['inputs'],ensure_ascii=False)
        old_units=task['unit_annotations']; task['unit_annotations']=[]
        for key,unit in old_units.items():
            if key in ('achiral_matrix','chiral_matrix'):
                task['unit_annotations'].append({'path':'/'+key,'unit':unit,'description':'Fingerprint similarity.'})
            else:
                for record in task['inputs']['records']:
                    task['unit_annotations'].append({'path':f"/records/{record['id']}/{key}",'unit':unit,'description':'Scientific quantity as defined in the question.'})
        validate_workflow(case['evaluation'])
