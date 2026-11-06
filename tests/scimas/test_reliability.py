"""Regressions for failures found in the Mini-200 DeepSeek run; no remote calls."""
import json

import pytest
from baselines.scimas.validation import path_schema
from baselines.scimas.verification import numerical_certificate
from baselines.scimas.task_graph import TaskGraph
from tools import ToolCatalog
from .test_runtime import run, Client, fixture_invoke
from .test_knowledge_planner import valid_plan


@pytest.mark.parametrize('limit', [0, None])
def test_disabled_failure_limit_allows_existing_transient_retry(tmp_path, limit):
    attempts = []
    def invoke(name, args, **kw):
        if name == 'MatrixInverse':
            attempts.append(name)
            if len(attempts) == 1:
                return {'status': 'error', 'output': None, 'error_type': 'Timeout'}
        return fixture_invoke(name, args, **kw)
    result = run(tmp_path, invoke=invoke, max_failures_per_action=limit)
    assert result['status'] == 'completed', result['failure_reason']
    assert len(attempts) == 2


@pytest.mark.parametrize('schema', [
    {'type': 'array'}, {'type': 'array', 'items': True},
    {'type': ['array', 'object', 'null']},
])
def test_dynamic_array_paths_remain_subject_to_actual_resolution(schema):
    assert path_schema(schema, [0]) == {}
    assert path_schema(schema, ['*'], allow_wildcards=True) == {}


@pytest.mark.parametrize('schema,index', [
    ({'type': 'array', 'items': False}, 0),
    ({'type': 'number'}, 0), ({'type': 'object'}, 0),
    ({'type': 'array'}, -1),
])
def test_unconstrained_array_fix_does_not_allow_invalid_paths(schema, index):
    with pytest.raises(ValueError):
        path_schema(schema, [index])


def test_native_dict_is_not_json_decoded_again():
    catalog = ToolCatalog()
    graph = TaskGraph.create({'id': 'test', 'question': 'Read a result'}, [], {
        'nodes': [{'id': 'freq', 'tool': 'GetMolecularFrequencies', 'arguments': {}}],
        'deliverables': [],
    }, catalog, 'custom')
    output = {'backend': 'supplied_qchem_output', 'property': 'frequencies',
              'source_file': 'fixture.qout', 'source_sha256': '0' * 64,
              'value': [1.0, 2.0, 3.0], 'units': 'cm^-1',
              'scope': 'Synthetic regression fixture, not a scientific reference',
              'mp_molecule_identity_verified': False}
    accepted = graph.accept_result('freq', {'status': 'success', 'output': output}, catalog)
    assert accepted['output'] == output


def test_reviewer_sees_binding_proof_and_pending_acceptance(tmp_path):
    seen = []
    def hook(payload, action):
        ctx = payload.get('context', {})
        if ctx.get('stage') == 'result':
            nid, oid = ctx['node'], ctx['observation_id']
            assert nid in ctx['current_graph_nodes']
            assert nid not in ctx['accepted_result_nodes']
            assert ctx['observations'][oid]['review_state'] == 'pending_review'
            assert not ctx['observations'][oid]['stale']
            assert ctx['argument_provenance']['resolution_verified']
            if nid == 'check':
                proof = ctx['argument_provenance']
                assert proof['declared_arguments']['right']['kind'] == 'node'
                assert proof['source_observations']['inverse']
                assert proof['resolved_arguments_field'] == 'arguments'
                assert isinstance(ctx['arguments']['right'], list)
            seen.append(nid)
        return action
    result = run(tmp_path, Client(hook))
    assert result['status'] == 'completed', result['failure_reason']
    assert seen == ['inverse', 'check']


