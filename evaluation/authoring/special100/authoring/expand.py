"""Build and verify an independent candidate release without replacing active tasks."""
import argparse,gzip,hashlib,importlib,json,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
BASE=HERE.parent;WORK=ROOT/'results/special100_work';SOURCE=WORK/'source50';CANDIDATE=WORK/'candidate';RUNS=WORK/'native'
from src.utils.io import atomic_json
from evaluation.workflow import validate_workflow,public_answer_contract
from evaluation.integrity.traces import canonical_sha256
from jsonschema import Draft202012Validator

def records(path):return [json.loads(l) for l in path.read_text().splitlines() if l]
def snapshot():
    if not SOURCE.exists():
        shutil.copytree(BASE,SOURCE,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        atomic_json(WORK/'source_identity.json',{'questions_sha256':hashlib.sha256((SOURCE/'questions.jsonl').read_bytes()).hexdigest(),'scope':'Immutable public release snapshot and genuine reviewed references; no credentials.'})

def status():
    tasks=records(CANDIDATE/'questions.jsonl') if (CANDIDATE/'questions.jsonl').exists() else []
    refs=records(CANDIDATE/'evaluation/references.jsonl') if (CANDIDATE/'evaluation/references.jsonl').exists() else []
    refmap={r['id']:r for r in refs};qs={t['id']:t for t in tasks}
    accepted=[tid for tid,r in refmap.items() if tid in qs and r['native_provenance']['task_sha256']==canonical_sha256(qs[tid])]
    result={'phase':'individual_design_and_native_reference_review','target':100,'authored':len(tasks),'accepted_references':len(accepted),'accepted_ids':sorted(accepted),'pending_reference_ids':sorted(set(qs)-set(accepted)),'active_release_tasks':len(records(BASE/'questions.jsonl')),'candidate_directory':str(CANDIDATE.relative_to(ROOT)),'reference_runs':str(RUNS.relative_to(ROOT))}
    atomic_json(BASE/'progress.json',result);atomic_json(WORK/'progress.json',result);return result

def build():
    snapshot();CANDIDATE.mkdir(parents=True,exist_ok=True);(CANDIDATE/'assets').mkdir(exist_ok=True);(CANDIDATE/'evaluation/trajectories').mkdir(parents=True,exist_ok=True)
    tasks=records(SOURCE/'questions.jsonl');criteria=records(SOURCE/'evaluation/criteria.jsonl');designs=json.loads((SOURCE/'design.json').read_text())['studies']
    assets=json.loads((SOURCE/'asset_manifest.json').read_text())['files']
    for name in assets:shutil.copy2(SOURCE/'assets'/name,CANDIDATE/'assets'/name)
    if not (CANDIDATE/'evaluation/references.jsonl').exists():
        shutil.copy2(SOURCE/'evaluation/references.jsonl',CANDIDATE/'evaluation/references.jsonl')
        for p in (SOURCE/'evaluation/trajectories').iterdir():shutil.copy2(p,CANDIDATE/'evaluation/trajectories'/p.name)
    authored=[]
    for domain in ['chemical','material','biology','machine_learning']:
        if (HERE/'extension'/f'{domain}.py').exists():authored.extend(importlib.import_module('extension.'+domain).build())
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())['tools'];schema=json.loads((ROOT/'evaluation/workflow/schema.json').read_text())
    for row in authored:
        task=row['task'];ev=row['evaluation'];validate_workflow(ev);Draft202012Validator(schema).validate(ev)
        from compiler import asset_guards
        asset_guards(row,registry)
        for node in ev['nodes']:
            for alt in node['alternatives']:assert set(alt['tools'])<=set(registry),alt['tools']
        task['Parameter']=json.dumps(task['inputs'],ensure_ascii=False,sort_keys=True,allow_nan=False)
        task['answer_schema']['x-scoring-semantics']=public_answer_contract({'evaluation':ev})
        tasks=[t for t in tasks if t['id']!=task['id']];criteria=[t for t in criteria if t['id']!=task['id']];designs=[t for t in designs if t['id']!=task['id']]
        tasks.append(task);criteria.append({'id':task['id'],'inputs':task['inputs'],'evaluation':ev});designs.append({'id':task['id'],'domain':task['domain'],**row['design']})
        for name,data in row['assets'].items():
            assert Path(name).name==name and name.startswith(task['id'])
            raw=(data if isinstance(data,str) else json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();(CANDIDATE/'assets'/name).write_bytes(raw)
            assets[name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'provenance':row.get('asset_provenance',{}).get(name,'Individually specified synthetic scientific fixture; not empirical measurements.')}
    assert len({t['id'] for t in tasks})==len(tasks)
    for name,rows in [('questions.jsonl',tasks),('evaluation/criteria.jsonl',criteria)]:
        (CANDIDATE/name).write_text(''.join(json.dumps(t,ensure_ascii=False,allow_nan=False)+'\n' for t in sorted(rows,key=lambda t:t['id'])))
    atomic_json(CANDIDATE/'asset_manifest.json',{'files':assets});atomic_json(CANDIDATE/'design.json',{'studies':sorted(designs,key=lambda t:t['id'])})
    shutil.copy2(BASE/'schema.json',CANDIDATE/'schema.json');return status()

def start(tid,attempt=1):
    folder=RUNS/tid/f'attempt_{attempt}';folder.mkdir(parents=True,exist_ok=False)
    cmd=[sys.executable,str(ROOT/'scripts/references/native_reference_session.py'),'--task',tid,'--directory',str(folder),'--task-source',str(CANDIDATE/'questions.jsonl'),'--task-root',str(CANDIDATE),'--task-timeout','3600','--actor-turn-timeout','1200']
    with (folder/'session.log').open('wb') as log:process=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
    result={'id':tid,'attempt':attempt,'pid':process.pid,'directory':str(folder),'actor_directory':str(folder/'actor')};atomic_json(folder/'parent_session.json',result);return result

def preflight(tid):
    from extension.common import resolve_assets
    from evaluation.workflow.expressions import operand,predicate
    from tools import ToolCatalog,execute
    from src.utils.paths import CALL_DIRECTORIES
    runtime=WORK/'preflight_runtime'/tid
    for name in ['artifacts','work']:(runtime/name).mkdir(parents=True,exist_ok=True)
    CALL_DIRECTORIES.set({name:str((runtime/name).resolve()) for name in ['artifacts','work']})
    row=None
    for name in ['chemical','material','biology','machine_learning']:
        if not (HERE/'extension'/f'{name}.py').exists():continue
        for r in importlib.import_module('extension.'+name).build():
            if r['task']['id']==tid:row=r;break
        if row:break
    assert row,tid
    inputs=resolve_assets(row['task']['inputs'],CANDIDATE);ctx={'inputs':inputs,'nodes':{}};catalog=ToolCatalog(ROOT)
    files=[str((CANDIDATE/'assets'/n).resolve()) for n in row['assets']]
    branches={b['id']:b['when'] for b in row['evaluation'].get('branches',[])}
    checked=[]
    for nid,tool,args,branch in row['_plan']:
        if branch and not predicate(branches[branch],ctx):continue
        actual=resolve_assets({k:operand(v,ctx) for k,v in args.items()},CANDIDATE)
        response=execute(tool,actual,files=files,catalog=catalog,timeout=180)
        checked.append({'id':nid,'tool':tool,'status':response['status'],'error':response.get('error')})
        if response['status']!='success':break
        ctx['nodes'][nid]={'arguments':actual,'output':response['output']}
    report={'id':tid,'author_contract_preflight':True,'not_a_reference_trajectory':True,'status':'passed' if checked and all(x['status']=='success' for x in checked) else 'failed','checks':checked}
    atomic_json(WORK/'preflight'/f'{tid}.json',report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['build','start','status','preflight']);p.add_argument('id',nargs='?');p.add_argument('--attempt',type=int,default=1);a=p.parse_args()
    r=build() if a.command=='build' else start(a.id,a.attempt) if a.command=='start' else preflight(a.id) if a.command=='preflight' else status();print(json.dumps(r,ensure_ascii=False))
