"""Repair feedback corrects protocol mistakes without changing scientific judgment."""
import pytest
from .test_runtime import Client, run


@pytest.mark.parametrize('stage', ['graph', 'result', 'final', 'executor', 'summary'])
@pytest.mark.parametrize('targets', [[], ['misspelled_node']])
def test_bad_repair_target_gets_bounded_feedback_before_repair(tmp_path, stage, targets):
    state = {'injected': False, 'corrected': False}
    def hook(payload, action):
        ctx = payload.get('context', {})
        matches = (ctx.get('stage') == stage if stage in {'graph', 'result', 'final'} else
                   'ready' in ctx if stage == 'executor' else 'finish' in action)
        if matches:
            if not state['injected']:
                state['injected'] = True
                return {'repair': {'nodes': targets, 'reason': 'Protocol test: invalid target identifier'}}
            if not state['corrected']:
                assert payload['format_feedback']['errors']
                assert payload['format_feedback']['previous_response']
                state['corrected'] = True
        return action
    trace = run(tmp_path, client=Client(hook))
    assert trace['status'] == 'completed', trace['failure_reason']
    assert state == {'injected': True, 'corrected': True}
    assert not trace['repairs'] and not trace['graph_refinements']
    assert trace['stats']['protocol_errors'] == 1
    assert len(trace['calls']) == 2


def test_persistently_invalid_repair_targets_still_fail(tmp_path):
    def hook(payload, action):
        if payload.get('context', {}).get('stage') == 'graph':
            return {'repair': {'nodes': ['missing'], 'reason': 'Unsupported target'}}
        return action
    trace = run(tmp_path, client=Client(hook))
    assert trace['status'] == 'failed'
    assert 'Role protocol retry limit' in trace['failure_reason']
    assert trace['stats']['protocol_errors'] == 3
    assert not trace['calls'] and not trace['repairs'] and not trace['graph_refinements']


def test_native_output_decoding_is_known_before_scientific_review(tmp_path):
    state = {'injected': False, 'corrected': False}
    def hook(payload, action):
        ctx = payload.get('context', {})
        if ctx.get('stage') == 'result':
            branch = next(b for b in payload['response_schema']['oneOf'] if 'accept' in b['properties'])
            assert branch['properties']['accept']['properties']['semantics']['items']['properties']['decoded'] == {'const': False}
            if not state['injected']:
                state['injected'] = True
                return {'accept': {'reason': 'Decoding boundary test', 'semantics': [
                    {'key': 'unit', 'value': 'invented', 'path': ['unit'], 'decoded': True}]}}
            if not state['corrected']:
                assert payload['format_feedback']['errors']
                state['corrected'] = True
        return action
    trace = run(tmp_path, client=Client(hook))
    assert trace['status'] == 'completed', trace['failure_reason']
    assert state == {'injected': True, 'corrected': True}
    assert trace['stats']['protocol_errors'] == 1
    assert all(not value['semantics'] for value in trace['results'].values())
    assert not trace['repairs']


def test_native_flag_does_not_make_invented_metadata_valid(tmp_path):
    state = {'rejected': False}
    def hook(payload, action):
        ctx = payload.get('context', {})
        if ctx.get('stage') == 'result' and ctx['node'] == 'inverse':
            if not ctx['semantic_feedback']:
                return {'accept': {'reason': 'Metadata grounding boundary test', 'semantics': [
                    {'key': 'unit', 'value': 'invented', 'path': ['unit'], 'decoded': False}]}}
            assert 'error' in ctx['semantic_feedback'][0]
            state['rejected'] = True
        return action
    trace = run(tmp_path, client=Client(hook))
    assert trace['status'] == 'completed', trace['failure_reason']
    assert state['rejected']
    assert trace['results']['inverse']['semantics'] == {}
