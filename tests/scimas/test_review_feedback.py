"""Specific review evidence, concrete repairs and observed recovery."""
from copy import deepcopy

import pytest

from baselines.scimas.feedback import plan_change_summary, repair_feedback, review_basis
from baselines.scimas.runtime import run_scimas
from tools import execute
from .test_runtime import Client, Knowledge
from .test_knowledge_planner import valid_plan, public_example


def test_cosmetic_revision_is_not_an_operational_change():
    original = valid_plan()
    renamed = deepcopy(original)
    renamed['nodes'][0]['purpose'] = 'More carefully calculate the inverse'
    changes = plan_change_summary(original, renamed)
    assert changes['changed_fields'] == {'inverse': ['purpose']}
    assert not changes['operational_change']
    renamed['nodes'][0]['arguments']['values']['path'] = ['inputs', 'correct_matrix']
    assert plan_change_summary(original, renamed)['operational_change']


def test_repair_feedback_cannot_borrow_an_unrelated_or_old_review():
    request = {'nodes': ['inverse'], 'reason': 'Singular source matrix'}
    record = {'stage': 'result', 'node': 'inverse', 'graph_sha256': 'current',
              'decision': {'repair': request},
              'basis': {'observation_id': 'o1', 'structural_validation': 'Singular'}}
    assert repair_feedback([record], request, 'current')['basis']['observation_id'] == 'o1'
    assert repair_feedback([record], request, 'old') is None
    assert repair_feedback([record], dict(request, nodes=['other']), 'current') is None


def test_basis_keeps_check_results_without_duplicating_raw_arrays():
    basis = review_basis('result', {
        'node': 'n', 'observation_id': 'o1', 'arguments': {'large': [0] * 10000},
        'structural_validation': 'Required field missing',
        'numerical_certificate': {'passed': False, 'residual': 1},
        'argument_provenance': {'source_observations': {'p': 'o0'}, 'resolution_verified': True},
    })
    assert 'arguments' not in basis
    assert basis['source_observations'] == {'p': 'o0'}
    assert not basis['numerical_certificate']['passed']


@pytest.mark.parametrize('initial_false_accept', [False, True])
def test_real_failed_binding_is_corrected_and_execution_verifies_recovery(tmp_path, initial_false_accept):
    knowledge = Knowledge()
    observed = {'failed_review': 0, 'repair_basis': None, 'revision': None}
    def hook(payload, action):
        ctx = payload.get('context', {})
        if payload.get('stage') == 'graph':
            plan = valid_plan()
            plan['nodes'][0]['arguments']['values']['path'] = ['inputs', 'singular_control']
            return {'plan': plan}
        if ctx.get('stage') == 'result' and ctx['structural_validation'] != 'passed':
            observed['failed_review'] += 1
            if initial_false_accept and observed['failed_review'] == 1:
                return action  # Deliberately contradict deterministic checks once.
            if initial_false_accept:
                assert ctx['semantic_feedback'][0]['error'] == ctx['structural_validation']
            return {'repair': {'nodes': ['inverse'],
                               'reason': 'The inverse node used singular_control, not the requested matrix.',
                               'suggested_change': 'Bind values to inputs.matrix.',
                               'verification': 'Recompute the inverse and check its matrix product.'}}
        if 'request' in ctx:
            observed['repair_basis'] = ctx['review_feedback']['basis']
            assert observed['repair_basis']['node'] == 'inverse'
            assert observed['repair_basis']['observation_id'] in ctx['observations']
            assert observed['repair_basis']['structural_validation'] != 'passed'
            assert ctx['request']['suggested_change'] == 'Bind values to inputs.matrix.'
            return {'plan': valid_plan()}
        if ctx.get('stage') == 'graph' and 'revision' in ctx:
            observed['revision'] = ctx['revision']
            assert ctx['revision']['changes']['changed_fields'] == {'inverse': ['arguments']}
        return action
    trace = run_scimas(
        public_example()['question'], catalog=knowledge.catalog, knowledge=knowledge,
        client=Client(hook), invoke=execute, trace_dir=tmp_path, case_id='RECOVERY', dataset='custom',
        inputs={**public_example()['inputs'], 'singular_control': [[0, 0], [0, 0]]},
        answer_schema={'type': 'object', 'properties': {'inverse': {'type': 'array'},
                                                    'product': {'type': 'array'}},
                       'required': ['inverse', 'product'], 'additionalProperties': False},
    )
    assert trace['status'] == 'completed', trace['failure_reason']
    assert observed['repair_basis'] and observed['revision']
    assert len(trace['calls']) == 3 and len(trace['repairs']) == 1
    assert trace['calls'][0]['status'] != 'success'
    repaired = trace['repairs'][0]
    assert repaired['graph_review'] == 'approved'
    assert repaired['execution_evidence']['accepted_nodes'] == ['check', 'inverse']
    assert repaired['execution_evidence']['pending_nodes'] == []
    assert repaired['execution_evidence']['status'] == 'affected_evidence_available'
    assert not repaired['execution_evidence']['task_success_proven']
    assert trace['final_answer']['product'] == [[1, 0], [0, 1]]
