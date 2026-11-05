"""Authoring helpers for explicit scientific graphs, never a task generator."""
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve();sys.path.insert(0,str(HERE.parents[1]))
from machine_learning import Study,V,I,N,E,refs
from revision import boolean

class Case(Study):
    def __init__(self,num,domain,tier,title,question,inputs,family,shared,parallel,join,limitation='Only the stated finite computational experiment is supported.'):
        super().__init__(num,title,question,inputs,tier=='advanced')
        self.domain,self.tier,self.family=domain,tier,family
        self.shared,self.parallel,self.join,self.limitation=shared,parallel,join,limitation
        self.extra_assets={}
    def emit(self):
        # Reusing an identical deterministic observation is legitimate. Every
        # node's object/method/input rules and dependency checks still apply.
        for node in self.nodes:
            tools=node['alternatives'][0]['tools']
            if len(tools)==1:node.setdefault('observation_reuse_group','identical_procedure_'+tools[0])
        review_equivalences(self)
        row=self.finish(self.shared,'; '.join(self.parallel))
        row['task']['domain']=self.domain
        row['design'].update(difficulty_tier=self.tier,task_family=self.family,
            shared_prerequisite=self.shared,parallel_scientific_subtasks=self.parallel,
            scientific_join=self.join,scientific_limitations=self.limitation,
            difficulty_basis=self.join,
            source_notes='Individually authored controlled scientific fixture. No experimental provenance, baseline performance selection, task-specific runtime shortcut or authored numerical gold. Targets are expressions over genuine registered tool observations.')
        if self.extra_assets:
            row['assets'].update(self.extra_assets)
            row['task']['files'].extend('asset://'+n for n in self.extra_assets)
        fields=', '.join(row['task']['answer_schema']['properties'])
        row['task']['question']+=f' Required output fields: {fields}. '+self.limitation
        row['_plan']=self.plan
        return row
    def asset(self,name,text):
        name=self.id+'_'+name;self.extra_assets[name]=text
        return V('asset://'+name)
    def out(self,*args,schema=None,**kwargs):
        super().out(*args,**kwargs)
        if schema:self.properties[args[0]]=schema
    def flag(self,key,left,op,right,**kwargs):boolean(self,key,left,op,right,**kwargs)

def vector(*args):return E('array',*args)
def matrix(rows):return E('numeric_rows',*[vector(*row) for row in rows])
def transpose(node,path,n,m):return matrix([[N(node,f'{path}/{i}/{j}') for i in range(n)] for j in range(m)])
def dot(a,b):return E('sum',vector(*[E('multiply',x,y) for x,y in zip(a,b)]))
def aliases(raw):
    from rdkit import Chem
    canonical=Chem.MolToSmiles(Chem.MolFromSmiles(raw),isomericSmiles=True)
    return list(dict.fromkeys([raw,canonical]))
def molecular(c,node,tool,raw,port='value'):
    c.add(node,tool,{'smiles':V(raw)})
    rule=c.nodes[-1]['alternatives'][0]['input_rules'][0]
    rule.pop('right');rule['op']='one_of';rule['value']=aliases(raw)
    return N(node,'/'+port)
def resolve_assets(value,base):
    if isinstance(value,str) and value.startswith('asset://'):return str((base/'assets'/value[8:]).resolve())
    if isinstance(value,list):return [resolve_assets(v,base) for v in value]
    if isinstance(value,dict):return {k:resolve_assets(v,base) for k,v in value.items()}
    return value


def review_equivalences(c):
    """Finite mathematical equivalences; no model-specific scoring concessions."""
    from copy import deepcopy
    for node in c.nodes:
        for alt in list(node['alternatives']):
            if alt['tools']==['CompareMolecularFingerprints'] and any(r.get('path')=='/algorithm' and r.get('right')==V('maccs') for r in alt['input_rules']):
                for rule in alt['input_rules']:
                    if rule.get('path')=='/options':rule.pop('right',None);rule.update(op='one_of',value=[None,{}])
            if alt['tools']==['PairwiseSequenceAlignment'] and any(r.get('path')=='/molecule_type' and r.get('right')==V('DNA') for r in alt['input_rules']):
                swapped=deepcopy(alt);rules={r.get('path'):r for r in swapped['input_rules']};rules['/sequence1']['right'],rules['/sequence2']['right']=rules['/sequence2']['right'],rules['/sequence1']['right'];node['alternatives'].append(swapped)
            if alt['tools']==['SolveLinearProgram']:
                # Row permutations must keep each RHS attached to its row.
                for stem in ['inequality','equality']:
                    paths=['/'+stem+'_matrix','/'+stem+'_rhs']
                    rules={r.get('path'):r for r in alt['input_rules'] if r.get('path') in paths}
                    if len(rules)==2:
                        alt['input_rules']=[r for r in alt['input_rules'] if r.get('path') not in paths]
                        alt['input_rules'].append({'left':E('paired_rows',{'source':'call_arguments','path':paths[0]},{'source':'call_arguments','path':paths[1]}),'op':'multiset_equal','right':E('paired_rows',rules[paths[0]]['right'],rules[paths[1]]['right']),'atol':1e-9,'rtol':1e-9})
            if alt['tools']==['MantelCorrelation'] and any(r.get('path')=='/permutations' and r.get('right')==V(0) for r in alt['input_rules']):
                swapped=deepcopy(alt);rules={r.get('path'):r for r in swapped['input_rules']}
                rules['/distance_a']['right'],rules['/distance_b']['right']=rules['/distance_b']['right'],rules['/distance_a']['right'];node['alternatives'].append(swapped)
    if c.id=='SMAS-0068':
        comp={n['id'] for n in c.nodes if n['alternatives'][0]['tools']==['GetElementComposition']}
        for node in c.nodes:
            if node['id'] in comp:
                alt=deepcopy(node['alternatives'][0]);alt['tools']=['ReadCrystalStructure']
                for r in alt['input_rules']:
                    if r.get('path')=='/file_name':r['path']='/structure_file'
                node['alternatives'].append(alt)
        def adapt(value):
            if isinstance(value,dict):
                if value.get('source')=='node' and value.get('node') in comp and value.get('path','').startswith('/element_amounts/'):
                    return E('crystal_element_amount',N(value['node'],''),V(value['path'].split('/')[-1]))
                return {k:adapt(v) for k,v in value.items()}
            if isinstance(value,list):return [adapt(v) for v in value]
            return value
        c.nodes=adapt(c.nodes);c.outcomes=adapt(c.outcomes)
