"""Parent-only independent reference gates and compact, truthful provenance."""
from copy import deepcopy
from pathlib import Path
import gzip,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
BASE=Path(__file__).resolve().parents[1]
from evaluation.workflow import score_workflow,validate_workflow
from evaluation.integrity.traces import canonical_sha256,verify_trajectory,execution_calls
from evaluation.integrity.reference import validate_workflow_reference
from tasks.schema import validation_errors
from src.utils.io import atomic_json


def mapping(path):return {r['id']:r for r in map(json.loads,path.read_text().splitlines())}


def prediction(trace):
    return {'id':trace['task_id'],'dataset':trace.get('dataset','full'),'status':trace['status'],
      'completed':trace['status']=='completed','failure_reason':trace.get('failure_reason'),
      'final_answer':trace['final_answer'],'calls':execution_calls(trace)}


def review(tid,actor_id,notes,attempt=1,task_base=None,run_root=None,actor_metadata=None):
    base=Path(task_base or BASE)
    tasks=mapping(base/'questions.jsonl');criteria=mapping(base/'evaluation/criteria.jsonl')
    task,criterion=tasks[tid],criteria[tid];run=Path(run_root or ROOT/'results/special_native_references')/tid/f'attempt_{attempt}'
    result=json.loads((run/'candidate.json').read_text());trace=Path(result['trace_path']);raw=trace.read_bytes()
    traj=json.loads(raw);p=prediction(traj)
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    verify_trajectory(traj,p,registry)
    if not p['completed'] or validation_errors(p['final_answer'],task['answer_schema']):raise ValueError(tid+': incomplete or invalid answer')
    score=score_workflow(criterion,p,aliases=registry['aliases'],tool_contracts=registry['tools'])
    if not score['joint_pass'] or score['pending_review']:
        return {'id':tid,'status':'needs_review','missing_nodes':[n['id'] for n in score['nodes'] if n.get('applicable') and n.get('required') and not n['matched']],
                'failed_outcomes':[o['id'] for o in score['outcomes'] if o.get('applicable') and not o['passed']]}
    actor_record=actor_metadata if actor_metadata is not None else (json.loads((base/'authoring/actor_records.json').read_text()).get(tid,{}) if (base/'authoring/actor_records.json').exists() else {})
    trace_sha=hashlib.sha256(raw).hexdigest()
    review={'task_id':tid,'task_sha256':canonical_sha256(task),'trace_sha256':trace_sha,
      'evaluation_sha256':canonical_sha256(criterion['evaluation']),'status':'approved','reviewer':'root_independent_scientific_review',
      'checks':dict.fromkeys(['scientific_correctness','evidence_grounding','task_alignment','tool_contracts','orchestration'],True),
      'rationale':notes,'native_actor':{'id':actor_id,'model':'gpt-6.1-sol','fork_turns':'none','model_api_used':False,
       'information_boundary':'Only public task/request and broker. Not an OS/account isolation claim.','session_history':actor_record}}
    generation=json.loads((run/'generation_manifest.json').read_text())
    assert generation['public_task_sha256']==canonical_sha256(task),'Public task changed after generation'
    out=base/'evaluation/trajectories'/f'{tid}.json.gz';out.parent.mkdir(exist_ok=True)
    out.write_bytes(gzip.compress(raw,mtime=0))
    ref={'id':tid,'question':task['question'],'inputs':task['inputs'],'answer_contract':task['answer_schema'],
         'expected_answer':p['final_answer'],'evaluation':criterion['evaluation'],'reference_trace':str(out.relative_to(ROOT)),
         'native_provenance':{'actor_backend':'native_subagent','actor_id':actor_id,'model_api_used':False,
          'model':'gpt-6.1-sol','fork_turns':'none','actor_context_history':actor_record,'task_sha256':canonical_sha256(task),'trace_sha256':trace_sha,
          'task_identity':dict.fromkeys(['current_public_task_sha256','generation_task_sha256','review_task_sha256'],canonical_sha256(task)),
          'generation_manifest':generation,'generation_manifest_sha256':canonical_sha256(generation)},
         'review':{'status':'approved','reviewer':review['reviewer'],'reviewed_trace_sha256':trace_sha,'record':review,
                   'record_sha256':canonical_sha256(review)}}
    validate_workflow_reference(ROOT,task,ref,registry['tools'],registry)
    path=base/'evaluation/references.jsonl';refs=mapping(path) if path.exists() else {};refs[tid]=ref
    path.write_text(''.join(json.dumps(refs[k],ensure_ascii=False,allow_nan=False)+'\n' for k in sorted(refs)))
    atomic_json(base/'progress.json',{'phase':'clean_reference_generation_and_secondary_review','target':len(tasks),'authored':len(tasks),
        'accepted_references':len(refs),'accepted_ids':sorted(refs)})
    return {'id':tid,'status':'approved','scientific_calls':score['scientific_calls']}


if __name__=='__main__':
    tid=sys.argv[1];actor=sys.argv[2];note=sys.argv[3];attempt=int(sys.argv[4]) if len(sys.argv)>4 else 1
    print(json.dumps(review(tid,actor,note,attempt),ensure_ascii=False))
