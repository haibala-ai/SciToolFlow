"""Validate mapped source references without relabelling genuine trajectories."""
from collections import Counter
import hashlib,json
from pathlib import Path
from tasks.datasets import load_dataset
from tasks.assets import load_agent_input
from evaluation.integrity.reference import validate_workflow_reference
from evaluation.suites.mini import load_references,prediction_from_reference,three_metrics,summarize


def validate_mini(root,dataset='mini'):
    root=Path(root);data=load_dataset(dataset,root);base=data.asset_root
    from tasks.datasets import MINI_DATASETS
    if data.name not in MINI_DATASETS:raise ValueError('Expected a Mini dataset')
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
    domains=Counter(q['domain'] for q in data.questions)
    if data.name=='mini' and domains!=dict.fromkeys(['Biology','Chemical','Material','MachineLearning'],50):
        raise ValueError('Mini requires50 tasks per domain')
    if data.name=='mini-100':
        import random
        sampling=json.loads((base/'sampling.json').read_text())
        if (sampling.get('method')!='uniform_without_replacement' or sampling.get('stratified') is not False
            or sampling.get('draws_performed')!=1
            or random.Random(sampling['seed']).sample(sampling['population_ids'],100)!=sampling['drawn_ids']):
            raise ValueError('Mini-100 sampling record is not the declared uniform draw')
        if dict(domains)!=json.loads((base/'metadata.json').read_text())['domains']:
            raise ValueError('Mini-100 domain counts differ from its frozen sample')
    checks=[];scores=[]
    for task in data.questions:
        schema.validate(task)
        sid=data.source_id(task['id']);source=sources[sid];original={**task,'id':sid}
        calls=validate_workflow_reference(root,original,source,registry['tools'],registry)
        load_agent_input(task,base)
        p=prediction_from_reference(root,source)
        scored=three_metrics(task,views[task['id']],p,p,registry)
        if not all(scored[k] for k in ['runtime_completed','tool_plan_correct','answer_correct']):raise ValueError('Mini reference self-check failed: '+task['id'])
        scores.append(scored)
        checks.append({'id':task['id'],'source_id':sid,'scientific_calls':calls,
            'runtime_completed':True,'necessary_capabilities_complete':True,'answer_correct':True,
            'orchestration_credit':scored['orchestration_credit'],
            'selection_efficiency':scored['selection_efficiency'],
            'tool_orchestration_score':scored['tool_orchestration_score']})
    return {'status':'passed','dataset':data.name,'tasks':len(data.questions),'references':len(sources),'domains':dict(domains),
            'raw_trajectories_relabelled':False,'reference_metrics':summarize(scores,dataset=data.name),
            'reference_metrics_are_not_baseline_model_results':True,'checks':checks}


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
            left=outcome.get('left',{})
            if left.get('operation') in {'distance_matrix','divide'}:
                from evaluation.workflow.schema import _selectors
                choices=[s for s in _selectors(left) if s.get('source')=='answer']
                left=next((s for s in choices if s.get('path')=='/'+outcome['id']), choices[0] if choices else {})
            path=left.get('path','')
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
    if len(rows)!=len(dataset.questions) or len({r['id'] for r in rows})!=len(dataset.questions) or set(r['id'] for r in rows)!=set(by_id):
        raise ValueError('Mini selection needs aligned unique task records')
    added=[r for r in rows if r['origin']=='full']
    if dataset.name=='mini' and (len(added)!=100 or Counter(r['domain'] for r in added)!=dict.fromkeys(['Chemical','Material','Biology','MachineLearning'],25)):
        raise ValueError('Full-source selection needs25 tasks per domain')
    index=({r['id']:r for r in json.loads((Path(root)/'tasks/full/index.json').read_text())['tasks']}
           if dataset.name=='mini' else {})
    for row in rows:
        task=by_id[row['id']]
        if row['public_task_sha256']!=canonical_task_hash(task) or row['source_id']!=dataset.source_id(row['id']):
            raise ValueError('Mini selection task/source identity differs')
        branches=row.get('parallel_subtasks',[])
        if not isinstance(branches,list) or len(branches)<2 or len(set(branches))!=len(branches):
            raise ValueError('Independent branch descriptions must be distinct')
        if row['origin']=='full':
            if dataset.name=='mini':
                original=index.get(row['source_id'])
                if original is None or original['category']=='high_difficulty':raise ValueError('High-difficulty or missing source is ineligible')
                if original['domain']!=task['domain']:raise ValueError('Wrong source discipline')
            if row['domain']!=task['domain']:raise ValueError('Wrong source discipline')
    return True


def canonical_task_hash(task):
    from evaluation.integrity.traces import canonical_sha256
    return canonical_sha256(task)
