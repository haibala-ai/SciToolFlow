"""Three independent metrics for the separate SciMas Special-100 study suite."""
from copy import deepcopy
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
BASE=Path(__file__).resolve().parent
from evaluation.workflow import score_workflow
from evaluation.integrity.traces import read_trajectory,verify_trajectory,canonical_sha256,execution_calls,trajectory_bytes
from tasks.schema import validation_errors
from src.utils.io import atomic_json,read_jsonl


def rows(path):return {r['id']:r for r in read_jsonl(path)}


def prediction_from_trace(trace):
    return {'id':trace['task_id'],'dataset':trace.get('dataset','full'),'status':trace['status'],
        'completed':trace['status']=='completed','final_answer':trace.get('final_answer'),
        'failure_reason':trace.get('failure_reason'),'calls':execution_calls(trace)}


def three_metrics(task,criterion,prediction,reference_prediction,catalog):
    answer=prediction.get('final_answer')
    shape=not validation_errors(answer,task['answer_schema'])
    runtime=bool(prediction.get('completed') is True and prediction.get('status')=='completed'
                 and not prediction.get('failure_reason'))
    actual=score_workflow(criterion,prediction,aliases=catalog.get('aliases',{}),tool_contracts=catalog['tools'])
    # Ground scientific targets in trusted reference observations, independently
    # of whether this baseline chose a correct tool route. Never use its answer
    # to define a target or count its claimed observations as evidence.
    independent=deepcopy(reference_prediction);independent['final_answer']=answer
    checked=score_workflow(criterion,independent,aliases=catalog.get('aliases',{}),tool_contracts=catalog['tools'])
    scientific=checked['answer_pass'] and not checked['pending_review']
    return {'id':task['id'],'runtime_completed':runtime,
            'tool_plan_correct':bool(actual['planning_pass'] and not actual['pending_review']),
            'answer_correct':bool(scientific),'answer_schema_valid':shape}


def evaluate(predictions, *, selected=None,base=BASE):
    tasks=rows(base/'questions.jsonl');criteria=rows(base/'evaluation/criteria.jsonl')
    references=rows(base/'evaluation/references.jsonl')
    ids=list(tasks) if selected is None else selected
    if not ids or len(set(ids))!=len(ids) or set(ids)-tasks.keys():raise ValueError('Unknown/empty/duplicate task selection')
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    metadata=json.loads((base/'metadata.json').read_text())
    for file,key in [(base/'strata.json','strata_sha256'),(base/'questions.jsonl','public_questions_sha256'),(base/'evaluation/criteria.jsonl','criteria_sha256'),(base/'asset_manifest.json','asset_manifest_sha256'),(ROOT/'tools/catalog/catalog.json','catalogue_contract_sha256')]:
        if hashlib.sha256(file.read_bytes()).hexdigest()!=metadata[key]:raise ValueError('Stale Special-100 release: '+file.name)
    envelope=json.loads(Path(predictions).read_text())
    if isinstance(envelope,dict) and envelope.get('suite','scimas-special-100-v2')!='scimas-special-100-v2':raise ValueError('Foreign study suite')
    predicted=envelope.get('predictions') if isinstance(envelope,dict) else envelope
    if not isinstance(predicted,list):raise ValueError('Expected predictions list or checkpoint with predictions')
    mapping={r['id']:r for r in predicted}
    if len(mapping)!=len(predicted) or set(mapping)-tasks.keys():raise ValueError('Duplicate/foreign task IDs')
    out=[]
    for tid in ids:
        ref=references[tid];reftrace=read_trajectory(ROOT/ref['reference_trace'])
        reference_prediction=prediction_from_trace(reftrace)
        prediction=mapping.get(tid)
        if prediction is None:
            out.append({'id':tid,'runtime_completed':False,'tool_plan_correct':False,'answer_correct':False,'failure':'missing_prediction'});continue
        if prediction.get('public_task_sha256')!=canonical_sha256(tasks[tid]):raise ValueError(tid+': public task identity mismatch')
        path=Path(prediction['trace_path']);path=path if path.is_absolute() else Path(predictions).resolve().parent/path
        raw=trajectory_bytes(path)
        if hashlib.sha256(raw).hexdigest()!=prediction.get('trace_sha256'):
            raise ValueError(tid+': trajectory identity mismatch')
        trace=read_trajectory(path);verify_trajectory(trace,prediction,registry)
        if trace.get('question') not in (None,tasks[tid]['question']):raise ValueError(tid+': question mismatch')
        out.append(three_metrics(tasks[tid],criteria[tid],prediction,reference_prediction,registry))
    n=len(ids)
    summary={'tasks':n,'runtime_completion_rate':sum(r['runtime_completed'] for r in out)/n,
             'tool_planning_accuracy':sum(r['tool_plan_correct'] for r in out)/n,
             'answer_accuracy':sum(r['answer_correct'] for r in out)/n}
    return {'schema_version':'scimas.special.three_metrics.v2','suite':'scimas-special-100-v2','summary':summary,'tasks':out}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--predictions',required=True,type=Path)
    p.add_argument('--tasks',default='all');p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    result=evaluate(a.predictions,selected=None if a.tasks=='all' else a.tasks.split(','))
    atomic_json(a.output,result);print(json.dumps(result['summary'],ensure_ascii=False,indent=2))
