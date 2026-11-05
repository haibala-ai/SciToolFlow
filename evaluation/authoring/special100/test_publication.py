"""Public information boundaries and equivalent evidence after wording review."""
from pathlib import Path
from copy import deepcopy
import importlib.util,json,sys
import pytest
BASE=Path(__file__).resolve().parent;ROOT=BASE.parents[2]
sys.path.insert(0,str(BASE/'authoring'))
from publication import rewrite,adjust_criteria
from audit import hidden_paths
from evaluation.workflow import score_workflow,validate_workflow
from evaluation.integrity.traces import read_trajectory,execution_calls


def rows(path):return {r['id']:r for r in map(json.loads,path.read_text().splitlines())}


def test_revised_public_statements_do_not_expose_interfaces_or_boolean_gold():
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())['tools']
    for original in rows(BASE/'questions.jsonl').values():
        task=rewrite(original)
        assert 'causal_effect_identified=false' not in task['question']
        assert not [name for name in registry if len(name)>8 and name!='Enumerate' and name in task['question']]
        assert not list(hidden_paths(task['inputs']))
        assert not list(hidden_paths(task['answer_schema']))
        assert task['inputs']==original['inputs']
        assert task['answer_schema']==original['answer_schema']


def test_public_json_assets_contain_no_gold_or_execution_plan():
    for p in (BASE/'assets').glob('*.json'):
        assert not list(hidden_paths(json.loads(p.read_text()))),p.name


def test_scimas_knowledge_contains_no_special_task_records():
    # General method hints are permitted; task IDs, dedicated gold and reference
    # chains would create an extra information channel for one baseline.
    for name in ['annotations.json','graph.json']:
        path=ROOT/'tools/graph/scimas'/name
        if path.exists():assert 'SMAS-' not in path.read_text()


def test_markov_stationary_allows_paired_row_permutations_but_not_wrong_rhs():
    tid='SMAS-0098';task=rows(BASE/'questions.jsonl')[tid]
    criterion=deepcopy(rows(BASE/'evaluation/criteria.jsonl')[tid]);adjust_criteria(task,criterion['evaluation'])
    validate_workflow(criterion['evaluation'])
    ref=rows(BASE/'evaluation/references.jsonl')[tid];trace=read_trajectory(ROOT/ref['reference_trace'])
    pred={'id':tid,'completed':True,'status':'completed','final_answer':trace['final_answer'],'calls':execution_calls(trace)}
    reg=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    stationary=next(c for c in pred['calls'] if c['tool']=='SolveLinearSystem')
    a,b=stationary['arguments']['matrix_a'],stationary['arguments']['vector_b']
    permutation=[2,0,1]
    stationary['arguments']['matrix_a']=[a[i] for i in permutation]
    stationary['arguments']['vector_b']=[b[i] for i in permutation]
    good=score_workflow(criterion,pred,aliases=reg['aliases'],tool_contracts=reg['tools'])
    assert next(n for n in good['nodes'] if n['id']=='stationary')['matched']
    stationary['arguments']['vector_b']=b
    bad=score_workflow(criterion,pred,aliases=reg['aliases'],tool_contracts=reg['tools'])
    assert not next(n for n in bad['nodes'] if n['id']=='stationary')['matched']


def test_coordinate_inventory_reuses_reader_provenance_without_extra_counter():
    tid='SMAS-0054';q=rows(BASE/'questions.jsonl')[tid];c=deepcopy(rows(BASE/'evaluation/criteria.jsonl')[tid])
    adjust_criteria(q,c['evaluation']);validate_workflow(c['evaluation'])
    assert not any(n['id'].startswith('count_') for n in c['evaluation']['nodes'])
    out=next(o for o in c['evaluation']['outcomes'] if o['id']=='atom_counts')
    assert '/provenance/atom_count' in json.dumps(out)


def test_selfies_inspection_is_decoder_evidence_without_duplicate_call():
    tid='SMAS-0059';q=rows(BASE/'questions.jsonl')[tid];c=deepcopy(rows(BASE/'evaluation/criteria.jsonl')[tid])
    adjust_criteria(q,c['evaluation']);validate_workflow(c['evaluation'])
    assert not any(n['id'].startswith('decode_') for n in c['evaluation']['nodes'])
    assert '/decoded_smiles' in json.dumps(c['evaluation']['outcomes'])

