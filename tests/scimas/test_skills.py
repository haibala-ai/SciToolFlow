"""Procedural transfer boundaries: reusable interfaces, never cached answers."""
from copy import deepcopy
import json

from baselines.scimas.experience import Experience, binding_recipe
from baselines.scimas.planner import Planner
from .test_knowledge_planner import (
    FixedKnowledge, ScriptedClient, decomposition, valid_plan, public_example,
)
from .test_runtime import Client, run


def test_recipe_reuses_interfaces_without_candidate_values_or_node_ids():
    first = {'kind': 'list', 'items': [
        {'kind': 'node', 'node': 'candidate_A', 'path': ['records', 0, 'value']},
        {'kind': 'literal', 'value': {'answer': 123456, 'secret_object': 'first'}},
    ]}
    second = deepcopy(first)
    second['items'][0].update(node='candidate_B', path=['records', 19, 'value'])
    second['items'][1]['value'] = {'different': 999}
    one = binding_recipe(first, {'candidate_A': 'ReadRecords'})
    two = binding_recipe(second, {'candidate_B': 'ReadRecords'})
    assert one == two
    encoded = json.dumps(one)
    assert all(s not in encoded for s in ['candidate_A', '123456', 'secret_object'])
    assert '<index>' in encoded and 'ReadRecords' in encoded


def test_recipes_keep_output_fields_decoding_and_literal_types_distinct():
    source = {'kind': 'node', 'node': 'n', 'path': ['value']}
    recipes = [binding_recipe(b, {'n': 'T'}) for b in (
        source, dict(source, path=['other']), dict(source, decoded=True),
        {'kind': 'literal', 'value': True}, {'kind': 'literal', 'value': 1},
    )]
    assert len({json.dumps(x, sort_keys=True) for x in recipes}) == 5


def test_repeated_candidates_deduplicate_skill_and_keep_latest_evidence():
    memory = Experience()
    for index in range(50):
        recipe = binding_recipe({'kind': 'node', 'node': str(index), 'path': ['rows', index]},
                                {str(index): 'Read'})
        memory.confirm('planner', 'Read', 'r1', recipe, [f'o{index}'],
                       dependencies={'Consume': 'c1'})
    assert len(memory.entries) == 1
    assert memory.entries[0]['evidence'] == ['o49']


def test_both_edge_contracts_and_branch_relevance_control_transfer():
    memory = Experience()
    memory.confirm('planner', 'Read', 'r1', {'consumed_by': 'Consume'}, ['o1', 'o2'],
                   dependencies={'Consume': 'c1'})
    contracts = {'Read': 'r1', 'Consume': 'c1', 'Other': 'v1'}
    assert memory.match('planner', contracts, focus_tools={'Consume'})
    assert not memory.match('planner', contracts, focus_tools={'Other'})
    assert not memory.match('planner', contracts, focus_tools=set())
    assert not memory.match('executor', contracts)
    assert not memory.match('planner', dict(contracts, Consume='c2'))
    memory.invalidate('Consume', 'c1')
    assert not memory.entries


def test_role_capacity_cannot_be_exhausted_by_another_role():
    memory = Experience(capacity=2, matches=1)
    memory.confirm('planner', 'T', 'v', {'adapter': 'x'}, ['o0'])
    for i in range(10):
        memory.confirm('reviewer', 'T', 'v', {'path': [str(i)]}, [f'o{i}'])
    assert len(memory.entries) == 3
    assert len(memory.match('planner', {'T': 'v'})) == 1
    assert len(memory.match('reviewer', {'T': 'v'})) == 1


def test_planner_only_receives_stage_relevant_instructions():
    client = ScriptedClient([decomposition(), {'plan': valid_plan()}])
    planner = Planner(FixedKnowledge(), client)
    report = planner.plan(public_example(), dataset='custom')
    first, second = [step['messages'][0]['content'] for step in report['steps']]
    assert first == planner.decomposition_prompt
    assert second == planner.prompt
    assert 'for_each' not in first and 'for_each' in second
    assert report['status'] == 'planned'


def test_runtime_records_verified_recipes_without_extra_generation(tmp_path):
    client = Client()
    trace = run(tmp_path, client)
    assert trace['status'] == 'completed', trace['failure_reason']
    # Two planning, graph review, two dispatch/result pairs, summary/final review.
    assert len(client.contexts) == 9
    planner = [e for e in trace['experiences'] if e['role'] == 'planner']
    assert len(planner) == 1
    assert set(planner[0]['required_contracts']) == {'MatrixInverse', 'MatrixMultiply'}
    assert planner[0]['operation']['bindings']['right'][0]['source_tool'] == 'MatrixInverse'
    assert 'node' not in planner[0]['operation']['bindings']['right'][0]
    final = [p['context'] for p in client.contexts
             if p.get('context', {}).get('stage') == 'final']
    assert final and final[0]['experience'] == []


def test_no_exp_disables_recipe_extraction_as_well_as_injection(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Disabled experience must not build recipes')
    monkeypatch.setattr('baselines.scimas.runtime.binding_recipe', forbidden)
    result = run(tmp_path, scimas_ablation='wo-exp')
    assert result['status'] == 'completed', result['failure_reason']
    assert result['experiences'] == []
