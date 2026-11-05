"""Publish the root's per-question scientific, mechanism and leakage review.

Static scans are supporting evidence, not a claim that a keyword scan proves
scientific quality. Individual scientific judgments are recorded in review_notes.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,sys
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parents[2]
sys.path.insert(0,str(ROOT))
from evaluation.integrity.traces import canonical_sha256

HIDDEN_KEYS={'ground_truth','expected_answer','reference_answer','tool_path','reference_trace','_plan','evaluation','criteria'}
EXEMPTIONS={
  'SMAS-0028':'The redundant change vector is derived input, not the bootstrap answer. Sampling-unit and endpoint conventions remain explicit.',
  'SMAS-0035':'The supplied R3 correction is an authorized alternate scientific source; the question assesses QC and composition, not guessing that correction.',
  'SMAS-0054':'coordinate_sets and SDF preserve equivalent raw geometry. Neither contains computed RMSD, distances, shape scores or comparison truth values.',
  'SMAS-0072':'Initial values, parameter bounds and the response family specify a reproducible calibration experiment; fitted parameters and inverse coefficients are not supplied.',
  'SMAS-0073':'The three inputs are explicitly controlled transcription-audit fixtures. No label identifies which numerical accounting checks pass; they are not represented as three new physical calculations.',
  'SMAS-0087':'The four sigma conventions define distinct estimands. Their resulting covariance or scaling conclusions are not given.'}
FAMILIES=[
 ('serialization_fidelity',['SMAS-0011','SMAS-0059'],'Single representation fidelity versus comparison of two standards; related purpose, distinct scientific evidence and join.'),
 ('network_diffusion',['SMAS-0008','SMAS-0040','SMAS-0052','SMAS-0100'],'Compound-space, physical sensor network, atom/contact geometry and nonuniform quadrature ask different scientific invariants; shared numerical kernel is disclosed.'),
 ('sampling_unit',['SMAS-0028','SMAS-0075'],'Cluster endpoint inference versus habitat-target-weighted inference; not merely different seeds.'),
 ('coverage',['SMAS-0048','SMAS-0077'],'Finite flagged inventory versus biodiversity effort and species richness; distinct objects and assumptions.'),
 ('validation_leakage',['SMAS-0039','SMAS-0088'],'Held-out groups versus cutoff-specific temporal embargo; different admissible populations and information boundaries.'),
 ('decision_cost',['SMAS-0043','SMAS-0091'],'Shared threshold-cost analysis versus explicit positive-class identity and cohort calibration.'),
 ('inverse_witness',['SMAS-0041','SMAS-0092'],'SPD eligibility gates versus shared multi-RHS inverse/direct-solution consistency.')]

def hidden_paths(value,path=''):
    if isinstance(value,dict):
        for key,item in value.items():
            if key.lower() in HIDDEN_KEYS:yield path+'/'+key
            yield from hidden_paths(item,path+'/'+key)
    elif isinstance(value,list):
        for i,item in enumerate(value):yield from hidden_paths(item,path+'/'+str(i))

def levels(spec):
    remaining={n['id']:set(n.get('depends_on',[])) for n in spec['nodes']};done=set();result=[]
    while remaining:
        ready=sorted(n for n,d in remaining.items() if d<=done)
        if not ready:raise ValueError('Cyclic capability graph')
        result.append(ready);done.update(ready)
        for n in ready:del remaining[n]
    return result

def generate(base=BASE):
    base=Path(base)
    q={r['id']:r for r in map(json.loads,(base/'questions.jsonl').read_text().splitlines())}
    criteria={r['id']:r for r in map(json.loads,(base/'evaluation/criteria.jsonl').read_text().splitlines())}
    refs={r['id']:r for r in map(json.loads,(base/'evaluation/references.jsonl').read_text().splitlines())}
    design={r['id']:r for r in json.loads((base/'design.json').read_text())['studies']}
    profiles={r['id']:r for r in json.loads((base/'strata.json').read_text())['tasks']}
    notes=json.loads((BASE/'authoring/review_notes.json').read_text())
    from publication import REVISED_IDS,PUBLICATION_NOTES
    tools=json.loads((ROOT/'tools/catalog/catalog.json').read_text())['tools']
    rows=[]
    for tid,t in q.items():
        c=criteria[tid];d=design[tid];p=profiles[tid];ls=levels(c['evaluation'])
        hidden=list(hidden_paths(t['inputs']))+list(hidden_paths(t['answer_schema']))
        for name in (base/'assets').glob(tid+'*'):
            if name.suffix=='.json':hidden.extend(name.name+v for v in hidden_paths(json.loads(name.read_text())))
        # Enumerate is also an ordinary verb. Scientific standards and formulae
        # are permitted; named registered execution interfaces are not needed.
        named=[n for n in tools if len(n)>8 and n!='Enumerate' and n in t['question']]
        answer_literal='causal_effect_identified=false' in t['question']
        assert not hidden,(tid,hidden)
        assert not named,(tid,named)
        assert not answer_literal,tid
        single=len(ls)==1
        fit='parallel_evidence_panel' if single else 'multistage_dependency_graph'
        strict_gap=single and p['difficulty_tier']!='foundation'
        interventions=[]
        if tid=='SMAS-0033':interventions.append('Removed an explicit scored Boolean answer; now asks for identification judgment from the observational design.')
        if tid in {'SMAS-0055','SMAS-0059','SMAS-0097'}:interventions.append('Replaced named registered tool interfaces with scientific representation or measurement definitions.')
        if tid in REVISED_IDS:interventions.append(PUBLICATION_NOTES[int(tid[-4:])])
        if not interventions:interventions.append('No specific answer or execution-route disclosure found in the individual wording review; necessary scientific definitions retained.')
        current=refs[tid]['native_provenance']['task_sha256']==canonical_sha256(t)
        rows.append({'id':tid,'domain':t['domain'],'difficulty_tier':p['difficulty_tier'],
          'title':t['question'].split('. ')[0],'public_task_sha256':canonical_sha256(t),
          'evaluation_sha256':canonical_sha256(c['evaluation']),
          'scientific_review':notes[tid],
          'scientific_purpose':d.get('scientific_goal',d.get('scientific_join','')),
          'shared_prerequisite':p['shared_prerequisite'],'parallel_subtasks':p['parallel_scientific_subtasks'],
          'scientific_join':p['scientific_join'],'graph_fit':{'class':fit,'declared_levels':len(ls),
             'declared_width':max(map(len,ls)),'multistage_capability_evidence':not single,
             'limitation':'A genuine parallel panel with scientific aggregation, but no inter-tool dependency chain. This supports a narrower parallel scheduling claim, not a strong multistage-planning advantage.' if strict_gap else
                          'Suitable bounded parallel control; not evidence of a multistage graph advantage.' if single else
                          'Explicit scientific dependencies and independent branches; actual speedup remains unmeasured.'},
          'leakage_review':{'scope':['question and title','inputs','answer schema','public JSON attachments','runtime public loader boundary'],
              'findings_and_repairs':interventions,'retained_input_or_protocol':EXEMPTIONS.get(tid,
                'Scientific units, fixed method conventions, tolerances and requested result fields define the experiment; raw observations are not hidden gold.'),
              'hidden_answer_or_plan_keys':hidden,'registered_interfaces_in_question':named,
              'explicit_answer_literal_found':answer_literal,'status':'reviewed'},
          'related_family_review':[{'family':name,'related_ids':ids,'distinction':why} for name,ids,why in FAMILIES if tid in ids],
          'reference_current_identity':current,'reference_trace_sha256':refs[tid]['native_provenance']['trace_sha256'],
          'reference_status':'current_identity' if current else 'refresh_required',
          'quality_disposition':'parallel_fit_only; strengthen_before_claiming_complex_multistage_advantage' if strict_gap else 'scope_appropriate',
          'technical_reference_acceptance_is_not_quality_or_baseline_performance':True})
    counts=Counter(r['graph_fit']['class'] for r in rows)
    gaps=[r['id'] for r in rows if r['difficulty_tier']!='foundation' and not r['graph_fit']['multistage_capability_evidence']]
    summary={'schema_version':'scimas.special.task_review.v1','tasks':len(rows),
      'review_basis':'Root individual question review plus previously recorded unique scientific notes; scans and graph statistics are supporting checks.',
      'questions_revised':len(REVISED_IDS),'current_identity_references':sum(r['reference_current_identity'] for r in rows),
      'graph_fit_counts':dict(counts),'complex_graph_strengthening_candidates':gaps,
      'whole_suite_strong_advantage_demonstrated':False,
      'leakage_scope':'Checks cover public question/inputs/schema/assets and loader. Authoring/evaluation are private reference materials and must not be included in solver context.',
      'performance_claim':'No measured SciMas versus serial-baseline advantage claimed.','tasks_review':rows}
    (base/'evaluation/task_review.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    lines=['# Special-100 逐题复核','',
      '审查分开记录科学正确性、图结构适配、公开信息边界和参考身份。参考自检通过不能替代题目质量判断，也不能证明 SciMas 优于其他方法。','',
      f'共审查 {len(rows)} 题：{counts["multistage_dependency_graph"]} 题有多层工具依赖，{counts["parallel_evidence_panel"]} 题主要是单层并行证据面板。后者有实际并行工作，但不能统一称为复杂多阶段编排。',
      '',f'其中 {len(gaps)} 道中等／较难题目前主要考察并行证据汇合；若要将其作为强多阶段编排题，应增强科学依赖。没有仅凭工具层数设立用户未规定的硬门槛，也没有宣称这些题已证明强编排优势。题号：'+', '.join(gaps)+'。','',
      '泄露检查涵盖题目标题、正文、输入、答案格式和公开 JSON 附件。移除了直接给出的判断、明确工具接口名和不必要的解题顺序。算法定义、计量单位、实验条件、容差和输出字段用于固定科学问题，予以保留。原始计算输出和用于评估预测的观测真值也属于合法题目数据。','',
      'SMAS-0035 的授权纠正来源、SMAS-0054 的原始坐标、SMAS-0028 的前后变化输入均在逐题记录中说明。它们不等于最终判断；不能仅凭字段名把合法观测误删。','',
      '[完整逐题记录](evaluation/task_review.json) 包括每题科学审查意见、共享前提、独立子任务、科学汇合、相关方法族区分、信息检查和当前参考身份。','',
      '| 题号 | 学科 | 难度 | 图结构 | 适配范围 | 当前参考 |','| --- | --- | --- | --- | --- | --- |']
    for r in rows:
        lines.append(f'| {r["id"]} | {r["domain"]} | {r["difficulty_tier"]} | {r["graph_fit"]["declared_levels"]} 层 / 宽 {r["graph_fit"]["declared_width"]} | {"主要并行面板" if r["id"] in gaps else "符合定位"} | {"匹配" if r["reference_current_identity"] else "待重采样"} |')
    (base/'review.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='tasks_review'},ensure_ascii=False))

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--directory',type=Path,default=BASE)
    generate(ap.parse_args().directory)
