"""Adversarial checks across scheduling, role feedback and retrieval scope."""
from copy import deepcopy

import pytest

from baselines.scimas.planner import Planner
from baselines.scimas.task_graph import TaskGraph
from .test_graph import catalog, node, lit, ref
from .test_runtime import Client, run
from .test_knowledge_planner import FixedKnowledge, ScriptedClient, valid_plan, public_example


def test_inspection_breaks_a_consecutive_thinking_streak(tmp_path):
    steps = []
    def hook(payload, action):
        if 'finish' not in action:
            return action
        steps.append(True)
        if len(steps) in (1, 3):
            return {'think': 'Check the recorded evidence before reporting'}
        if len(steps) == 2:
            ctx = payload['context']
            return {'inspect': {'observation_id': ctx['accepted_observations']['inverse'],
                                'path': ['inverse'], 'decoded': False}}
        return action
    result = run(tmp_path, Client(hook), max_consecutive_thinks=1)
    assert result['status'] == 'completed', result['failure_reason']
    assert result['stats']['think_steps'] == 2
    assert result['stats']['inspection_steps'] == 1
    from pathlib import Path
    import hashlib
    from tools import ToolCatalog
    from evaluation.integrity.traces import authenticate_prediction
    prediction = dict(result, id='EXAMPLE', completed=True,
                      trace_sha256=hashlib.sha256(Path(result['trace_path']).read_bytes()).hexdigest())
    authenticated, check = authenticate_prediction(prediction, ToolCatalog().root,
                                                   tmp_path, {'tools': ToolCatalog().tools}, dataset='custom')
    assert check['verified'], check
    assert authenticated['_consecutive_thinks'] == 1


@pytest.mark.parametrize('variant', ['full', 'wo-exp'])
def test_all_variants_receive_explicit_execution_and_gate_context(tmp_path, variant):
    seen = []
    def hook(payload, action):
        ctx = payload.get('context', {})
        if 'graph' in ctx:
            assert ctx['execution_policy']['variant'] == variant
            assert isinstance(ctx['gate_states'], dict)
            assert ctx['graph']['requirements']
            assert 'requirements' not in ctx  # A single complete copy in graph.
            seen.append(True)
        return action
    result = run(tmp_path, Client(hook), scimas_ablation=variant)
    assert result['status'] == 'completed', result['failure_reason']
    assert seen


@pytest.mark.parametrize('op,left,right,expected', [
    ('in', 1, [1.0], True),
    ('in', [1], [[1.0]], True),
    ('eq', [True], [1], False),
    ('eq', {'flag': True}, {'flag': 1}, False),
    ('eq', 1, 1.0, True),
    ('in', True, [1], False),
    ('eq', '1', 1, False),
    ('eq', 1, 1.000000000001, False),
    ('in', 1, [1.000000000001], False),
    ('ne', [True], [1], True),
    ('eq', -0.0, 0, True),
])
def test_gate_equality_and_membership_use_consistent_json_semantics(catalog, op, left, right, expected):
    question = 'Report the result only when the supplied condition is satisfied.'
    graph = TaskGraph.create({'id': 'case', 'question': question, 'inputs': {}},
        [{'id': 'report', 'description': 'Conditional result', 'evidence': question, 'mode': 'screen'}],
        {'nodes': [node('source'), node('result', ref('source'),
             when={'op': op, 'left': lit(left), 'right': lit(right), 'evidence': question})],
         'deliverables': [{'requirement': 'report', 'nodes': ['result'], 'description': 'Result'}]},
        catalog, 'custom')
    assert graph.condition_state('result', {},
        approved_gates={'result': graph.node_identity('result')}) is expected


def test_excluded_known_tool_is_repairable_planning_feedback():
    class RestrictedKnowledge(FixedKnowledge):
        def __init__(self):
            super().__init__()
            self.allowed = lambda name: name != 'MatrixMultiply'
        def search(self, queries, deadline):
            result = super().search(queries, deadline)
            result['tools'].pop('MatrixMultiply')
            return result
        def planning_view(self, names):
            if any(not self.allowed(name) for name in names):
                raise ValueError('Lookup outside current tool scope')
            return {name: self.catalog.describe(name)['tools'][name] for name in names}
    public = deepcopy(public_example())
    public['question'] = 'Report a supported matrix operation on the supplied matrix.'
    requirements = [{'id': 'report', 'description': 'A supported matrix operation',
                     'evidence': public['question'], 'mode': 'complete'}]
    corrected = valid_plan()
    corrected['nodes'] = corrected['nodes'][:1]
    corrected['deliverables'][0]['nodes'] = ['inverse']
    client = ScriptedClient([{'requirements': requirements, 'queries': ['matrix operation']},
                             {'plan': valid_plan()}, {'plan': corrected}])
    result = Planner(RestrictedKnowledge(), client, max_requests=3).plan(public, dataset='custom')
    assert result['status'] == 'planned'
    assert len(client.calls) == 3
    assert 'excluded' in str(result['steps'][1]['validation']['errors'])


def test_protocol_correction_breaks_a_consecutive_thinking_streak(tmp_path):
    steps = []
    def hook(payload, action):
        if 'finish' not in action:
            return action
        steps.append(True)
        if len(steps) in (1, 3):
            return {'think': 'Check the recorded evidence before reporting'}
        if len(steps) == 2:
            return {'unsupported_action': True}
        return action
    result = run(tmp_path, Client(hook), max_consecutive_thinks=1)
    assert result['status'] == 'completed', result['failure_reason']
    assert result['stats']['think_steps'] == 2
    assert result['stats']['protocol_errors'] == 1


