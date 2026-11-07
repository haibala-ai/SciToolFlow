"""Intervention isolation, canaries and less common scheduler entry points."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from baselines.scimas.ablation import VARIANTS, resolve_ablation
from baselines.scimas.experience import Experience
from baselines.scimas.runtime import run_scimas
from .test_runtime import Client, Knowledge, fixture_invoke, run
from .test_knowledge_planner import public_example, valid_plan
from .test_ablation import independent_hook


@pytest.mark.parametrize('variant', VARIANTS)
def test_only_declared_configuration_fields_change(variant):
    config = json.loads((Path(__file__).parents[2] / 'baselines/scimas/config.json').read_text())
    # Shared generation/communication controls must also survive intervention.
    config.update(max_model_requests=400, max_output_tokens=65536, task_timeout=7200,
                  api_concurrency=12, concurrency=2, transport_retries=2)
    before = deepcopy(config)
    policy = resolve_ablation(variant)
    expected = deepcopy(config)
    if not policy.parallel:
        expected['tool_concurrency'] = 1
    if not policy.local_repair:
        expected['local_repairs'] = 0
    if not policy.graph_refinement:
        expected['graph_refinements'] = 0
    assert policy.apply(config) == expected
    assert config == before


@pytest.mark.parametrize('variant', ['wo-exp', 'wo-all'])
@pytest.mark.parametrize('failed_call', [False, True])
def test_experience_implementation_is_not_reached(variant, failed_call, monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('Disabled experience implementation was reached')
    for name in ('confirm', 'match', 'invalidate'):
        monkeypatch.setattr(Experience, name, forbidden)
    monkeypatch.setattr('baselines.scimas.runtime.binding_recipe', forbidden)
    def invoke(name, arguments, **kwargs):
        if failed_call:
            return {'status': 'error', 'output': None, 'error_type': 'InvalidInput',
                    'error': 'Controlled deterministic failure'}
        return fixture_invoke(name, arguments, **kwargs)
    result = run(tmp_path, scimas_ablation=variant, invoke=invoke)
    assert result['status'] == ('failed' if failed_call else 'completed'), result['failure_reason']
    assert 'Disabled experience implementation was reached' not in (result['failure_reason'] or '')
    assert result['experiences'] == []


@pytest.mark.parametrize('variant', ['wo-parallel', 'wo-all'])
def test_serial_policy_overrides_concurrency_and_dispatch_flag(variant, tmp_path):
    result = run(tmp_path, Client(independent_hook), scimas_ablation=variant,
                 config={'tool_concurrency': 16})
    assert result['status'] == 'completed', result['failure_reason']
    assert result['limits']['tool_concurrency'] == 1
    dispatches = [s for s in result['steps'] if s['type'] == 'dispatch']
    assert dispatches and all(s['parallel'] is False for s in dispatches)


@pytest.mark.parametrize('variant', ['wo-local-repair', 'wo-all'])
@pytest.mark.parametrize('entry', ['executor', 'result_review', 'summary', 'final_review',
                                  'blocked_binding', 'template_expansion', 'expanded_graph_review'])
def test_every_execution_repair_entry_stays_disabled(variant, entry, tmp_path):
    def hook(payload, action):
        ctx = payload.get('context', {})
        if payload.get('stage') == 'graph' and entry == 'blocked_binding':
            action['plan']['nodes'][1]['arguments']['right']['path'] = ['inverse', 99]
        if payload.get('stage') == 'graph' and entry in {'template_expansion', 'expanded_graph_review'}:
            action['plan']['nodes'][1]['for_each'] = {'kind': 'node', 'node': 'inverse', 'path': ['inverse']}
        triggered = (
            (entry == 'executor' and 'ready' in ctx and 'inverse' in ctx['accepted_result_nodes'])
            or (entry == 'result_review' and ctx.get('stage') == 'result')
            or (entry == 'summary' and 'finish' in action)
            or (entry == 'final_review' and ctx.get('stage') == 'final')
            or (entry == 'expanded_graph_review' and ctx.get('stage') == 'graph'
                and 'inverse' in ctx['accepted_result_nodes'])
        )
        if triggered:
            return {'repair': {'nodes': ['inverse'], 'reason': 'Controlled runtime correction request'}}
        if 'request' in ctx:
            pytest.fail('Disabled execution repair must never request a replacement plan')
        return action
    result = run(tmp_path, Client(hook), scimas_ablation=variant,
                 config={'local_repairs': 50, 'max_map_items': 1 if entry == 'template_expansion' else 128})
    if not resolve_ablation(variant).scientific_review and entry in {'result_review', 'final_review', 'expanded_graph_review'}:
        # These callers have been removed altogether, not allowed to repair.
        assert result['status'] == 'completed', result['failure_reason']
        assert result['repairs'] == result['repair_attempts'] == []
        assert not any(s.get('role') in {'repair', 'reviewer'} for s in result['steps'])
        return
    assert result['status'] == 'failed'
    assert 'LocalRepairDisabled' in result['failure_reason'], result['failure_reason']
    assert result['limits']['local_repairs'] == 0
    assert result['stats']['scientific_calls'] >= 1
    assert result['repairs'] == result['repair_attempts'] == []
    assert not any(step.get('role') == 'repair' for step in result['steps'])
    assert len(result['graphs']) == (2 if entry == 'expanded_graph_review' else 1)


@pytest.mark.parametrize('variant', ['full', 'wo-early-stop', 'wo-all'])
def test_early_stop_policy_applies_after_template_expansion(variant, tmp_path):
    k = Knowledge()
    question = public_example()['question'] + ' Only compute candidates if condition number exceeds 3.'
    def hook(payload, action):
        if payload.get('stage') == 'decompose':
            action['requirements'][0]['mode'] = 'screen'
        if payload.get('stage') == 'graph':
            plan = valid_plan()
            candidate = deepcopy(plan['nodes'][0])
            candidate.update(id='candidate', for_each={'kind': 'task', 'path': ['inputs', 'candidates']})
            candidate['arguments']['values'] = {'kind': 'item', 'path': []}
            candidate['when'] = {
                'op': 'gt', 'left': {'kind': 'node', 'node': 'inverse', 'path': ['condition_number']},
                'right': {'kind': 'literal', 'value': 3}, 'evidence': 'condition number exceeds 3',
            }
            plan['nodes'][1] = candidate
            plan['deliverables'][0]['nodes'] = ['inverse', 'candidate']
            return {'plan': plan}
        return action
    result = run_scimas(question, catalog=k.catalog, knowledge=k, client=Client(hook),
                        invoke=fixture_invoke, trace_dir=tmp_path, case_id='EXPANDED', dataset='custom',
                        inputs={**public_example()['inputs'], 'candidates': [[[2, 0], [0, 4]]] * 2},
                        scimas_ablation=variant)
    assert result['status'] == 'completed', result['failure_reason']
    assert len(result['graphs']) >= 2
    enabled = resolve_ablation(variant).early_stop
    assert len(result['calls']) == (1 if enabled else 3)
    assert len(result['pruned']) == (2 if enabled else 0)
    false_gates = [g for g in result['gate_evaluations'] if g['state'] is False]
    assert len(false_gates) == 2
    assert {g['action'] for g in false_gates} == ({'prune'} if enabled else {'continue_without_screening'})
