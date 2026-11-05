"""Build the independently mapped Mini-200 without changing its source suites."""
from copy import deepcopy
from collections import Counter
import gzip,hashlib,json,shutil
from pathlib import Path
from src.utils.paths import project_root
from src.utils.io import read_jsonl,atomic_json
from evaluation.integrity.traces import canonical_sha256,read_trajectory,execution_calls
from scripts.benchmark.mini_notes import SELECTION,NOTES,REVIEW

ROOT=project_root();BASE=ROOT/'tasks/mini';SEED=ROOT/'evaluation/authoring/special100'


def asset_names(task):
    found=set()
    def visit(x):
        if isinstance(x,str) and (x.startswith('asset://') or x.startswith('qchem:asset://')):
            name=x.split('asset://',1)[1]
            if Path(name).name!=name:raise ValueError('Unsafe asset URI')
            found.add(name)
        elif isinstance(x,list):
            for v in x:visit(v)
        elif isinstance(x,dict):
            for v in x.values():visit(v)
    visit(task['inputs']);visit(task.get('files',[]));return found


def build():
    BASE.mkdir(exist_ok=True);(BASE/'assets').mkdir(exist_ok=True)
    (BASE/'evaluation/trajectories').mkdir(parents=True,exist_ok=True)
    full={r['id']:r for r in read_jsonl(ROOT/'tasks/full/questions.jsonl')}
    seed=read_jsonl(SEED/'questions.jsonl');assert len(seed)==100
    seed_refs={r['id']:r for r in read_jsonl(SEED/'evaluation/references.jsonl')}
    full_refs={r['id']:r for r in read_jsonl(ROOT/'evaluation/data/references.jsonl.gz')}
    seed_review={r['id']:r for r in json.loads((SEED/'evaluation/task_review.json').read_text())['tasks_review']}
    sources=[(t,seed_refs[t['id']],SEED,'special100',t['id'],None,seed_review[t['id']]['scientific_review']) for t in seed]
    picked=[]
    for domain,nums in SELECTION.items():
        assert len(nums)==25
        for number in nums:
            fid=f'FLOW-{number:04d}';source=full[fid];selection=REVIEW[number]
            assert source['domain']==domain and selection['category']!='high_difficulty'
            picked.append(fid)
            sources.append((source,full_refs[fid],ROOT/'tasks/full','full',fid,number,NOTES[number]))
    assert len(picked)==len(set(picked))==100 and len(sources)==200
    tasks=[];references=[];mapping=[];reviews=[];manifest={};needed=set();reference_ids=set()
    for i,(source,ref,release,origin,sid,number,note) in enumerate(sources,1):
        tid=f'SMAS-{i:04d}';task={**deepcopy(source),'id':tid};tasks.append(task)
        assert ref['id']==sid and sid not in reference_ids;reference_ids.add(sid)
        mapping.append((tid,origin,sid))
        current_ref=deepcopy(ref);raw_path=ROOT/ref['reference_trace']
        target=BASE/'evaluation/trajectories'/(sid+'.json.gz')
        # Compress only if the source is uncompressed. Never rewrite raw traces.
        if raw_path.suffix=='.gz':shutil.copyfile(raw_path,target)
        else:target.write_bytes(gzip.compress(raw_path.read_bytes(),mtime=0))
        current_ref['reference_trace']=str(target.relative_to(ROOT));references.append(current_ref)
        inventory=json.loads((release/'asset_manifest.json').read_text())['files']
        names=asset_names(task)
        for name in list(names):
            companion=Path(name).with_suffix('.provenance.json').name
            if companion in inventory and (release/'assets'/companion).is_file():names.add(companion)
        for name in sorted(names):
            raw=(release/'assets'/name).read_bytes();digest=hashlib.sha256(raw).hexdigest()
            assert inventory[name]['sha256']==digest
            if name in manifest:assert manifest[name]['sha256']==digest,'Conflicting public basename'
            else:
                manifest[name]={**inventory[name],'sha256':digest,'bytes':len(raw)}
                (BASE/'assets'/name).write_bytes(raw)
            needed.add(name)
        nodes=ref['evaluation']['nodes'];remaining={n['id']:set(n.get('depends_on',[])) for n in nodes};done=set();levels=[]
        while remaining:
            ready=sorted(n for n,d in remaining.items() if d<=done);assert ready
            levels.append(ready);done.update(ready)
            for n in ready:del remaining[n]
        trace=read_trajectory(target);calls=[c for c in execution_calls(trace) if c['tool']!='DescribeTools']
        tools=Counter(c['tool'] for c in calls if c['status']=='success')
        reviews.append({'id':tid,'origin':origin,'source_id':sid,'domain':task['domain'],
          'scientific_goal':REVIEW[number]['scientific_goal'] if number else seed_review[sid]['title'],
          'review_rationale':note,'source_public_task_sha256':canonical_sha256(source),
          'public_task_sha256':canonical_sha256(task),'scientific_content_changed':False,
          'reference_reused_without_raw_trace_edit':True,'reference_trace_sha256':ref['native_provenance']['trace_sha256'],
          'reference_scientific_calls':len(calls),'successful_tools':sorted(tools),
          'capability_depth':len(levels),'capability_width':max(map(len,levels)),
          'graph_fit':'multistage_dependency_graph' if len(levels)>1 else 'parallel_evidence_panel',
          'parallel_subtasks':REVIEW[number]['parallel_subtasks'] if number else seed_review[sid]['parallel_subtasks'],
          'scientific_join':REVIEW[number]['join_requirement'] if number else seed_review[sid]['scientific_join'],
          'category':REVIEW[number]['category'] if number else seed_review[sid]['difficulty_tier'],
          'leakage_review':'Reviewed public question, scientific measurement definitions and attached inputs; definitions/observed labels are not hidden answer keys.',
          'scope_limit':'Design-based fit, not empirical baseline advantage. Related method families are retained only for distinct scientific targets.'})
    for old in (BASE/'assets').iterdir():
        if old.is_file() and old.name not in needed:old.unlink()
    (BASE/'questions.jsonl').write_text(''.join(json.dumps(t,ensure_ascii=False,allow_nan=False)+'\n' for t in tasks))
    (BASE/'ids.tsv').write_text('mini_id\torigin\tsource_id\n'+''.join('\t'.join(row)+'\n' for row in mapping))
    raw=''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in references).encode()
    (BASE/'evaluation/references.jsonl.gz').write_bytes(gzip.compress(raw,mtime=0))
    atomic_json(BASE/'asset_manifest.json',{'files':manifest})
    schema=json.loads((SEED/'schema.json').read_text());schema['title']='SciToolFlow Mini-200 public task';atomic_json(BASE/'schema.json',schema)
    old_summary=json.loads((SEED/'evaluation/task_review.json').read_text())
    atomic_json(BASE/'selection.json',{'schema_version':'scitoolflow.mini.selection.v1','tasks':200,'origins':{'special100':100,'full':100},
       'policy':{'full_source_domain_quota':25,'merged_domain_quota':50,'exclude_high_difficulty_from_full':True,
        'selection_is_performance_based':False,'annotations_visible_to_agent':False,
        'identity_rule':'SMAS-0001..0100 preserve the existing Special IDs. SMAS-0101..0200 map bijectively to unchanged Full scientific tasks. References retain source IDs and genuine raw trajectories.',
        'primary_metrics':['runtime_completion_rate','tool_planning_accuracy','answer_accuracy']},
       'retained_special100_scope_limits':[x for x in old_summary['complex_graph_strengthening_candidates']],
       'source_files_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
          ROOT/'tasks/full/questions.jsonl',ROOT/'scripts/benchmark/mini_notes.py',SEED/'questions.jsonl',ROOT/'evaluation/data/references.jsonl.gz',SEED/'evaluation/references.jsonl']},
       'tasks_review':reviews})
    public_files=['questions.jsonl','ids.tsv','asset_manifest.json','schema.json']
    private_files=['selection.json','evaluation/references.jsonl.gz']
    atomic_json(BASE/'metadata.json',{'schema_version':'scitoolflow.mini.v1','name':'SciToolFlow Mini-200','dataset':'mini',
      'tasks':200,'id_range':'SMAS-0001..SMAS-0200','origins':{'special100':100,'full':100},
      'domains':dict(Counter(t['domain'] for t in tasks)),'full_source_domains':dict(Counter(r['domain'] for r in reviews if r['origin']=='full')),
      'graph_fit_counts':dict(Counter(r['graph_fit'] for r in reviews)),
      'reference_scientific_calls':sum(r['reference_scientific_calls'] for r in reviews),
      'references':'evaluation/references.jsonl.gz','reference_identity':'original source task IDs; public views are mapped, never raw trajectory relabels',
      'primary_metrics':['runtime_completion_rate','tool_planning_accuracy','answer_accuracy'],'performance_claim':'not measured',
      'sha256':{name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in public_files+private_files}})
    print(json.dumps({'tasks':len(tasks),'assets':len(manifest),'domains':dict(Counter(t['domain'] for t in tasks))}))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['build','check'],nargs='?',default='build')
    args=parser.parse_args()
    if args.command=='build':build()
    else:
        from evaluation.integrity.mini import validate_mini,audit_metric_boundaries
        report=validate_mini(ROOT);report['metric_boundary_audit']=audit_metric_boundaries(ROOT)
        atomic_json(BASE/'evaluation/acceptance.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in {'checks','metric_boundary_audit'}}))
        print(json.dumps({'wrong_scientific_fields_rejected':report['metric_boundary_audit']['wrong_scientific_fields_rejected']}))