def test_repair_inspection_survives_a_contract_query(tmp_path):
    from tools import execute
    state = {'requested': False, 'steps': 0, 'evidence_retained': False}
    def hook(payload, action):
        ctx = payload.get('context', {})
        if ctx.get('stage') == 'result' and ctx.get('node') == 'check' and not state['requested']:
            state['requested'] = True
            return {'repair': {'nodes': ['check'], 'reason': 'Inspect and clarify this branch'}}
        if 'request' in ctx:
            state['steps'] += 1
            if state['steps'] == 1:
                return {'inspect': {'observation_id': ctx['accepted_observations']['inverse'],
                                    'path': ['inverse'], 'decoded': False}}
            if state['steps'] == 2:
                return {'describe_tools': ['MatrixMultiply']}
            assert any(item.get('value') == [[0.5, 0], [0, 0.25]] for item in ctx['feedback'])
            state['evidence_retained'] = True
            plan = valid_plan()
            plan['nodes'][1]['purpose'] = 'Use the inspected inverse and the confirmed product contract'
            return {'plan': plan}
        return action
    result = run(tmp_path, Client(hook), invoke=execute)
    assert result['status'] == 'completed', result['failure_reason']
    assert state['evidence_retained']
    assert result['stats']['inspection_steps'] == 1


def test_repair_records_search_history_and_skips_identical_queries(tmp_path, monkeypatch):
    from . import test_runtime as fixtures
    original = fixtures.Knowledge
    searches = []
    class CountingKnowledge(original):
        def search(self, queries, deadline):
            searches.append(list(queries))
            return super().search(queries, deadline)
    monkeypatch.setattr(fixtures, 'Knowledge', CountingKnowledge)
    state = {'requested': False, 'steps': 0}
    def hook(payload, action):
        ctx = payload.get('context', {})
        if ctx.get('stage') == 'graph' and not state['requested']:
            state['requested'] = True
            return {'repair': {'nodes': ['inverse'], 'reason': 'Clarify the documented inverse operation'}}
        if 'request' in ctx:
            state['steps'] += 1
            if state['steps'] == 1:
                return {'queries': ['Matrix inverse']}
            if state['steps'] == 2:
                return {'queries': ['  Matrix   inverse  ']}
            assert ctx['search_history'] == [['Matrix inverse']]
            assert any('retrieval_notice' in item for item in ctx['feedback'])
            plan = valid_plan()
            plan['nodes'][0]['purpose'] = 'Apply the already retrieved inverse operation'
            return {'plan': plan}
        return action
    result = run(tmp_path, Client(hook))
    assert result['status'] == 'completed', result['failure_reason']
    assert len(searches) == 2  # One initial retrieval and one repair retrieval.


def test_initial_planner_skips_a_previously_executed_query():
    from .test_knowledge_planner import decomposition
    client = ScriptedClient([decomposition(), {'queries': [' matrix   inverse ']}, {'plan': valid_plan()}])
    result = Planner(FixedKnowledge(), client, max_requests=3).plan(public_example(), dataset='custom')
    assert result['status'] == 'planned'
    assert len(result['retrievals']) == 1
    assert len(client.calls) == 3


def test_query_deduplication_preserves_scientific_case_and_units():
    from baselines.scimas.knowledge import fresh_queries
    completed = set()
    fresh, skipped = fresh_queries(['CO', 'Co', 'mM', 'mm', '  CO  ', '\t'], completed)
    assert fresh == ['CO', 'Co', 'mM', 'mm']
    assert skipped == ['  CO  ', '\t']
    assert fresh_queries(['Co', 'co'], completed) == (['co'], ['Co'])


def test_reused_planner_reports_per_call_embedding_usage():
    from .test_knowledge_planner import decomposition
    knowledge = FixedKnowledge()
    client = ScriptedClient([decomposition(), {'plan': valid_plan()},
                             decomposition(), {'plan': valid_plan()}])
    planner = Planner(knowledge, client)
    first = planner.plan(public_example(), dataset='custom')
    second = planner.plan(public_example(), dataset='custom')
    assert first['embedding_usage']['requests'] == second['embedding_usage']['requests'] == 1
    assert knowledge.embedding.stats['requests'] == 2


def test_reused_runtime_knowledge_does_not_charge_previous_task_usage(tmp_path, monkeypatch):
    from . import test_runtime as fixtures
    from baselines.scimas.runtime import run_scimas
    from tools import ToolCatalog
    knowledge = fixtures.Knowledge()
    knowledge.embedding.stats.update(requests=7, prompt_tokens=700,
                                     communication_wait_seconds=20.0, communication_intervals=[])
    original_search = knowledge.search
    def measured_search(queries, deadline):
        knowledge.embedding.stats['requests'] += 1
        return original_search(queries, deadline)
    monkeypatch.setattr(knowledge, 'search', measured_search)
    result = run_scimas(public_example()['question'], catalog=ToolCatalog(),
        knowledge=knowledge, client=Client(), invoke=fixtures.fixture_invoke,
        trace_dir=tmp_path, case_id='SHARED', dataset='custom',
        inputs=public_example()['inputs'])
    assert result['status'] == 'completed', result['failure_reason']
    assert result['embedding_usage']['requests'] == 1
    assert result['embedding_usage']['prompt_tokens'] == 0
    assert result['embedding_usage']['communication_wait_seconds'] == 0
    assert result['metrics']['communication_wait_seconds'] == 0
    assert result['metrics']['runtime_seconds'] == result['metrics']['wall_runtime_seconds']
