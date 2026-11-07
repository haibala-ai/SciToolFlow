"""Explicit v2 intervention: no initial refinement, no Reviewer in wo-all."""
import pytest

from baselines.scimas.roles import Roles
from baselines.scimas.feedback import deterministic_review
from .test_runtime import run, Client, fixture_invoke


@pytest.mark.parametrize('variant', ['wo-local-repair', 'wo-all'])
def test_initial_executor_repair_cannot_reach_repair_role(tmp_path, variant):
    def hook(payload, action):
        if 'ready' in payload.get('context', {}):
            return {'repair': {'nodes': ['inverse'], 'reason': 'Change the submitted initial graph'}}
        return action
    trace = run(tmp_path, Client(hook), scimas_ablation=variant,
                config={'graph_refinements': 50})
    assert trace['status'] == 'failed'
    assert 'GraphRefinementDisabled' in trace['failure_reason']
    assert trace['limits']['graph_refinements'] == 0
    assert not trace['calls'] and not trace['graph_refinements']
    assert not any(s.get('role') == 'repair' for s in trace['steps'])


def test_wo_all_never_invokes_scientific_reviewer_or_repair(tmp_path, monkeypatch):
    original = Roles.ask
    invoked = []
    def guarded(self, role, *args, **kwargs):
        assert role not in {'reviewer', 'repair'}, role
        invoked.append(role)
        return original(self, role, *args, **kwargs)
    monkeypatch.setattr(Roles, 'ask', guarded)
    trace = run(tmp_path, scimas_ablation='wo-all')
    assert trace['status'] == 'completed', trace['failure_reason']
    assert invoked == ['executor', 'executor', 'summary']
    assert trace['metrics']['model_requests'] == 5  # Planner 2, Executor 2, Summary 1.
    assert trace['ablation']['schema_version'] == 'scimas.ablation.v2'
    assert not trace['ablation']['scientific_review']
    assert {r['stage'] for r in trace['reviews']} == {'graph', 'result', 'final'}
    assert all(r['mode'] == 'deterministic_only' and not r['scientific_review'] for r in trace['reviews'])


def test_wo_local_repair_retains_scientific_reviewer(tmp_path):
    trace = run(tmp_path, scimas_ablation='wo-local-repair')
    assert trace['status'] == 'completed', trace['failure_reason']
    assert trace['ablation']['scientific_review']
    assert len([s for s in trace['steps'] if s.get('role') == 'reviewer']) == 4
    assert all(r['mode'] == 'llm_scientific' for r in trace['reviews'])


def test_wo_all_does_not_invent_a_numerical_certificate_for_uncovered_tools(tmp_path):
    def invoke(name, args, **kwargs):
        result = fixture_invoke(name, args, **kwargs)
        if name == 'MatrixInverse':
            result['output']['inverse'] = [[7, 0], [0, 7]]
        return result
    trace = run(tmp_path, invoke=invoke, scimas_ablation='wo-all')
    # MatrixInverse has no built-in equation certificate. Its valid schema is
    # insufficient scientific proof once the LLM Reviewer is explicitly removed.
    assert trace['status'] == 'completed', trace['failure_reason']
    assert trace['final_answer']['inverse'] == [[7, 0], [0, 7]]
    assert all(not r['scientific_review'] for r in trace['reviews'])
    assert not any(s.get('role') in {'reviewer', 'repair'} for s in trace['steps'])


def test_wo_all_still_enforces_existing_numerical_certificates(tmp_path):
    from baselines.scimas.runtime import run_scimas
    from .test_runtime import Knowledge
    knowledge = Knowledge()
    question = 'Compute the eigensystem of the supplied symmetric matrix.'
    def hook(payload, action):
        if payload.get('stage') == 'decompose':
            return {'requirements': [{'id': 'report', 'description': 'Eigensystem',
                                      'evidence': question, 'mode': 'complete'}],
                    'queries': ['symmetric eigensystem']}
        if payload.get('stage') == 'graph':
            return {'plan': {'nodes': [{'id': 'eigen', 'tool': 'SymmetricEigenDecomposition',
                                       'purpose': 'Compute the eigenvalues and eigenvectors', 'object': 'matrix',
                                       'arguments': {'values': {'kind': 'task', 'path': ['inputs', 'matrix']}}}],
                             'deliverables': [{'requirement': 'report', 'nodes': ['eigen'], 'description': 'Eigensystem'}]}}
        return action
    def invoke(*args, **kwargs):
        return {'status': 'success', 'output': {'eigenvalues': [7, 7], 'eigenvectors': [[1, 0], [0, 1]]}}
    trace = run_scimas(question, inputs={'matrix': [[2, 0], [0, 4]]}, catalog=knowledge.catalog,
                        knowledge=knowledge, client=Client(hook), invoke=invoke, trace_dir=tmp_path,
                        case_id='CERTIFICATE', dataset='custom', scimas_ablation='wo-all')
    assert trace['status'] == 'failed'
    assert 'numerical verification failed' in trace['failure_reason']
    assert len(trace['calls']) == 1 and not trace['results']


def test_deterministic_review_does_not_fabricate_scientific_approval():
    assert 'reject' in deterministic_review('graph', {'graph_validation': {'valid': False, 'errors': ['cycle']}}, [])
    assert 'reject' in deterministic_review('result', {'structural_validation': 'bad output'}, [])
    assert 'reject' in deterministic_review('result', {'structural_validation': 'passed', 'numerical_certificate': {'passed': False}}, [])
    accepted = deterministic_review('result', {'structural_validation': 'passed'}, [])
    assert accepted['accept']['semantics'] == []
    assert 'not scientific approval' in accepted['accept']['reason']
