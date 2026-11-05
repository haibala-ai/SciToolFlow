"""Scientifically justified capability equivalences found by independent pilots.

These corrections broaden valid representations, not scientific tolerances.
"""
from copy import deepcopy
import hashlib,json


def apply(rows,base):
    for row in rows:
        tid=row['task']['id'];ev=row['evaluation']
        if tid.startswith('SMAS-00') and row['task']['domain']=='Chemical':
            direction='argmax' if 'Maximize ' in row['task']['question'] else 'argmin' if 'Minimize ' in row['task']['question'] else None
            if direction:
                for outcome in ev['outcomes']:
                    if outcome['id']=='decision':outcome['right']['operation']=direction
        if row['task']['domain']=='Material':
            from pymatgen.core import Structure
            from tempfile import TemporaryDirectory
            with TemporaryDirectory() as temp:
                for node in ev['nodes']:
                    alt=node['alternatives'][0]
                    if alt['tools']!=['GetElementComposition']:continue
                    names=[r['value'][0] for r in alt['input_rules'] if r.get('op')=='one_of' and r.get('path')=='/file_name']
                    if not names:continue
                    name=names[0];path=__import__('pathlib').Path(temp)/name;path.write_text(row['assets'][name])
                    counts=Structure.from_file(path).composition.get_el_amt_dict()
                    node['observation_reuse_group']='formula_'+hashlib.sha256(json.dumps(counts,sort_keys=True).encode()).hexdigest()[:12]
                    node['alternatives'].append({'tools':['CompositionFractions'],
                        'input_rules':[{'left':{'operation':'molecular_formula_counts','args':[{'source':'call_arguments','path':'/formula'}]},'op':'eq','value':counts}],
                        'output_rules':[{'path':'/element_amounts','op':'eq','value':counts}]})
        for node in ev['nodes']:
            for alt in list(node['alternatives']):
                if alt['tools']==['MantelCorrelation']:
                    zero=any(r.get('path')=='/permutations' and r.get('value')==0 for r in alt.get('input_rules',[]))
                    if zero:
                        alt['input_rules']=[r for r in alt.get('input_rules',[]) if r.get('path')!='/seed']
                        # Descriptive Pearson triangle correlation is symmetric.
                        # With zero permutations there is no direction-dependent
                        # finite RNG realization to change by swapping matrices.
                        swapped=deepcopy(alt);bindings={}
                        for rule in swapped.get('input_rules',[]):
                            path=rule.get('path') or rule.get('left',{}).get('path')
                            if path in ('/distance_a','/distance_b'):bindings[path]=rule
                        if len(bindings)==2:
                            first,second=bindings['/distance_a'],bindings['/distance_b']
                            first['right'],second['right']=second['right'],first['right']
                            if swapped not in node['alternatives']:node['alternatives'].append(swapped)
                    node['observation_reuse_group']='same_mantel_inputs_and_protocol'
        if row['task']['domain']=='Material':
            # Domain operations already parsing a pinned source can establish
            # its site count without an additional reader-only call.
            reads={n['id']:n for n in ev['nodes'] if n['alternatives'][0]['tools']==['ReadCrystalStructure']}
            replacements={};volumes={}
            for rid,read in reads.items():
                source_hash=next((r['value'] for r in read['alternatives'][0]['output_rules'] if r.get('path')=='/source_sha256'),None)
                for other in ev['nodes']:
                    if other['alternatives'][0]['tools']!=['PeriodicNeighborList']:continue
                    hashes=[r.get('value') for r in other['alternatives'][0]['output_rules'] if r.get('path')=='/source_sha256']
                    if source_hash in hashes:replacements[rid]=other['id'];break
                for other in ev['nodes']:
                    if other['alternatives'][0]['tools']!=['CalculateDensity']:continue
                    hashes=[r.get('value') for r in other['alternatives'][0]['output_rules'] if r.get('path')=='/source_sha256']
                    if source_hash in hashes:
                        replacements.setdefault(rid,other['id']);volumes[rid]=other['id'];break
            def transform(value):
                if isinstance(value,dict):
                    if value.get('operation')=='length' and len(value.get('args',[]))==1:
                        arg=value['args'][0]
                        if arg.get('source')=='node' and arg.get('node') in replacements and arg.get('path')=='/structure/sites':
                            return {'source':'node','node':replacements[arg['node']],'path':'/sites' if next(n for n in ev['nodes'] if n['id']==replacements[arg['node']])['alternatives'][0]['tools']==['CalculateDensity'] else '/site_count'}
                    if value.get('source')=='node' and value.get('node') in volumes and value.get('path')=='/structure/lattice/volume':
                        return {'source':'node','node':volumes[value['node']],'path':'/volume_angstrom_cubed'}
                    return {k:transform(v) for k,v in value.items()}
                if isinstance(value,list):return [transform(v) for v in value]
                return value
            ev['outcomes']=transform(ev['outcomes'])
            def selectors(value):
                if isinstance(value,dict):
                    if value.get('source')=='node':yield value['node']
                    for v in value.values():yield from selectors(v)
                elif isinstance(value,list):
                    for v in value:yield from selectors(v)
            used=set(selectors(ev['outcomes']))
            removed={rid for rid in replacements if rid not in used}
            if removed:
                ev['nodes']=[n for n in ev['nodes'] if n['id'] not in removed]
                for out in ev['outcomes']:
                    out['evidence_nodes']=list(dict.fromkeys(replacements.get(n,n) if n in removed else n for n in out.get('evidence_nodes',[])))
        if row['task']['domain']=='Material':
            # File identity is content-based. Exact historical absolute paths
            # would reject copied inputs and a different checkout location.
            for n in ev['nodes']:
                for alt in n['alternatives']:
                    if any('source_sha256' in r.get('path','') for r in alt.get('output_rules',[])):
                        alt['input_rules']=[r for r in alt.get('input_rules',[]) if not (r.get('op')=='one_of' and any(str(v).endswith(('.cif','.vasp','.json')) for v in r.get('value',[])))]
        if tid=='SMAS-0048':
            ev['nodes']=[n for n in ev['nodes'] if not n['id'].startswith('mass_summary_')]
            for outcome in ev['outcomes']:
                if outcome['id'].startswith('pmf_max_'):
                    label=outcome['id'][-1]
                    outcome['right']={'operation':'max','args':[{'source':'node','node':'replacement_'+label,'path':'/pmf'}]}
                    outcome['evidence_nodes']=['replacement_'+label]
        if tid=='SMAS-0043':
            # FitLogisticRegression standardizes internally. Explicit preceding
            # population standardization is equivalent only if prediction uses
            # the same coordinate system; check the two routes coherently.
            import numpy as np
            raw=row['task']['inputs'];train=np.asarray(raw['training_features'],float);test=np.asarray(raw['heldout_features'],float)
            mean=train.mean(axis=0);scale=train.std(axis=0);scale[scale==0]=1
            standardized=((train-mean)/scale).tolist();heldout=((test-mean)/scale).tolist()
            fit=next(n for n in ev['nodes'] if n['id']=='fit')
            rule=next(r for r in fit['alternatives'][0]['input_rules'] if r.get('path')=='/training_features')
            rule.pop('right',None);rule.update(op='one_of',value=[raw['training_features'],standardized])
            pred=next(n for n in ev['nodes'] if n['id']=='probability');base_alt=pred['alternatives'][0]
            alternatives=[]
            for training,testing in [(raw['training_features'],raw['heldout_features']),(standardized,heldout)]:
                alt=deepcopy(base_alt)
                feature=next(r for r in alt['input_rules'] if r.get('path')=='/features')
                feature['right']={'value':testing}
                alt['input_rules'].append({'left':{'source':'node_arguments','node':'fit','path':'/training_features'},'op':'eq','value':training,'atol':1e-9,'rtol':1e-9})
                alternatives.append(alt)
            pred['alternatives']=alternatives
        if tid=='SMAS-0040':
            # An explicit squared norm of observed vectors is elementary
            # arithmetic. Do not require one particular calculator tool.
            def node(n,p):return {'source':'node','node':n,'path':p}
            def E(o,*a,**kw):return {'operation':o,'args':list(a),**kw}
            errors={}
            for label in 'abc':
                diffs=[E('subtract',node('state_'+label,'/product/'+str(i)),{'source':'inputs','path':'/target/'+str(i)}) for i in range(4)]
                errors[label]=E('sum',E('array',*[E('multiply',d,d) for d in diffs]))
            ev['nodes']=[n for n in ev['nodes'] if not n['id'].startswith('error_')]
            for out in ev['outcomes']:
                if out['id'].startswith('error_'):
                    label=out['id'][-1];out['right']=errors[label];out['evidence_nodes']=['state_'+label]
                if out['id']=='selected':
                    out['right']=E('argmin',E('paired_rows',{'value':['a','b','c']},E('array',*[errors[x] for x in 'abc'])),id_path='/0',value_path='/1',tie_atol=1e-9)
                    out['evidence_nodes']=['state_'+x for x in 'abc']
