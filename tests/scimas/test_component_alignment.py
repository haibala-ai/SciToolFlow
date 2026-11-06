"""Component boundary regressions; scripted roles and local evidence only."""
from copy import deepcopy

import pytest

from baselines.scimas.planner import Planner
from baselines.scimas.task_graph import TaskGraph
from baselines.scimas.validation import path_schema
from .test_graph import catalog, spec, node, ref, graph, check, template_graph
from .test_runtime import run, Client
from .test_runtime import fixture_invoke
from .test_knowledge_planner import FixedKnowledge, ScriptedClient, decomposition, valid_plan, public_example


@pytest.mark.parametrize('record_schema', [
    {'type': 'object'},
    {'type': 'object', 'additionalProperties': True},
    {'type': 'object', 'properties': {'id': {'type': 'string'}}},
])
def test_reader_dynamic_fields_are_runtime_obligations(catalog, record_schema):
    catalog.tools['Reader'] = spec({'value': {'type': 'number'}}, {
        'type': 'object', 'properties': {
            'preview_records': {'type': 'array', 'items': record_schema}},
        'required': ['preview_records'], 'additionalProperties': False})
    g = graph(catalog, [node('read', tool='Reader'),
                       node('use', ref('read', ['preview_records', 0, 'score']), tool='Consume')])
    report = check(g, catalog)
    assert report['valid'], report
    assert any(item['check'] == 'actual_field_presence_and_full_parameter_contract'
               for item in report['runtime_obligations'])
    for record, expected in [({'id': 'r1', 'score': 7}, 7),
                             ({'id': 'r1'}, None),
                             ({'id': 'r1', 'score': 'wrong type'}, None)]:
        evidence = {'read': g.accept_result('read', {
            'status': 'success', 'output': {'preview_records': [record]}}, catalog)}
        if expected is None:
            with pytest.raises(ValueError):
                g.arguments('use', evidence, catalog)
        else:
            assert g.arguments('use', evidence, catalog) == {'value': expected}


@pytest.mark.parametrize('schema', [
    {'type': 'object', 'additionalProperties': False},
    {'type': 'object', 'unevaluatedProperties': False},
    {'type': 'number'}, {'type': 'array'}, {'type': 'string'},
])
def test_runtime_uncertainty_does_not_override_closed_or_wrong_container(schema):
    with pytest.raises(ValueError):
        path_schema(schema, ['smiles'])


@pytest.mark.parametrize('values', [[2, 3], []])
def test_chained_map_collects_remain_bound_to_real_producers(catalog, values):
    original = template_graph(catalog)
    plan = deepcopy(original.plan)
    plan['nodes'][0]['arguments']['values']['value'] = values
    plan['nodes'].insert(2, node('second', {'kind': 'item', 'path': []},
        for_each={'kind': 'collect', 'node': 'mapped', 'path': ['value']}))
    plan['nodes'][-1]['arguments']['values'] = {
        'kind': 'collect', 'node': 'second', 'path': ['value']}
    g = TaskGraph.create(original.task, original.requirements, plan, catalog, 'custom')
    assert check(g, catalog)['valid']
    evidence = {'source': g.accept_result('source', {
        'status': 'success', 'output': {'values': values}}, catalog)}
    g, _ = g.expand('mapped', evidence, catalog)
    assert check(g, catalog)['valid']
    for index, value in enumerate(values):
        nid = 'mapped__' + str(index)
        evidence[nid] = g.accept_result(nid, {'status': 'success', 'output': {'value': value}}, catalog)
    g, _ = g.expand('second', evidence, catalog)
    assert check(g, catalog)['valid']
    for index, value in enumerate(values):
        nid = 'second__' + str(index)
        assert g.arguments(nid, evidence, catalog) == {'value': value}
        evidence[nid] = g.accept_result(nid, {'status': 'success', 'output': {'value': value}}, catalog)
    assert g.arguments('joined', evidence, catalog) == {'values': values}
    if values:
        evidence.pop('mapped__0')
        with pytest.raises((ValueError, KeyError)):
            g.arguments('second__0', evidence, catalog)


def test_known_catalogue_tools_do_not_need_an_extra_retrieval_round():
    class NarrowKnowledge(FixedKnowledge):
        def search(self, queries, deadline):
            result = super().search(queries, deadline)
            result['tools'].pop('MatrixMultiply')
            return result
    client = ScriptedClient([decomposition(), {'plan': valid_plan()}])
    result = Planner(NarrowKnowledge(), client, max_requests=2).plan(public_example(), dataset='custom')
    assert result['status'] == 'planned'
    assert any(item['mode'] == 'plan_contract_resolution'
               and item['names'] == ['MatrixMultiply'] for item in result['contract_queries'])
    assert len(client.calls) == 2


@pytest.mark.parametrize('action_kind', ['bad_plan', 'queries', 'describe_tools', 'bad_protocol'])
def test_repair_bounds_count_all_generation_requests(tmp_path, action_kind):
    requests = []
    def hook(payload, action):
        ctx = payload.get('context', {})
        if ctx.get('stage') == 'graph':
            return {'repair': {'nodes': ['inverse'], 'reason': 'Regression repair request'}}
        if 'request' in ctx:
            requests.append(payload)
            if action_kind == 'queries':
                return {'queries': ['matrix inverse']}
            if action_kind == 'describe_tools':
                return {'describe_tools': ['MatrixInverse']}
            if action_kind == 'bad_protocol':
                return {'unknown_action': True}
            plan = valid_plan()
            plan['nodes'][0]['arguments'] = {}
            return {'plan': plan}
        return action
    result = run(tmp_path, Client(hook), config={'repair_requests': 2})
    assert 'RepairRequestLimit' in result['failure_reason']
    assert len(requests) == 2
    assert [p['context']['remaining_requests'] for p in requests] == [2, 1]
    assert result['graph_refinement_attempts'][0]['status'] == 'request_limit'
    assert result['graph_refinement_attempts'][0]['requests'] == 2
    assert not result['repairs']
    assert result['stats']['model_turns'] == len(result['resource_usage']['requests'])


