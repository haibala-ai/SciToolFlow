"""Parent-side launch/status helpers for the existing native ReAct broker."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
BASE=Path(__file__).resolve().parents[1]
RUNS=ROOT/'results/special_native_references'
PYTHON=sys.executable


def start(tid,attempt=1,*,base=BASE,runs=RUNS,task_timeout=1800,actor_turn_timeout=900):
    base,runs=Path(base).resolve(),Path(runs).resolve()
    directory=runs/tid/('attempt_'+str(attempt))
    directory.mkdir(parents=True,exist_ok=False)
    command=[PYTHON,str(ROOT/'scripts/references/native_reference_session.py'),'--task',tid,
             '--directory',str(directory),'--task-source',str(base/'questions.jsonl'),'--task-root',str(base),
             '--task-timeout',str(task_timeout),'--actor-turn-timeout',str(actor_turn_timeout)]
    with (directory/'session.log').open('wb') as log:
        p=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=log,start_new_session=True)
    state={'id':tid,'attempt':attempt,'pid':p.pid,'directory':str(directory),'actor_directory':str(directory/'actor')}
    (directory/'parent_session.json').write_text(json.dumps(state,indent=2)+'\n')
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('id');p.add_argument('--attempt',type=int,default=1)
    p.add_argument('--directory',type=Path,default=BASE);p.add_argument('--runs',type=Path,default=RUNS)
    p.add_argument('--task-timeout',type=int,default=1800);p.add_argument('--actor-turn-timeout',type=int,default=900)
    a=p.parse_args();print(json.dumps(start(a.id,a.attempt,base=a.directory,runs=a.runs,
        task_timeout=a.task_timeout,actor_turn_timeout=a.actor_turn_timeout)))