@pytest.mark.parametrize('tid,removed',[('SMAS-0071',{'logp'})])
def test_observed_scalar_bookkeeping_does_not_require_calculator_calls(tid,removed):
    task=rows(BASE/'questions.jsonl')[tid];criterion=deepcopy(rows(BASE/'evaluation/criteria.jsonl')[tid])
    adjust_criteria(task,criterion['evaluation']);validate_workflow(criterion['evaluation'])
    assert not removed & {n['id'] for n in criterion['evaluation']['nodes']}
    ref=rows(BASE/'evaluation/references.jsonl')[tid];trace=read_trajectory(ROOT/ref['reference_trace'])
    pred={'id':tid,'completed':True,'status':'completed','final_answer':trace['final_answer'],'calls':execution_calls(trace)}
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    scored=score_workflow(criterion,pred,aliases=registry['aliases'],tool_contracts=registry['tools'])
    assert scored['joint_pass']
    pred['calls']=[]
    assert not score_workflow(criterion,pred,aliases=registry['aliases'],tool_contracts=registry['tools'])['joint_pass']


def test_temporal_scale_equivalence_keeps_training_population_boundary():
    tid='SMAS-0088';task=rows(BASE/'questions.jsonl')[tid]
    criterion=deepcopy(rows(BASE/'evaluation/criteria.jsonl')[tid]);adjust_criteria(task,criterion['evaluation'])
    validate_workflow(criterion['evaluation'])
    ref=rows(BASE/'evaluation/references.jsonl')[tid];trace=read_trajectory(ROOT/ref['reference_trace'])
    pred={'id':tid,'completed':True,'status':'completed','final_answer':trace['final_answer'],'calls':execution_calls(trace)}
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    assert score_workflow(criterion,pred,aliases=registry['aliases'],tool_contracts=registry['tools'])['joint_pass']
    for call in pred['calls']:
        if call['tool']=='StandardizeNumericFeatures':call['arguments']['training_features']=task['inputs']['features']
    bad=score_workflow(criterion,pred,aliases=registry['aliases'],tool_contracts=registry['tools'])
    assert not bad['planning_pass']


@pytest.mark.parametrize('tid',['SMAS-0089','SMAS-0090','SMAS-0099'])
def test_equivalent_linear_algebra_routes_keep_scientific_answers_and_reject_wrong_ones(tid):
    task=rows(BASE/'questions.jsonl')[tid];criterion=deepcopy(rows(BASE/'evaluation/criteria.jsonl')[tid])
    adjust_criteria(task,criterion['evaluation']);validate_workflow(criterion['evaluation'])
    ref=rows(BASE/'evaluation/references.jsonl')[tid];trace=read_trajectory(ROOT/ref['reference_trace'])
    p={'id':tid,'completed':True,'status':'completed','final_answer':trace['final_answer'],'calls':execution_calls(trace)}
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    grade=lambda x:score_workflow(criterion,x,aliases=registry['aliases'],tool_contracts=registry['tools'])
    assert grade(p)['joint_pass']
    if tid=='SMAS-0089':
        p['final_answer']['solution_r2'][0]+=1
    elif tid=='SMAS-0090':p['final_answer']['estimable_b']=True
    else:p['final_answer']['vertex_bounds_c']=[8,12]
    assert not grade(p)['answer_pass']


def test_transcription_audit_requires_each_independent_source_observation():
    tid='SMAS-0073';task=rows(BASE/'questions.jsonl')[tid]
    assert len(task['inputs']['sources'])==3
    criterion=rows(BASE/'evaluation/criteria.jsonl')[tid]
    ref=rows(BASE/'evaluation/references.jsonl')[tid];trace=read_trajectory(ROOT/ref['reference_trace'])
    p={'id':tid,'completed':True,'status':'completed','final_answer':trace['final_answer'],'calls':execution_calls(trace)}
    registry=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    grade=lambda x:score_workflow(criterion,x,aliases=registry['aliases'],tool_contracts=registry['tools'])
    assert grade(p)['joint_pass']
    scientific=[c for c in p['calls'] if c['tool']!='DescribeTools']
    assert len(scientific)==3
    p['calls']=scientific[:1]
    assert not grade(p)['planning_pass']


def test_file_ingestion_cannot_read_hidden_scoring_or_authoring_files(monkeypatch):
    from tools.runtime.config import UPLOAD_CONTEXT
    from tools.implementations.general.research_data import _public_source_path
    monkeypatch.delenv('SCITOOLFLOW_ARTIFACTS_DIR',raising=False)
    public=next((BASE/'assets').glob('SMAS-0001*')).resolve()
    token=UPLOAD_CONTEXT.set({'all_paths':[str(public)],'paths':[str(public)],'base_path':str(public.parent)})
    try:
        assert _public_source_path(str(public))==public
        for path in [BASE/'evaluation/criteria.jsonl',BASE/'evaluation/references.jsonl',
                     BASE/'authoring/review_notes.json',BASE/'design.json']:
            with pytest.raises(PermissionError):_public_source_path(str(path.resolve()))
    finally:UPLOAD_CONTEXT.reset(token)
