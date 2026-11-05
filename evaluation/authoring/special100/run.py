"""Run the separate special suite through the existing baseline runtimes."""
import argparse,hashlib,importlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
BASE=Path(__file__).resolve().parent;sys.path.insert(0,str(BASE))
from data import load_tasks
from src.models.client import GenerationClient
from tools import ToolCatalog,execute
from src.utils.io import atomic_json
from evaluation.integrity.traces import canonical_sha256
from baselines.scimas.assets import public_asset_scope


def run(args):
    selected=load_tasks(args.tasks);raw={t['id']:t for t in load_tasks(args.tasks,resolve=False)}
    output=Path(args.output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('Use a new output file; existing runs are preserved')
    method=getattr(importlib.import_module('baselines.'+args.baseline+'.runtime'),'run_'+args.baseline)
    client=GenerationClient(args.backend)
    if args.model:client.model=args.model
    catalog=ToolCatalog();predictions=[]
    previous={k:os.environ.get(k) for k in ['SCITOOLFLOW_WORK_DIR','SCITOOLFLOW_ARTIFACTS_DIR']}
    try:
        for task in selected:
            directory=output.parent/task['id'];directory.mkdir(exist_ok=False)
            for key,child in [('SCITOOLFLOW_WORK_DIR','work'),('SCITOOLFLOW_ARTIFACTS_DIR','artifacts')]:
                path=directory/child;path.mkdir();os.environ[key]=str(path)
            with public_asset_scope(BASE):
                result=method(task['question'],catalog=catalog,client=client,
                    invoke=lambda n,a,**kw:execute(n,a,catalog=catalog,**kw),trace_dir=directory/'trajectories',
                    case_id=task['id'],inputs=task['inputs'],files=task['files'],answer_schema=task['answer_schema'],
                    task_timeout=args.task_timeout,max_model_requests=args.max_model_requests)
            row={'id':task['id'],'dataset':result.get('dataset','full'),'baseline':args.baseline,
                'completed':result['status']=='completed','status':result['status'],'final_answer':result.get('final_answer'),
                'failure_reason':result.get('failure_reason'),'calls':result['calls'],'trace_path':result['trace_path'],
                'trace_sha256':hashlib.sha256(Path(result['trace_path']).read_bytes()).hexdigest(),
                'public_task_sha256':canonical_sha256(raw[task['id']])}
            predictions.append(row)
            atomic_json(output,{'suite':'scimas-special-100-v2','baseline':args.baseline,
                              'model':client.model,'predictions':predictions})
    finally:
        client.close()
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    return {'tasks':len(predictions),'completed':sum(p['completed'] for p in predictions),'output':str(output)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',choices=['react','scitoolagent','scimas'],required=True)
    p.add_argument('--backend',choices=['api','vllm','local'],default='vllm');p.add_argument('--model')
    p.add_argument('--tasks',default='all');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--task-timeout',type=float,default=7200);p.add_argument('--max-model-requests',type=int,default=400)
    a=p.parse_args()
    if a.task_timeout<=0 or a.max_model_requests<=0:p.error('Limits must be positive')
    print(json.dumps(run(a),ensure_ascii=False))
