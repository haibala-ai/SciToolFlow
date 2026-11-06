"""Mini-200: authenticated execution and three independent scientific metrics."""
import hashlib,json
from pathlib import Path
from tasks.datasets import load_dataset
from tasks.schema import validation_errors
from src.utils.io import read_jsonl,atomic_json
from evaluation.workflow import score_workflow
from evaluation.integrity.traces import read_trajectory,execution_calls,authenticate_prediction,verify_release_envelope,canonical_sha256
from evaluation.integrity.resources import validate_policy,check_resources
from .reference_context import prediction_from_reference


def load_references(root,dataset=None):
    root=Path(root);data=dataset or load_dataset('mini',root);base=data.asset_root
    meta=json.loads((base/'metadata.json').read_text())
    for name in ['evaluation/references.jsonl.gz','selection.json']:
        if hashlib.sha256((base/name).read_bytes()).hexdigest()!=meta['sha256'][name]:
            raise ValueError('Mini private artifact identity mismatch: '+name)
    sources={r['id']:r for r in read_jsonl(base/meta['references'])}
    if len(sources)!=len(data.questions) or set(sources)!=set(data.source_ids.values()):raise ValueError('Mini references do not match the source mapping')
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


def three_metrics(task,criterion,prediction,reference_prediction,registry):
    answer=prediction.get('final_answer');shape=not validation_errors(answer,task['answer_schema'])
    actual=score_workflow(criterion,prediction,aliases=registry.get('aliases',{}),tool_contracts=registry['tools'])
    independent={**reference_prediction,'final_answer':answer}
    checked=score_workflow(criterion,independent,aliases=registry.get('aliases',{}),tool_contracts=registry['tools'])
    return {'id':task['id'],
      'runtime_completed':bool(prediction.get('completed') is True and prediction.get('status')=='completed' and not prediction.get('failure_reason')),
      'tool_plan_correct':bool(actual['planning_pass'] and not actual['pending_review']),
      'answer_correct':bool(checked['answer_pass'] and not checked['pending_review']),
      'answer_schema_valid':shape,
      'orchestration_credit':actual['orchestration_credit'],
      'selection_efficiency':actual['selection_efficiency'],
      'tool_orchestration_score':actual['tool_orchestration_score'],
      'planning_reportable':not actual['pending_review'],
      'planning_diagnostics':{'selected_routes':actual.get('selected_efficiency_routes',{}),
        'charged_scientific_calls':actual['charged_scientific_calls'],
        'matched_scientific_calls':actual['matched_scientific_calls'],
        'supporting_work_observations':actual.get('supporting_work_observations',[]),
        'redundant_semantic_observations':actual.get('redundant_semantic_observations',[])},
      'pending_review':bool(actual['pending_review'] or checked['pending_review'])}


def summarize(rows,dataset='mini'):
    """Macro-average per-task scores; missing/invalid evidence stays in denominator."""
    n=len(rows)
    if not n:raise ValueError('Cannot evaluate an empty Mini selection')
    mean=lambda field:sum(float(r.get(field,0)) for r in rows)/n
    reportable=all(r.get('planning_reportable',True) for r in rows)
    score=mean('tool_orchestration_score')
    return {'dataset':dataset,'tasks':n,'runtime_completion_rate':mean('runtime_completed'),
      'tool_planning_accuracy':score if reportable else None,
      'observed_mean_tool_orchestration_score':score,
      'tool_planning_reportable':reportable,
      'strict_tool_planning_accuracy':mean('tool_plan_correct'),
      'mean_orchestration_credit':mean('orchestration_credit'),
      'mean_selection_efficiency':mean('selection_efficiency'),
      'answer_accuracy':mean('answer_correct')}


def evaluate(root,predictions,output,task_ids=None,dataset='mini'):
    from tasks.datasets import MINI_DATASETS
    if dataset not in MINI_DATASETS:raise ValueError('Unknown Mini scoring dataset: '+str(dataset))
    root=Path(root).resolve();data=load_dataset(dataset,root);selected=data.select(task_ids)
    _,refs=load_references(root,data);registry=json.loads((root/'tools/catalog/catalog.json').read_text())
    path=Path(predictions).resolve();envelope=json.loads(path.read_text())
    fingerprint=verify_release_envelope(envelope,root,dataset=dataset)
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
            authenticated,integrity=authenticate_prediction(prediction,root,path.parent,registry,dataset=dataset)
            if prediction.get('public_task_sha256')!=canonical_sha256(task):
                integrity={'verified':False,'reason':'Public task identity mismatch'}
            if not integrity['verified']:
                row={'id':tid,'runtime_completed':False,'tool_plan_correct':False,'answer_correct':False,
                     'failure':'evidence_integrity','evidence_integrity':integrity}
            else:
                resource=None
                try:
                    resource=check_resources(authenticated,policy)
                except (ValueError,KeyError,TypeError) as error:
                    resource={'verified':False,'error':str(error)}
                row=three_metrics(task,refs[tid],authenticated,prediction_from_reference(root,refs[tid]),registry)
                row.update(evidence_integrity=integrity,resource_usage=resource,
                           resource_policy_compliant=bool(resource.get('verified') and not resource.get('exceeded')))
        row.update(domain=task['domain'],source_id=data.source_id(tid));result.append(row)
    summary=summarize(result,dataset=dataset)
    report={'schema_version':'scitoolflow.mini.three_metrics.v3','summary':summary,'dataset':dataset,
      'metric_definition_version':'independent-runtime-answer.v2',
      'tool_planning_definition':'Macro mean of per-task 3*C*E/(2*E+C), zero when C or E is zero; unavailable while planning review is pending.',
      'release_fingerprint':fingerprint,'primary_metrics':['runtime_completion_rate','tool_planning_accuracy','answer_accuracy'],
      'tasks':result,'llm_judge_used':False}
    atomic_json(output,report);return report
