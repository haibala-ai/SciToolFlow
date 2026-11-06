"""Unknown-format probes have bounded, causal scientific-input certificates."""
from copy import deepcopy
import pytest
from evaluation.workflow import score_workflow, validate_workflow
from tests.evaluation.test_mini_orchestration_design import reference
from tests.evaluation.test_workflow_capability_groups import prediction
from tests.support.workflows import call


ERROR = 'Expected a bounded JSON object-record list,optionally under data'


def fixture():
    ref = reference()
    ref['evaluation']['efficiency']['disambiguation_rules'] = [{
        'id': 'unknown-root-format', 'tools': ['Inspect'], 'statuses': ['error'],
        'error_types': ['InvalidInput'], 'before_nodes': ['source'], 'max_calls': 1,
        'input_rules': [{'path': '/file', 'op': 'eq', 'value': 'public.json'}],
        'output_rules': [
            {'left': {'source': 'call_error', 'path': ''}, 'op': 'eq', 'value': ERROR},
            {'left': {'source': 'call_output', 'path': ''}, 'op': 'type', 'value': 'null'},
        ],
    }]
    pred = prediction('difference')
    probe = call('probe', 'Inspect', {'file': 'public.json'}, None)
    probe.update(status='error', error_type='InvalidInput', error=ERROR)
    pred['calls'].insert(0, probe)
    return ref, pred


def test_one_correct_unknown_format_probe_before_real_read_is_bounded():
    ref, pred = fixture()
    score = score_workflow(ref, pred)
    assert score['planning_pass'] and score['selection_efficiency'] == 1
    duplicate = deepcopy(pred['calls'][0]); duplicate['observation_id'] = 'repeat'
    pred['calls'].insert(1, duplicate)
    assert score_workflow(ref, pred)['selection_efficiency'] == 2/3


@pytest.mark.parametrize('kind', ['path', 'error', 'error_type', 'already-read', 'missing-reader'])
def test_wrong_input_failure_and_informed_probe_are_not_free(kind):
    ref, pred = fixture()
    if kind == 'path': pred['calls'][0]['arguments']['file'] = 'other.json'
    elif kind == 'error': pred['calls'][0]['error'] = 'wrong parameter'
    elif kind == 'error_type': pred['calls'][0]['error_type'] = 'Timeout'
    elif kind == 'already-read': pred['calls'].insert(1, pred['calls'].pop(0))
    elif kind == 'missing-reader': pred['calls'] = [pred['calls'][0]]
    score = score_workflow(ref, pred)
    assert score['exploration_exempt_calls'] == 0


def test_later_reader_cannot_hide_that_source_was_already_read_before_probe():
    ref, pred = fixture()
    source = deepcopy(pred['calls'][1]); source['observation_id'] = 'earlier-read'
    pred['calls'].insert(0, source)
    assert score_workflow(ref, pred)['exploration_exempt_calls'] == 0


def test_timed_parallel_collection_order_preserves_probe_causality():
    ref, pred = fixture()
    for index, receipt in enumerate(pred['calls']):
        receipt.update(started_seconds=2*index, finished_seconds=2*index+1)
    pred['calls'].reverse()
    assert score_workflow(ref, pred)['selection_efficiency'] == 1
    probe = next(c for c in pred['calls'] if c['tool'] == 'Inspect')
    probe['finished_seconds'] = 3
    assert score_workflow(ref, pred)['exploration_exempt_calls'] == 0


@pytest.mark.parametrize('before', [[], ['missing'], ['source', 'source']])
def test_invalid_before_constraints_are_rejected(before):
    ref, _ = fixture()
    ref['evaluation']['efficiency']['disambiguation_rules'][0]['before_nodes'] = before
    with pytest.raises(ValueError): validate_workflow(ref['evaluation'])