def test_identical_inspections_cannot_loop_until_the_task_deadline(tmp_path):
    def hook(payload, action):
        ctx = payload.get('context', {})
        allows_inspection = any('inspect' in branch.get('properties', {})
                                for branch in payload.get('response_schema', {}).get('oneOf', []))
        if ctx.get('stage') == 'result' and allows_inspection:
            return {'inspect': {'observation_id': ctx['observation_id'], 'path': [], 'decoded': False}}
        return action
    result = run(tmp_path, Client(hook))
    assert result['status'] == 'completed', result['failure_reason']
    assert len(result['calls']) == 2
    assert result['stats']['inspection_steps'] == 6  # Three inspections for each real result.
    assert sum(bool(step.get('progress_intervention')) for step in result['steps']) == 2


def test_schema_composition_preserves_sibling_types_and_closed_paths():
    schema = {'type': 'object', 'properties': {'known': {'type': 'number'}},
              'additionalProperties': False,
              'anyOf': [{'required': ['known']}, {'properties': {'known': {'minimum': 0}}}]}
    assert path_schema(schema, ['known'])['anyOf'][0] == {'type': 'number'}
    with pytest.raises(ValueError):
        path_schema(schema, ['invented'])
    with pytest.raises(ValueError):
        path_schema({'allOf': [{'type': 'object'}, {'additionalProperties': False}]}, ['invented'])
    assert path_schema({'allOf': [{'type': 'object'}, {'properties': {'value': {'type': 'number'}}}]}, ['value']) == {'type': 'number'}


def test_repair_role_can_inspect_existing_outputs_without_repeating_tools(tmp_path):
    state = {'requested': False, 'inspected': False, 'feedback_received': False}
    def hook(payload, action):
        ctx = payload.get('context', {})
        if ctx.get('stage') == 'result' and ctx.get('node') == 'check' and not state['requested']:
            state['requested'] = True
            return {'repair': {'nodes': ['check'], 'reason': 'Inspect upstream evidence before revising this branch'}}
        if 'request' in ctx:
            if not state['inspected']:
                state['inspected'] = True
                return {'inspect': {'observation_id': ctx['accepted_observations']['inverse'],
                                    'path': ['inverse'], 'decoded': False}}
            assert ctx['feedback'][0]['value'] == [[0.5, 0], [0, 0.25]]
            state['feedback_received'] = True
            plan = valid_plan()
            plan['nodes'][1]['purpose'] = 'Use the inspected inverse in the requested identity-product check'
            return {'plan': plan}
        return action
    result = run(tmp_path, Client(hook), config={'repair_requests': 2})
    assert result['status'] == 'completed', result['failure_reason']
    assert state['feedback_received']
    assert sum(call['tool'] == 'MatrixInverse' for call in result['calls']) == 1
    assert result['repair_attempts'][0]['requests'] == 2


@pytest.mark.parametrize('category', ['format', 'scientific_review'])
def test_unchanged_rejected_final_answers_have_a_no_progress_boundary(tmp_path, category):
    def hook(payload, action):
        if category == 'format' and 'finish' in action:
            return {'finish': {'inverse': 'wrong type', 'product': []}}
        if category == 'scientific_review' and payload.get('context', {}).get('stage') == 'final':
            return {'revise_answer': 'This regression reviewer requires a correction'}
        return action
    result = run(tmp_path, Client(hook), answer_schema_guard=False)
    assert 'FinalAnswerNoProgress' in result['failure_reason']
    assert len(result['calls']) == 2
    assert result['final_answer'] is None


def test_original_tool_failure_reaches_reviewer_and_repair_role(tmp_path):
    state = {'failed': False, 'reviewer_saw_error': False, 'repair_saw_error': False}
    detail = 'Input document uses records; this selected adapter requires a data list'
    def invoke(name, arguments, **kwargs):
        if name == 'MatrixInverse' and not state['failed']:
            state['failed'] = True
            return {'status': 'error', 'output': None, 'error_type': 'InvalidInput', 'error': detail}
        return fixture_invoke(name, arguments, **kwargs)
    def hook(payload, action):
        ctx = payload.get('context', {})
        if ctx.get('stage') == 'result' and ctx['structural_validation'] != 'passed':
            failed = ctx['observations'][ctx['observation_id']]
            assert failed['error'] == detail and failed['error_type'] == 'InvalidInput'
            assert detail in ctx['structural_validation']
            state['reviewer_saw_error'] = True
            return {'repair': {'nodes': ['inverse'], 'reason': 'Fix the documented input incompatibility'}}
        if 'request' in ctx:
            assert any(row.get('error') == detail for row in ctx['observations'].values())
            state['repair_saw_error'] = True
            plan = valid_plan()
            plan['nodes'][0]['purpose'] = 'Use the corrected compatible input'
            return {'plan': plan}
        return action
    result = run(tmp_path, Client(hook), invoke=invoke)
    assert result['status'] == 'completed', result['failure_reason']
    assert state['reviewer_saw_error'] and state['repair_saw_error']
    assert len(result['calls']) == 3
