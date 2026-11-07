"""Offline component checks only: no agent loop, benchmark task, model or tool process."""
from concurrent.futures import wait
from types import SimpleNamespace
import socket
import subprocess

import pytest

from baselines.scimas.executor import Executor
from baselines.common.metrics import task_metrics
from baselines.common.resources import BudgetedClient, TaskResources
from baselines.scimas.task_graph import TaskGraph
from .test_graph import catalog, template_graph, check, result


@pytest.fixture(autouse=True)
def no_external_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Component checks must not access networks or start subprocesses')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)


def completed_pair(tmp_path):
    pool = Executor(lambda *a, **k: {'status': 'success', 'output': 'receipt'}, tmp_path, 2)
    for name in ['a', 'b']:
        pool.submit({'id': name, 'tool': 'Fake'}, name, {}, parallel=True, files=[], timeout=1)
    assert not wait(pool.running, timeout=2).not_done
    return pool


def test_abandoned_review_batch_keeps_other_receipt_for_cleanup(tmp_path):
    pool = completed_pair(tmp_path)
    logged = []
    try:
        with pytest.raises(RuntimeError, match='review failed'):
            for record, response in pool.completed(0):
                logged.append((record, response))
                raise RuntimeError('review failed')
        assert len(pool.running) == 1
        pool.cancel_all()
        logged.extend(pool.completed(0))
        assert {r['node'] for r, _ in logged} == {'a', 'b'}
        assert len(logged) == 2 and not pool.running
        assert logged[-1][0]['stale']
        assert all(response['status'] == 'success' for _, response in logged)
    finally:
        pool.close()


def test_graph_change_can_invalidate_completed_but_unreviewed_sibling(tmp_path):
    pool = completed_pair(tmp_path)
    try:
        batch = pool.completed(0)
        first, _ = next(batch)
        sibling = next(iter(pool.running.values()))['node']
        assert sibling != first['node']
        pool.invalidate([sibling])
        second, response = next(batch)
        assert second['node'] == sibling and second['stale']
        assert second['cancel'].is_set() and response['status'] == 'success'
        assert list(batch) == [] and not pool.running
    finally:
        pool.close()


@pytest.mark.parametrize('error', [RuntimeError('worker error'), SystemExit('worker exit'), KeyboardInterrupt()])
def test_worker_exits_have_an_error_receipt_not_a_lost_future(tmp_path, error):
    def invoke(*args, **kwargs):
        raise error
    pool = Executor(invoke, tmp_path, 1)
    try:
        pool.submit({'id': 'a', 'tool': 'Fake'}, 'a', {}, parallel=False, files=[], timeout=1)
        rows = list(pool.completed(2))
        assert len(rows) == 1 and not pool.running
        record, response = rows[0]
        assert record['finished'] >= record['started']
        assert response['status'] == 'error'
        assert response['error_type'] == type(error).__name__
    finally:
        pool.close()


@pytest.mark.parametrize('finished,excluded', [(102, 6), (104, 5), (106, 3), (110, 0), (None, 0)])
def test_uncollected_receipt_stops_covering_network_wait_at_actual_finish(finished, excluded):
    usage = {'clock_started_monotonic': 100, 'elapsed_seconds': 10,
             'communication_intervals': [[103, 107], [105, 109]]}
    call = {'tool': 'Fake', 'started': 101}
    if finished is not None:
        call['finished'] = finished
    metrics = task_metrics(usage, [], pending_calls=[call])
    assert metrics['communication_fault_seconds'] == 6
    assert metrics['communication_wait_seconds'] == excluded
    assert metrics['runtime_seconds'] == 10 - excluded
    assert metrics['tool_calls'] == 1 and not metrics['tool_calls_complete']
    if finished is not None:
        receipt = {'tool': 'Fake', 'started_seconds': 1, 'finished_seconds': finished - 100}
        final = task_metrics(usage, [receipt], finished=True)
        assert final['runtime_seconds'] == metrics['runtime_seconds']
        assert final['tool_calls'] == metrics['tool_calls']


def test_finished_and_running_siblings_union_real_work_without_double_counting():
    usage = {'clock_started_monotonic': 100, 'elapsed_seconds': 10,
             'communication_intervals': [[102, 109]]}
    metrics = task_metrics(usage, [], pending_calls=[
        {'tool': 'FakeA', 'started': 100, 'finished': 104},
        {'tool': 'FakeB', 'started': 105, 'finished': 107},
    ])
    assert metrics['excluded_communication_intervals'] == [[104, 105], [107, 109]]
    assert metrics['runtime_seconds'] == 7


def test_interrupted_model_request_does_not_remain_pending_or_count_as_network_failure():
    clock = [100]
    resources = TaskResources(clock=lambda: clock[0])
    def request(*args, **kwargs):
        clock[0] = 103
        raise KeyboardInterrupt()
    client = BudgetedClient(SimpleNamespace(request=request), resources)
    with pytest.raises(KeyboardInterrupt):
        client.request([])
    usage = resources.snapshot()
    assert usage['requests'][0]['status'] == 'error'
    assert usage['requests'][0]['interrupted'] is True
    assert usage['requests'][0]['duration_seconds'] == 3
    assert usage['model_requests'] == 1
    assert usage['communication_fault_seconds'] == 0
    assert not usage['token_usage_complete']
    assert usage['prompt_tokens'] is None and usage['completion_tokens'] is None
    from evaluation.integrity.resources import check_resources
    checked = check_resources({
        'completed': False, '_resource_usage': usage,
        '_execution_limits': {'resource_policy': 'task-resources.v1',
                              'model_requests': 400, 'task_seconds': 7200},
    }, {'version': 'task-resources.v1', 'max_model_requests': 400, 'task_seconds': 7200})
    assert checked['verified'] and checked['model_requests'] == 1


@pytest.mark.parametrize('length', [77, 78, 80])
def test_valid_long_template_ids_expand_with_valid_distinct_children(catalog, length):
    original = template_graph(catalog)
    plan = original.plan
    name = 'm' * length
    plan['nodes'][1]['id'] = name
    plan['nodes'][2]['arguments']['values']['node'] = name
    graph = TaskGraph.create(original.task, original.requirements, plan, catalog)
    assert check(graph, catalog)['valid']
    evidence = {'source': graph.accept_result('source', {'status': 'success', 'output': {'values': [2, 3]}}, catalog)}
    expanded, _ = graph.expand(name, evidence, catalog)
    assert check(expanded, catalog)['valid']
    children = expanded.ready(evidence, catalog)
    assert len(children) == 2 and len(set(children)) == 2
    assert all(len(nid) <= 80 for nid in children)
    again, _ = graph.expand(name, evidence, catalog)
    assert again.plan == expanded.plan
    for nid in children:
        evidence[nid] = result(expanded, catalog, nid, expanded.arguments(nid, evidence, catalog)['value'])
    assert expanded.arguments('joined', evidence, catalog)['values'] == [2, 3]
