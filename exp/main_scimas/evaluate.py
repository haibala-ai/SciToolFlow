"""Verify the packaged results using their original, fingerprinted source trees."""
from pathlib import Path
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import tarfile
from datetime import datetime

BASE=Path(__file__).resolve().parent


def read(path):return json.loads(Path(path).read_text())


def source_tree(spec, packaged=False):
    source=Path(spec['source_root'])
    if source.is_dir() and not packaged:
        return source
    # Reconstruct immutable source/index and task files without changing the repository.
    dependency=spec['source_dependency'];archive=BASE/dependency['archive']
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==dependency['sha256']
    project=BASE.parents[1]
    key=Path(dependency['archive']).name.split('.')[0]
    source=project/'.local/cache/scimas_result_sources'/key
    if not (source/'.ready').exists():
        source.mkdir(parents=True,exist_ok=True)
        with tarfile.open(archive,'r:gz') as bundle:
            for member in bundle:
                rel=Path(member.name)
                assert member.isfile() and not rel.is_absolute() and '..' not in rel.parts
                target=source/rel;target.parent.mkdir(parents=True,exist_ok=True)
                with bundle.extractfile(member) as stream:
                    target.write_bytes(stream.read())
        hashes=read(BASE/dependency['actor_file_hashes'])
        for name,expected in hashes.items():
            assert hashlib.sha256((source/name).read_bytes()).hexdigest()==expected,name
        (source/'.ready').write_text(dependency['sha256']+'\n')
    dataset=read(BASE/'metadata/dataset_snapshot.json')
    marker=source/'.dataset.sha256'
    if not marker.exists() or marker.read_text().strip()!=dataset['sha256']:
        archive=BASE/dataset['archive']
        assert hashlib.sha256(archive.read_bytes()).hexdigest()==dataset['sha256']
        with tarfile.open(archive,'r:gz') as bundle:
            for member in bundle:
                rel=Path(member.name)
                assert member.isfile() and not rel.is_absolute() and '..' not in rel.parts and rel.parts[0]=='tasks'
                target=source/rel;target.parent.mkdir(parents=True,exist_ok=True)
                if target.is_symlink():target.unlink()
                with bundle.extractfile(member) as stream:target.write_bytes(stream.read())
        marker.write_text(dataset['sha256']+'\n')
    return source


def main():
    sources=read(BASE/'metadata/sources.json')['sources']
    expected=read(BASE/'scores.json');actual={}
    reports=[]
    for spec in sources:
        source=source_tree(spec,packaged='--packaged-sources' in sys.argv)
        envelope=read(BASE/spec['predictions_file'])
        assert envelope['fingerprint']==spec['fingerprint']
        assert {r['id'] for r in envelope['predictions']}==set(spec['selected_ids'])
        for row in envelope['predictions']:
            path=Path(row['trace_path'])
            path=(path if path.is_absolute() else BASE/path).resolve()
            assert path.is_relative_to(BASE/'trajectories') and path.is_file()
            assert hashlib.sha256(path.read_bytes()).hexdigest()==row['trace_sha256']
            row['trace_path']=str(path)
        # Temporary production inputs live at the package root so trace files
        # remain inside the evaluator's explicitly authorized run directory.
        pred=tempfile.NamedTemporaryFile(mode='w',prefix='.evaluation-',suffix='.json',dir=BASE,delete=False)
        out=tempfile.NamedTemporaryFile(prefix='.score-',suffix='.json',dir=BASE,delete=False);out.close()
        try:
            json.dump(envelope,pred,ensure_ascii=False);pred.close()
            env=dict(os.environ,SCITOOLFLOW_ROOT=str(source),PYTHONPATH=str(source),PYTHONDONTWRITEBYTECODE='1')
            cmd=[sys.executable,str(source/'cli.py'),'score','--dataset','mini-100',
                 '--tasks',','.join(spec['selected_ids']),'--predictions',pred.name,'--output',out.name]
            result=subprocess.run(cmd,cwd=source,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
            if result.returncode:raise RuntimeError('Offline scoring failed: '+result.stdout[-2000:])
            report=read(out.name)
            for row in report['tasks']:
                assert row['id'] not in actual
                assert row.get('evidence_integrity',{}).get('verified'),row
                actual[row['id']]=row
            reports.append({'source_id':spec['id'],'verified_tasks':len(report['tasks'])})
            print('Verified',len(report['tasks']),'tasks from',spec['id'],flush=True)
        finally:
            pred.close();Path(pred.name).unlink(missing_ok=True);Path(out.name).unlink(missing_ok=True)
    assert len(actual)==100
    fields=('runtime_completed','tool_plan_correct','answer_correct','orchestration_credit',
            'selection_efficiency','tool_orchestration_score','planning_reportable','pending_review')
    for old in expected['tasks']:
        new=actual[old['id']]
        for field in fields:
            a,b=old.get(field),new.get(field)
            if type(a) in (float,int) and type(b) in (float,int):
                assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12),(old['id'],field,a,b)
            else:assert a==b,(old['id'],field,a,b)
    metrics=read(BASE/'task_metrics.json')['tasks'];predictions=read(BASE/'predictions.json')['predictions']
    byid={r['id']:r for r in metrics};assert len(byid)==100
    for row in predictions:
        assert all(byid[row['id']].get(k)==v for k,v in row['metrics'].items())
    manifest=read(BASE/'metadata/verification.json')
    manifest.update(status='passed',offline_scoring_verified=True,scientific_scores_unchanged=True,
        verified_at=datetime.now().astimezone().isoformat(),sources=reports,model_requests=0,tool_calls=0)
    tmp=BASE/'metadata/.verification.tmp';tmp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    tmp.replace(BASE/'metadata/verification.json')
    print('All 100 trajectories authenticated. Scientific scores, time, calls and token metrics preserved.')


if __name__=='__main__':main()
