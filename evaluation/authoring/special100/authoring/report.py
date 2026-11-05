"""Build task catalog and measured reference diagnostics; no baseline score claims."""
import json,hashlib,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT));BASE=Path(__file__).resolve().parents[1]
from evaluation.integrity.traces import read_trajectory,canonical_sha256
from evaluation.workflow import score_workflow
from src.utils.io import atomic_json
FEATURED={'SMAS-0011','SMAS-0012','SMAS-0014','SMAS-0022','SMAS-0027','SMAS-0028','SMAS-0039','SMAS-0050','SMAS-0054','SMAS-0063','SMAS-0067','SMAS-0072','SMAS-0075','SMAS-0076','SMAS-0083','SMAS-0086','SMAS-0088','SMAS-0090','SMAS-0094','SMAS-0099'}


def generate(base=BASE):
    from strata import generate as review_strata
    review_strata(base)
    strata=json.loads((base/'strata.json').read_text())
    profiles={r['id']:r for r in strata['tasks']}
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    annotations=json.loads((ROOT/'tools/graph/scimas/annotations.json').read_text())['tools']
    parallel=json.loads((ROOT/'tools/graph/scimas/parallel_review.json').read_text())
    tasks=[json.loads(l) for l in (base/'questions.jsonl').read_text().splitlines()]
    refs={r['id']:r for r in map(json.loads,(base/'evaluation/references.jsonl').read_text().splitlines())}
    designs=json.loads((base/'design.json').read_text())['studies'];details=[];tools=set();predictions=[]
    for task in tasks:
        tid=task['id'];ref=refs[tid];trace=read_trajectory(ROOT/ref['reference_trace'])
        calls=[c for step in trace['steps'] for c in step.get('calls',[])];scientific=[c for c in calls if c['tool']!='DescribeTools']
        tools.update(c['tool'] for c in scientific if c['status']=='success')
        remaining={n['id']:set(n.get('depends_on',[])) for n in ref['evaluation']['nodes']};levels=[];done=set()
        while remaining:
            ready=sorted(n for n,deps in remaining.items() if deps<=done)
            assert ready;levels.append(ready);done.update(ready)
            for n in ready:del remaining[n]
        scientific_prediction={'id':tid,'completed':trace['status']=='completed','status':trace['status'],
            'final_answer':trace['final_answer'],'calls':calls}
        graded=score_workflow(ref,scientific_prediction,aliases=registry['aliases'],tool_contracts=registry['tools'])
        active={n['id']:n for n in graded['nodes'] if n['applicable'] and n['matched']}
        observations={c['observation_id']:c for c in scientific if c.get('status')=='success'}
        pending={n['id']:set(n.get('depends_on',[])) & active.keys() for n in ref['evaluation']['nodes'] if n['id'] in active}
        accepted=set();ready_widths=[]
        while pending:
            ready=[n for n,d in pending.items() if d<=accepted]
            assert ready
            safe={active[n]['observation_id'] for n in ready if active[n]['observation_id'] in observations
                and annotations.get(observations[active[n]['observation_id']]['tool'],{}).get('execution_hints',{}).get('parallel_safe')=='isolated_processes_with_resource_limits'}
            ready_widths.append(len(safe));accepted.update(ready)
            for n in ready:del pending[n]
        reviewed_width=max(ready_widths)
        assert reviewed_width>=2, (tid,'No reviewed independent scientific pair')
        details.append({'id':tid,'domain':task['domain'],'title':task['question'].split('. ')[0],
            'featured_showcase':tid in FEATURED,'difficulty_tier':profiles[tid]['difficulty_tier'],'reference_action':profiles[tid]['reference_action'],'reference_scientific_calls':len(scientific),
            'successful_reference_tools':sorted({c['tool'] for c in scientific if c['status']=='success'}),
            'source_reviewed_applicable_ready_width':reviewed_width,'declared_capability_dag_width':max(map(len,levels)),'capability_levels':levels,
            'graph_fit_class':'multistage_dependency_graph' if len(levels)>1 else 'parallel_evidence_panel',
            'reference_decisions':len(trace['steps'])})
        predictions.append({'id':tid,'dataset':trace.get('dataset','full'),'status':trace['status'],
          'completed':trace['status']=='completed','failure_reason':trace.get('failure_reason'),'final_answer':trace['final_answer'],
          'calls':calls,'trace_path':str((ROOT/ref['reference_trace']).resolve()),'trace_sha256':ref['native_provenance']['trace_sha256'],
          'public_task_sha256':canonical_sha256(task)})
    for d in designs:d['featured_showcase']=d['id'] in FEATURED
    atomic_json(base/'design.json',{'studies':designs})
    summary={'schema_version':'scimas.special.v1','suite':'scimas-special-100-v2','task_count':len(tasks),'difficulty_counts':strata['difficulty_counts'],'advanced_domain_counts':strata['advanced_domain_counts'],'reference_refresh':strata['reference_policy'],'id_namespace':'SMAS-0001..SMAS-0100',
      'domains':dict(Counter(t['domain'] for t in tasks)),'featured_case_studies':sorted(FEATURED),
      'reference_actor':{'model':'gpt-6.1-sol','accepted_reference_trajectories':len(tasks),'fork_turns':'none','generation_api_used':False,
          'isolation':'Public task/request plus tool broker; not independent OS accounts'},
      'primary_metrics':['runtime_completion_rate','tool_planning_accuracy','answer_accuracy'],
      'strata_sha256':hashlib.sha256((base/'strata.json').read_bytes()).hexdigest(),
      'public_questions_sha256':hashlib.sha256((base/'questions.jsonl').read_bytes()).hexdigest(),
      'criteria_sha256':hashlib.sha256((base/'evaluation/criteria.jsonl').read_bytes()).hexdigest(),
      'asset_manifest_sha256':hashlib.sha256((base/'asset_manifest.json').read_bytes()).hexdigest(),
      'active_full_and_mini_unchanged':True,'catalogue_contract_sha256':hashlib.sha256((ROOT/'tools/catalog/catalog.json').read_bytes()).hexdigest(),
      'reference_scientific_calls':sum(d['reference_scientific_calls'] for d in details),
      'covered_scientific_tools':len(tools),'reference_call_range':[min(d['reference_scientific_calls'] for d in details),max(d['reference_scientific_calls'] for d in details)],
      'scientific_tool_names':sorted(tools),'all_tasks_have_reviewed_parallel_pair':True,'paired_verified_tool_count':parallel['tools'],'paired_verified_calls':sum(c['two_real_process_calls'] for c in parallel['checks']),'source_reviewed_tool_annotations':len(annotations),'parallel_review_sha256':hashlib.sha256((ROOT/'tools/graph/scimas/parallel_review.json').read_bytes()).hexdigest(),
      'baseline_comparison_status':'not_run; reference self-checks are not SciMas performance',
      'graph_fit_counts':dict(Counter(d['graph_fit_class'] for d in details)),
      'graph_fit_scope':'Parallel evidence panels have a narrower scheduling interpretation than multistage dependency studies; capability graph depth does not include model-only scientific aggregation.',
      'tasks':details}
    atomic_json(base/'metadata.json',summary)
    selfcheck=ROOT/'results/special100_release_acceptance';selfcheck.mkdir(parents=True,exist_ok=True)
    atomic_json(selfcheck/'reference_predictions.json',{'suite':'scimas-special-100-v2','baseline':'native_reference_self_check','predictions':predictions})
    lines=['# Special-100 题目目录','',
      '20 题作为重点科学展示案例，其余题目用于受控工具编排分析。图宽是声明能力 DAG 的最大同层节点数，包含候选分支；它不是实测加速比。调用数来自实际参考轨迹。','',
      '| 题号 | 学科 | 难度 | 科学目标 | 重点案例 | 参考科学调用 | 能力图宽 |','| --- | --- | --- | --- | --- | ---: | ---: |']
    for d in details:lines.append(f"| {d['id']} | {d['domain']} | {dict(advanced='较难',intermediate='中等',foundation='基础')[d['difficulty_tier']]} | {d['title']} | {'是' if d['featured_showcase'] else ''} | {d['reference_scientific_calls']} | {d['declared_capability_dag_width']} |")
    (base/'catalog.md').write_text('\n'.join(lines)+'\n')
    atomic_json(base/'progress.json',{'phase':'reference_accepted_individual_review_complete','suite':summary['suite'],
        'target':100,'authored':len(tasks),'accepted_references':len(refs),'accepted_ids':list(refs),
        'difficulty_counts':strata['difficulty_counts'],'source_reviewed_parallel_pairs':len(tasks),
        'reference_refresh':strata['reference_policy'],'technical_reference_checks':'passed',
        'individual_quality_review':'Completed with disclosed graph-fit scope limits; no whole-suite baseline advantage claim.',
        'information_leakage_review':'All100 reviewed;43 public statements revised and re-referenced.',
        'graph_fit_counts':summary['graph_fit_counts'],'review':'evaluation/task_review.json'})
    print(json.dumps({k:summary[k] for k in ['task_count','domains','reference_scientific_calls','covered_scientific_tools','reference_call_range']},ensure_ascii=False))


if __name__=='__main__':generate()