def test_invalid_dispatch_is_corrected_before_any_tool_execution(tmp_path):
    selections = []
    def hook(payload, action):
        ctx = payload.get('context', {})
        if 'ready' in ctx:
            selections.append(ctx)
            if len(selections) == 1:
                return {'dispatch': ['not_a_ready_node']}
            if len(selections) == 2:
                assert ctx['feedback'][0]['unavailable_nodes'] == ['not_a_ready_node']
        return action
    result = run(tmp_path, Client(hook))
    assert result['status'] == 'completed', result['failure_reason']
    assert len(result['calls']) == 2
    assert any(s['type'] == 'selection_error' for s in result['steps'])


def test_invalid_dispatch_retries_are_bounded(tmp_path):
    def hook(payload, action):
        if 'ready' in payload.get('context', {}):
            return {'dispatch': ['unknown']}
        return action
    result = run(tmp_path, Client(hook))
    assert 'selection retry limit' in result['failure_reason']
    assert not result['calls']
    assert len([s for s in result['steps'] if s['type'] == 'selection_error']) == 3


def test_repair_unknown_lookup_receives_feedback_and_keeps_valid_names(tmp_path):
    state = {'graph_reviews': 0, 'queried': False, 'feedback': False}
    def hook(payload, action):
        ctx = payload.get('context', {})
        if ctx.get('stage') == 'graph':
            state['graph_reviews'] += 1
            if state['graph_reviews'] == 1:
                return {'repair': {'nodes': ['inverse'], 'reason': 'Adjust documented parameter'}}
        if 'request' in ctx:
            if not state['queried']:
                state['queried'] = True
                return {'describe_tools': ['MatrixInverse', 'UnknownTool']}
            state['feedback'] = bool(ctx['feedback'])
            assert 'MatrixInverse' in ctx['contracts']
            plan = valid_plan()
            plan['nodes'][0]['purpose'] = 'Compute the required inverse with a clarified purpose'
            return {'plan': plan}
        return action
    result = run(tmp_path, Client(hook))
    assert result['status'] == 'completed', result['failure_reason']
    assert state['feedback']


def test_eigensystem_certificate_accepts_degeneracy_and_checks_columns():
    good = numerical_certificate('SymmetricEigenDecomposition',
        {'values': [[2, 0], [0, 2]]},
        {'eigenvalues': [2, 2], 'eigenvectors': [[0.6, -0.8], [0.8, 0.6]]})
    assert good['passed'] and good['max_abs_equation_residual'] == 0
    bad = numerical_certificate('SymmetricEigenDecomposition',
        {'values': [[2, 0], [0, 3]]},
        {'eigenvalues': [2, 3], 'eigenvectors': [[0.6, -0.8], [0.8, 0.6]]})
    assert not bad['passed']


@pytest.mark.parametrize('phase,expected_calls', [('decompose', 0), ('result', 1)])
def test_api_aborted_scimas_attempt_keeps_evidence_but_has_no_reportable_runtime(tmp_path, phase, expected_calls):
    from src.models.communication import CommunicationError
    def hook(payload, action):
        stage = payload.get('stage', payload.get('context', {}).get('stage'))
        if stage == phase:
            raise CommunicationError('Injected connection failure', service='generation',
                                     category='ConnectTimeout', request_may_have_been_sent=False)
        return action
    result = run(tmp_path, Client(hook))
    assert result['status'] == 'failed'
    assert result['infrastructure_failure']['category'] == 'ConnectTimeout'
    metrics = result['metrics']
    assert not metrics['runtime_reportable'] and metrics['runtime_seconds'] is None
    assert metrics['wall_runtime_seconds'] == result['duration_seconds']
    assert metrics['active_runtime_seconds'] + metrics['communication_wait_seconds'] == pytest.approx(metrics['wall_runtime_seconds'])
    assert len(result['calls']) == expected_calls
    trace = json.loads(open(result['trace_path']).read())
    assert trace['metrics'] == metrics


def test_equation_certificate_has_no_mandatory_numpy_dependency(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'numpy', None)
    result = numerical_certificate('SymmetricEigenDecomposition',
        {'values': [[2, 0], [0, 2]]},
        {'eigenvalues': [2, 2], 'eigenvectors': [[0.6, -0.8], [0.8, 0.6]]})
    assert result['passed']
