"""Validate all100 public studies, real references and three-metric grading boundaries."""
from copy import deepcopy
from pathlib import Path
import argparse,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
BASE=Path(__file__).resolve().parent;sys.path.insert(0,str(BASE))
from evaluate import rows,three_metrics,prediction_from_trace
from evaluation.workflow import validate_workflow,score_workflow
from evaluation.integrity.reference import validate_workflow_reference
from evaluation.integrity.traces import read_trajectory,canonical_sha256
from jsonschema import Draft202012Validator
from src.utils.io import atomic_json


def mutate(value):
    if isinstance(value,dict):
        out=deepcopy(value)
        for key,item in out.items():
            changed,done=mutate(item)
            if done:out[key]=changed;return out,True
    elif isinstance(value,list):
        out=deepcopy(value)
        for i,item in enumerate(out):
            changed,done=mutate(item)
            if done:out[i]=changed;return out,True
    elif type(value) in (int,float):return value+10000*(1+abs(value)),True
    return value,False


def validate(*,partial=False):
    tasks=rows(BASE/'questions.jsonl');criteria=rows(BASE/'evaluation/criteria.jsonl')
    refs=rows(BASE/'evaluation/references.jsonl') if (BASE/'evaluation/references.jsonl').exists() else {}
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    assert list(tasks)==[f'SMAS-{i:04d}' for i in range(1,101)]
    assert set(criteria)==set(tasks)
    strata=json.loads((BASE/'strata.json').read_text())
    assert {r['id'] for r in strata['tasks']}==set(tasks)
    assert strata['difficulty_counts']=={'advanced':28,'intermediate':52,'foundation':20}
    assert set(refs)=={p.name.removesuffix('.json.gz') for p in (BASE/'evaluation/trajectories').glob('*.json.gz')}
    assert {p.name for p in (BASE/'assets').iterdir() if p.is_file()}==set(json.loads((BASE/'asset_manifest.json').read_text())['files'])
    if not partial:assert set(refs)==set(tasks),'All100 need accepted native references'
    schema=json.loads((BASE/'schema.json').read_text());wfs=json.loads((ROOT/'evaluation/workflow/schema.json').read_text())
    for task in tasks.values():Draft202012Validator(schema).validate(task)
    manifest=json.loads((BASE/'asset_manifest.json').read_text())['files']
    for name,info in manifest.items():
        raw=(BASE/'assets'/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==info['sha256']
    checks=[];calls=0
    for tid,ref in sorted(refs.items()):
        task=tasks[tid];criterion=criteria[tid]
        assert canonical_sha256(ref['evaluation'])==canonical_sha256(criterion['evaluation'])
        validate_workflow(criterion['evaluation']);Draft202012Validator(wfs).validate(criterion['evaluation'])
        calls+=validate_workflow_reference(ROOT,task,ref,registry['tools'],registry)
        trace=read_trajectory(ROOT/ref['reference_trace']);p=prediction_from_trace(trace)
        good=three_metrics(task,criterion,p,p,registry)
        assert all(good[k] for k in ['runtime_completed','tool_plan_correct','answer_correct']),good
        missing=deepcopy(p);missing['calls']=[]
        independent=three_metrics(task,criterion,missing,p,registry)
        assert independent['answer_correct'] and not independent['tool_plan_correct'],independent
        bad=deepcopy(p);bad['final_answer']=None
        invalid=three_metrics(task,criterion,bad,p,registry)
        assert not invalid['runtime_completed'] and not invalid['answer_correct']
        changed,found=mutate(p['final_answer'])
        if found:
            bad=deepcopy(p);bad['final_answer']=changed
            assert not three_metrics(task,criterion,bad,p,registry)['answer_correct'],'Wrong science accepted: '+tid
        # Exercise every applicable scored answer port, not just the first one.
        baseline_score=score_workflow(criterion,p,aliases=registry.get('aliases',{}),tool_contracts=registry['tools'])
        applicable={o['id'] for o in baseline_score['outcomes'] if o.get('applicable') and o.get('required',True)}
        from evaluation.workflow.values import pointer
        checked_fields=set()
        for outcome in criterion['evaluation']['outcomes']:
            if outcome['id'] not in applicable:continue
            left=outcome.get('left',{})
            if left.get('source')!='answer':continue
            path=left.get('path','')
            if not path or path in checked_fields:continue
            tokens=[x.replace('~1','/').replace('~0','~') for x in path[1:].split('/')]
            edited=deepcopy(p['final_answer']);parent=edited
            for token in tokens[:-1]:parent=parent[int(token)] if isinstance(parent,list) else parent[token]
            key=int(tokens[-1]) if isinstance(parent,list) else tokens[-1]
            old=parent[key]
            new,changed=mutate(old)
            if not changed:
                if type(old) is bool:new=not old
                elif old is None:new=0
                elif isinstance(old,str):new='__wrong_scientific_value__'
                elif isinstance(old,list):new=['__wrong_scientific_value__']
                else:continue
            parent[key]=new
            bad=deepcopy(p);bad['final_answer']=edited
            assert not three_metrics(task,criterion,bad,p,registry)['answer_correct'],(tid,path,'Incorrect scored field accepted')
            checked_fields.add(path)
        checks.append({'id':tid,'reference_pass':True,'separate_metric_boundaries':True,
                       'wrong_value_rejected':found,'scored_field_mutations_rejected':len(checked_fields)})
    domains={d:sum(t['domain']==d for t in tasks.values()) for d in ['Chemical','Material','Biology','MachineLearning']}
    return {'status':'passed' if len(refs)==100 else 'partial','tasks':len(tasks),'accepted_references':len(refs),
            'domains':domains,'assets':len(manifest),'difficulty_counts':strata['difficulty_counts'],'scientific_reference_calls':calls,'task_checks':checks}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--partial',action='store_true')
    p.add_argument('--output',type=Path,default=BASE/'evaluation/acceptance.json');a=p.parse_args()
    r=validate(partial=a.partial);atomic_json(a.output,r)
    print(json.dumps({k:v for k,v in r.items() if k!='task_checks'},ensure_ascii=False))
