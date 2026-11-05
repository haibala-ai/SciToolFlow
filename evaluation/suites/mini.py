"""Mini-200: authenticated execution and three independent scientific metrics."""
import hashlib,json
from pathlib import Path
from tasks.datasets import load_dataset
from tasks.schema import validation_errors
from src.utils.io import read_jsonl,atomic_json
from evaluation.workflow import score_workflow
from evaluation.integrity.traces import read_trajectory,execution_calls,authenticate_prediction,verify_release_envelope,canonical_sha256
from evaluation.integrity.resources import validate_policy,check_resources


def load_references(root,dataset=None):
    root=Path(root);base=root/'tasks/mini';data=dataset or load_dataset('mini',root)
    meta=json.loads((base/'metadata.json').read_text())
    for name in ['evaluation/references.jsonl.gz','selection.json']:
        if hashlib.sha256((base/name).read_bytes()).hexdigest()!=meta['sha256'][name]:
            raise ValueError('Mini private artifact identity mismatch: '+name)
    sources={r['id']:r for r in read_jsonl(base/meta['references'])}
    if len(sources)!=200 or set(sources)!=set(data.source_ids.values()):raise ValueError('Mini references do not match the source mapping')
    views={}
    for task in data.questions:
        source=sources[data.source_id(task['id'])]
        original={**task,'id':source['id']}
        if (source['question']!=original['question'] or source['inputs']!=original['inputs']
            or source['answer_contract']!=original['answer_schema']
            or source['native_provenance']['task_identity']['current_public_task_sha256']!=canonical_sha256(original)):
            raise ValueError('Mini scientific task/source reference differs: '+task['id'])
        # Only the workflow grading view receives the public ID. The stored
        # generation manifest,review,reference and raw trajectory keep source IDs.
        views[task['id']]={**source,'id':task['id']}
    return sources,views


def prediction_from_reference(root,reference):
    trace=read_trajectory(Path(root)/reference['reference_trace'])
    return {'id':trace['task_id'],'dataset':trace.get('dataset','full'),'status':trace['status'],
            'completed':trace['status']=='completed','failure_reason':trace.get('failure_reason'),
            'final_answer':trace['final_answer'],'calls':execution_calls(trace)}


def three_metrics(task,criterion,prediction,reference_prediction,registry):
    answer=prediction.get('final_answer');shape=not validation_errors(answer,task['answer_schema'])
    actual=score_workflow(criterion,prediction,aliases=registry.get('aliases',{}),tool_contracts=registry['tools'])
    independent={**reference_prediction,'final_answer':answer}
    checked=score_workflow(criterion,independent,aliases=registry.get('aliases',{}),tool_contracts=registry['tools'])
    return {'id':task['id'],
      'runtime_completed':bool(prediction.get('completed') is True and prediction.get('status')=='completed' and not prediction.get('failure_reason') and shape),
      'tool_plan_correct':bool(actual['planning_pass'] and not actual['pending_review']),
      'answer_correct':bool(shape and checked['answer_pass'] and not checked['pending_review']),
      'pending_review':bool(actual['pending_review'] or checked['pending_review'])}


def evaluate(root,predictions,output,task_ids=None):
    root=Path(root).resolve();data=load_dataset('mini',root);selected=data.select(task_ids)
    _,refs=load_references(root,data);registry=json.loads((root/'tools/catalog/catalog.json').read_text())
    path=Path(predictions).resolve();envelope=json.loads(path.read_text())
    fingerprint=verify_release_envelope(envelope,root,dataset='mini')
    policy=validate_policy(envelope['settings'].get('resource_policy'))
    rows=envelope.get('predictions')
    if not isinstance(rows,list):raise ValueError('Checkpoint predictions must be an array')
    by_id={r['id']:r for r in rows}
    if len(by_id)!=len(rows) or set(by_id)-set(data.source_ids):raise ValueError('Duplicate/foreign Mini prediction IDs')
    result=[]
    for task in selected:
        tid=task['id'];prediction=by_id.get(tid)
        if prediction is None:
            row={'id':tid,'runtime_completed':False,'tool_plan_correct':False,'answer_correct':False,'failure':'missing_prediction'}
        else:
            authenticated,integrity=authenticate_prediction(prediction,root,path.parent,registry,dataset='mini')
            if prediction.get('public_task_sha256')!=canonical_sha256(task):
                integrity={'verified':False,'reason':'Public task identity mismatch'}
            if not integrity['verified']:
                row={'id':tid,'runtime_completed':False,'tool_plan_correct':False,'answer_correct':False,
                     'failure':'evidence_integrity','evidence_integrity':integrity}
            else:
                resource=None
                try:
                    resource=check_resources(authenticated,policy)
                    if resource['exceeded']:authenticated.update(completed=False,status='failed',failure_reason='ExperimentResourceBudgetExceeded')
                except (ValueError,KeyError,TypeError) as error:
                    row={'id':tid,'runtime_completed':False,'tool_plan_correct':False,'answer_correct':False,
                         'failure':'resource_integrity','reason':str(error)}
                else:
                    row=three_metrics(task,refs[tid],authenticated,prediction_from_reference(root,refs[tid]),registry)
                    row.update(evidence_integrity=integrity,resource_usage=resource)
        row.update(domain=task['domain'],source_id=data.source_id(tid));result.append(row)
    n=len(result)
    summary={'dataset':'mini','tasks':n,'runtime_completion_rate':sum(x['runtime_completed'] for x in result)/n,
      'tool_planning_accuracy':sum(x['tool_plan_correct'] for x in result)/n,'answer_accuracy':sum(x['answer_correct'] for x in result)/n}
    report={'schema_version':'scitoolflow.mini.three_metrics.v1','summary':summary,'dataset':'mini',
      'release_fingerprint':fingerprint,'primary_metrics':['runtime_completion_rate','tool_planning_accuracy','answer_accuracy'],
      'tasks':result,'llm_judge_used':False}
    atomic_json(output,report);return report
