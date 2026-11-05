"""Scientific-equivalence and rejection boundaries; never invokes an LLM."""
from copy import deepcopy
import importlib.util,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3];BASE=Path(__file__).resolve().parent


@pytest.fixture(scope='module')
def score():
    spec=importlib.util.spec_from_file_location('special_metrics',BASE/'evaluate.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    tasks=module.rows(BASE/'questions.jsonl');criteria=module.rows(BASE/'evaluation/criteria.jsonl');refs=module.rows(BASE/'evaluation/references.jsonl')
    catalog=json.loads((ROOT/'tools/catalog/catalog.json').read_text())
    from evaluation.integrity.traces import read_trajectory
    def case(tid):
        reference=module.prediction_from_trace(read_trajectory(ROOT/refs[tid]['reference_trace']))
        def grade(prediction):return module.three_metrics(tasks[tid],criteria[tid],prediction,reference,catalog)
        assert all(grade(reference)[k] for k in ['runtime_completed','tool_plan_correct','answer_correct'])
        return deepcopy(reference),grade
    return case


def test_identity_adapters_are_not_forced_when_domain_output_establishes_graph(score):
    for tid in ['SMAS-0006','SMAS-0008','SMAS-0009']:
        p,grade=score(tid)
        p['calls']=[c for c in p['calls'] if c['tool']!='CanonicalMolecularIdentity']
        assert grade(p)['tool_plan_correct']


def test_exact_graph_reuse_preserves_policy_difference(score):
    p,grade=score('SMAS-0005')
    assert sum(c['tool']=='SMILESToWeight' for c in p['calls'])==3
    assert grade(p)['tool_plan_correct']
    wrong=deepcopy(p)
    call=next(c for c in wrong['calls'] if c['tool']=='CanonicalMolecularIdentity' and c['arguments'].get('tautomer_policy')=='canonical')
    call['arguments']['tautomer_policy']='preserve'
    assert not grade(wrong)['tool_plan_correct']


def test_gate_failure_requires_null_and_same_scientific_target(score):
    p,grade=score('SMAS-0004')
    assert p['final_answer']['eligible_a'] is False and p['final_answer']['eligible_b'] is True and p['final_answer']['eligible_c'] is False
    for field in ['eligible_c','mass_a','tpsa_c']:
        wrong=deepcopy(p);wrong['final_answer'][field]=True if field=='eligible_c' else 0
        assert not grade(wrong)['answer_correct']


def test_fragment_charge_cannot_be_replaced_by_whole_salt_charge(score):
    p,grade=score('SMAS-0007');wrong=deepcopy(p)
    wrong['final_answer']['charge_b']=0;wrong['final_answer']['neutral_b']=True
    assert not grade(wrong)['answer_correct']
    wrong=deepcopy(p)
    c=next(c for c in wrong['calls'] if c['tool']=='CanonicalMolecularIdentity' and '.' in c['arguments']['smiles'])
    c['arguments']['fragment_policy']='keep_all'
    assert not grade(wrong)['tool_plan_correct']


def test_maccs_none_and_empty_options_are_the_same_default(score):
    p,grade=score('SMAS-0008')
    c=next(c for c in p['calls'] if c['tool']=='CompareMolecularFingerprints' and c['arguments']['algorithm']=='maccs')
    c['arguments']['options']={}
    assert grade(p)['tool_plan_correct']
    c['arguments']['algorithm']='morgan'
    assert not grade(p)['tool_plan_correct']


def test_conserved_mass_does_not_force_identical_roundtrip_graph(score):
    p,grade=score('SMAS-0011')
    assert p['final_answer']['roundtrip_same_a'] is False
    assert abs(p['final_answer']['delta_mass_a'])<1e-9
    wrong=deepcopy(p);wrong['final_answer']['roundtrip_same_a']=True
    assert not grade(wrong)['answer_correct']
    wrong=deepcopy(p);wrong['final_answer']['canonical_a']=wrong['final_answer']['recovered_a']
    assert not grade(wrong)['answer_correct']


def test_descriptive_correlation_is_symmetric_but_permutation_protocol_is_strict(score):
    p,grade=score('SMAS-0033');swapped=deepcopy(p)
    for c in swapped['calls']:
        if c['tool']=='MantelCorrelation':
            a=c['arguments'];a['distance_a'],a['distance_b']=a['distance_b'],a['distance_a']
    assert grade(swapped)['tool_plan_correct']
    next(c for c in swapped['calls'] if c['tool']=='MantelCorrelation')['arguments']['permutations']=199
    assert not grade(swapped)['tool_plan_correct']
    wrong=deepcopy(p);wrong['final_answer']['causal_effect_identified']=True
    assert not grade(wrong)['answer_correct']


def test_common_baseline_and_rna_denominators_are_scientific_constraints(score):
    p,grade=score('SMAS-0006');wrong=deepcopy(p)
    next(c for c in wrong['calls'] if c['tool']=='CalculateTPSA')['arguments']['smiles']='CCO'
    assert not grade(wrong)['tool_plan_correct']
    p,grade=score('SMAS-0037');wrong=deepcopy(p)
    wrong['final_answer']['U2_gc_percent_bounds_all_nongap']=[100.,100.]
    assert not grade(wrong)['answer_correct']


def test_versioned_suite_rejects_old_release_envelopes(tmp_path):
    spec=importlib.util.spec_from_file_location('special_version_guard',BASE/'evaluate.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    file=tmp_path/'predictions.json';file.write_text(json.dumps({'suite':'scimas-special-50','predictions':[]}))
    with pytest.raises(ValueError,match='Foreign study suite'):module.evaluate(file,selected=['SMAS-0004'])


def test_nonunique_blend_accepts_another_feasible_optimum_but_rejects_false_witnesses(score):
    p,grade=score('SMAS-0060');alternate=deepcopy(p);a=alternate['final_answer']
    x_c=20.;x_b=(12.-a['CNO_c'][1]*x_c)/a['CNO_b'][1];x=[100.-x_b-x_c,x_b,x_c]
    a['allocation_g']=x
    for index,key in enumerate(['carbon_g','nitrogen_g','oxygen_g']):a[key]=sum(a['CNO_'+label][index]*v for label,v in zip('abc',x))
    a['total_g']=sum(x)
    assert grade(alternate)['answer_correct']
    for allocation in [[-1.,31.,70.],[65.,10.,25.]]:
        wrong=deepcopy(alternate);b=wrong['final_answer'];b['allocation_g']=allocation
        for index,key in enumerate(['carbon_g','nitrogen_g','oxygen_g']):b[key]=sum(b['CNO_'+label][index]*v for label,v in zip('abc',allocation))
        b['total_g']=sum(allocation)
        assert not grade(wrong)['answer_correct']


def test_lp_row_permutations_preserve_rhs_pairing(score):
    p,grade=score('SMAS-0060');call=next(c for c in p['calls'] if c['tool']=='SolveLinearProgram');args=call['arguments']
    args['inequality_matrix']=args['inequality_matrix'][::-1];args['inequality_rhs']=args['inequality_rhs'][::-1]
    assert grade(p)['tool_plan_correct']
    args['inequality_rhs']=args['inequality_rhs'][::-1]
    assert not grade(p)['tool_plan_correct']


def test_reflection_and_rounded_mode_metrics_do_not_fabricate_equivalence(score):
    for tid,field in [('SMAS-0054','mirror_proper_equivalent'),('SMAS-0076','euclidean_bray')]:
        p,grade=score(tid);assert p['final_answer'][field] is False
        wrong=deepcopy(p);wrong['final_answer'][field]=True
        assert not grade(wrong)['answer_correct']


def test_orientation_controls_are_informative_and_ambiguity_is_not_repaired(score):
    p,grade=score('SMAS-0081');answer=p['final_answer']
    assert answer['forward_score_a']>answer['reverse_score_a']
    assert answer['reverse_score_b']>answer['forward_score_b']
    assert answer['eligible_c'] is False and answer['best_score_c'] is None
    wrong=deepcopy(p);wrong['final_answer']['best_score_c']=0.
    assert not grade(wrong)['answer_correct']


def test_clustering_rejects_noise_population_and_undefined_quality_substitutions(score):
    p,grade=score('SMAS-0097');answer=p['final_answer']
    assert answer['raw_best']==['a'] and answer['coverage_best']==['b']
    assert answer['silhouette_c'] is None
    wrong=deepcopy(p);wrong['final_answer']['coverage_best']=['a']
    assert not grade(wrong)['answer_correct']
    wrong=deepcopy(p);wrong['final_answer']['silhouette_c']=0.
    assert not grade(wrong)['answer_correct']
    # Equivalent nonnoise label names keep their partitions/noise positions.
    renamed=deepcopy(p)
    for label in 'abc':renamed['final_answer']['labels_'+label]=[10+v if v!=-1 else -1 for v in answer['labels_'+label]]
    assert grade(renamed)['answer_correct']


def test_nonidentifiable_contrast_requires_null_and_joint_uncertainty_is_not_cartesian(score):
    p,grade=score('SMAS-0090');assert p['final_answer']['estimate_b'] is None
    wrong=deepcopy(p);wrong['final_answer']['estimate_b']=1.
    assert not grade(wrong)['answer_correct']
    p,grade=score('SMAS-0099');a=p['final_answer'];assert a['joint_sum_width']<a['sum_of_marginal_widths']
    wrong=deepcopy(p);wrong['final_answer']['joint_sum_width']=a['sum_of_marginal_widths']
    assert not grade(wrong)['answer_correct']
