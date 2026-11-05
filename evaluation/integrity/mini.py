"""Validate mapped source references without relabelling genuine trajectories."""
from collections import Counter
import hashlib,json
from pathlib import Path
from tasks.datasets import load_dataset
from tasks.assets import load_agent_input
from evaluation.integrity.reference import validate_workflow_reference
from evaluation.suites.mini import load_references,prediction_from_reference,three_metrics


def validate_mini(root):
    root=Path(root);base=root/'tasks/mini';data=load_dataset('mini',root)
    sources,views=load_references(root,data)
    validate_selection(root,data,json.loads((base/'selection.json').read_text()))
    registry=json.loads((root/'tools/catalog/catalog.json').read_text())
    inventory=json.loads((base/'asset_manifest.json').read_text())['files']
    from jsonschema import Draft202012Validator
    schema=Draft202012Validator(json.loads((base/'schema.json').read_text()))
    for name,info in inventory.items():
        file=(base/'assets'/name).resolve()
        if file.parent!=(base/'assets').resolve() or hashlib.sha256(file.read_bytes()).hexdigest()!=info['sha256']:
            raise ValueError('Mini asset identity mismatch: '+name)
    if Counter(q['domain'] for q in data.questions)!=dict.fromkeys(['Biology','Chemical','Material','MachineLearning'],50):
        raise ValueError('Mini requires50 tasks per domain')
    checks=[]
    for task in data.questions:
        schema.validate(task)
        sid=data.source_id(task['id']);source=sources[sid];original={**task,'id':sid}
        calls=validate_workflow_reference(root,original,source,registry['tools'],registry)
        load_agent_input(task,base)
        p=prediction_from_reference(root,source)
        scored=three_metrics(task,views[task['id']],p,p,registry)
        if not all(scored[k] for k in ['runtime_completed','tool_plan_correct','answer_correct']):raise ValueError('Mini reference self-check failed: '+task['id'])
        checks.append({'id':task['id'],'source_id':sid,'scientific_calls':calls,'three_metrics_pass':True})
    return {'status':'passed','tasks':200,'references':len(sources),'domains':dict(Counter(q['domain'] for q in data.questions)),
            'raw_trajectories_relabelled':False,'checks':checks}


def audit_metric_boundaries(root):
    """One-time release audit; scoring never executes a submitted program/model."""
    from copy import deepcopy
    from evaluation.workflow import score_workflow
    root=Path(root);dataset=load_dataset('mini',root);_,refs=load_references(root,dataset)
    registry=json.loads((root/'tools/catalog/catalog.json').read_text());checks=[]
    def mutate(value):
        if type(value) is bool:return not value
        if type(value) in (int,float):return value+10000*(1+abs(value))
        if value is None:return 0
        if isinstance(value,str):return '__wrong_scientific_value__'
        if isinstance(value,list):
            if not value:return ['__wrong_scientific_value__']
            return [mutate(value[0])]+deepcopy(value[1:])
        if isinstance(value,dict):
            edited=deepcopy(value)
            if not edited:return {'__wrong__':True}
            key=next(iter(edited));edited[key]=mutate(edited[key]);return edited
        raise ValueError('Unsupported answer value')
    for task in dataset.questions:
        tid=task['id'];ref=refs[tid];pred=prediction_from_reference(root,ref)
        missing={**pred,'calls':[]}
        score=three_metrics(task,ref,missing,pred,registry)
        if score['tool_plan_correct'] or not score['answer_correct']:raise ValueError('Metric coupling: '+tid)
        graded=score_workflow(ref,pred,aliases=registry.get('aliases',{}),tool_contracts=registry['tools'])
        active={o['id'] for o in graded['outcomes'] if o.get('applicable') and o.get('required',True)}
        paths=set()
        for outcome in ref['evaluation']['outcomes']:
            left=outcome.get('left',{});path=left.get('path','')
            if outcome['id'] not in active or left.get('source')!='answer' or not path or path in paths:continue
            edited=deepcopy(pred['final_answer']);tokens=[v.replace('~1','/').replace('~0','~') for v in path[1:].split('/')]
            parent=edited
            for token in tokens[:-1]:parent=parent[int(token)] if isinstance(parent,list) else parent[token]
            key=int(tokens[-1]) if isinstance(parent,list) else tokens[-1];parent[key]=mutate(parent[key])
            bad={**pred,'final_answer':edited}
            if three_metrics(task,ref,bad,pred,registry)['answer_correct']:raise ValueError('Wrong scientific field accepted: '+tid+path)
            paths.add(path)
        checks.append({'id':tid,'independent_metric_boundaries':True,'wrong_scientific_fields_rejected':len(paths)})
    return {'tasks':len(checks),'wrong_scientific_fields_rejected':sum(x['wrong_scientific_fields_rejected'] for x in checks),'checks':checks}


def validate_selection(root,dataset,selection):
    """Check scientific-source eligibility, not an author-supplied difficulty label."""
    rows=selection.get('tasks_review',[]);by_id={q['id']:q for q in dataset.questions}
    if len(rows)!=200 or len({r['id'] for r in rows})!=200 or set(r['id'] for r in rows)!=set(by_id):
        raise ValueError('Mini selection needs200 unique task records')
    added=[r for r in rows if r['origin']=='full']
    if len(added)!=100 or Counter(r['domain'] for r in added)!=dict.fromkeys(['Chemical','Material','Biology','MachineLearning'],25):
        raise ValueError('Full-source selection needs25 tasks per domain')
    index={r['id']:r for r in json.loads((Path(root)/'tasks/full/index.json').read_text())['tasks']}
    for row in rows:
        task=by_id[row['id']]
        if row['public_task_sha256']!=canonical_task_hash(task) or row['source_id']!=dataset.source_id(row['id']):
            raise ValueError('Mini selection task/source identity differs')
        branches=row.get('parallel_subtasks',[])
        if not isinstance(branches,list) or len(branches)<2 or len(set(branches))!=len(branches):
            raise ValueError('Independent branch descriptions must be distinct')
        if row['origin']=='full':
            original=index.get(row['source_id'])
            if original is None or original['category']=='high_difficulty':raise ValueError('High-difficulty or missing source is ineligible')
            if original['domain']!=task['domain'] or row['domain']!=task['domain']:raise ValueError('Wrong source discipline')
    return True


def canonical_task_hash(task):
    from evaluation.integrity.traces import canonical_sha256
    return canonical_sha256(task)
