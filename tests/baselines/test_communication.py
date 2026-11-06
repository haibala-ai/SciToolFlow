"""Failure classification, circuit admission and exact wall-time exclusions."""
import pytest
from src.models.communication import CommunicationError, CommunicationCircuit, infrastructure_failure
from src.utils.timing import interval_seconds
from baselines.common.resources import TaskResources, BudgetedClient
from baselines.common.metrics import task_metrics
from baselines.react.runner import resume_rows


class Clock:
    now = 100.0
    def __call__(self): return self.now


def test_failed_request_is_excluded_once_including_its_internal_retries():
    clock = Clock()
    resources = TaskResources(clock=clock)
    class Client:
        def request(self, messages, **kw):
            clock.now += 30
            raise CommunicationError('No connection', service='generation', category='ConnectTimeout',
                                     attempts=3, request_may_have_been_sent=False)
    with pytest.raises(CommunicationError) as caught:
        BudgetedClient(Client(), resources).request([])
    usage = resources.snapshot()
    assert usage['communication_fault_seconds'] == 30
    assert usage['requests'][0]['duration_seconds'] == 30
    assert usage['communication_intervals'] == [[100, 130]]
    metrics = task_metrics(usage, [], runtime_seconds=32, finished=True,
                           infrastructure_failure=infrastructure_failure(caught.value))
    assert metrics['runtime_seconds'] is None and not metrics['runtime_reportable']
    assert metrics['wall_runtime_seconds'] == 32
    assert metrics['communication_wait_seconds'] == 30
    assert metrics['active_runtime_seconds'] == 2


def test_successful_request_counts_normal_latency_but_not_reconnection():
    clock = Clock()
    resources = TaskResources(clock=clock)
    class Client:
        def request(self, messages, **kw):
            clock.now += 10
            return {'text': '{}', 'communication_intervals': [[100, 103]],
                    'communication_wait_seconds': 3, 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}
    BudgetedClient(Client(), resources).request([])
    metrics = task_metrics(resources.snapshot(), [], finished=True)
    assert metrics['wall_runtime_seconds'] == 10
    assert metrics['communication_wait_seconds'] == 3
    assert metrics['runtime_seconds'] == 7
    assert metrics['runtime_reportable']


def test_overlapping_network_intervals_are_unioned_and_clipped_to_task_wall():
    usage = {'clock_started_monotonic': 100, 'elapsed_seconds': 20,
             'communication_intervals': [[98, 105], [103, 108], [110, 113], [118, 125]],
             'communication_wait_seconds': 999}
    metrics = task_metrics(usage, [{'tool': 'A', 'duration_seconds': 20},
                                  {'tool': 'B', 'duration_seconds': 20}],
                           communication_wait_seconds=999,
                           communication_intervals=[[104, 107], [112, 114]])
    # [100,108] U [110,114] U [118,120]: 14s, never the sum of overlapping attempts.
    assert metrics['wall_runtime_seconds'] == 20
    assert metrics['communication_wait_seconds'] == 14
    assert metrics['runtime_seconds'] == 6


@pytest.mark.parametrize('spans,total', [([],0), ([[1,3],[1,3]],2),
    ([[1,5],[2,3]],4), ([[1,2],[2,4]],3), ([[1,2],[3,4]],2)])
def test_interval_union_boundaries(spans,total):
    assert interval_seconds(spans) == total


def test_typed_failure_survives_planning_wrapper_without_exposing_messages():
    try:
        try:
            raise CommunicationError('safe diagnostic', service='embedding', category='SSLError')
        except Exception:
            raise RuntimeError('PlanningFailure') from None
    except Exception as error:
        assert infrastructure_failure(error)['service'] == 'embedding'


def test_circuit_opens_on_consecutive_failures_and_stays_open_while_draining():
    circuit = CommunicationCircuit(3)
    failure = {'infrastructure_failure': {'service': 'generation'}}
    circuit.observe(failure); circuit.observe({'completed': True})
    assert not circuit.open and circuit.consecutive == 0
    for _ in range(3): circuit.observe(failure)
    assert circuit.open
    circuit.observe({'completed': True})
    assert circuit.open
    disabled = CommunicationCircuit(0)
    for _ in range(10): disabled.observe(failure)
    assert not disabled.open


def test_resume_only_infrastructure_keeps_model_failures_and_successes():
    rows = [{'id':'a','completed':False,'infrastructure_failure':{'service':'generation'}},
            {'id':'b','completed':False}, {'id':'c','completed':True}]
    selected = resume_rows({'fingerprint':'same','predictions':rows}, 'same', retry_infrastructure=True)
    assert [r['id'] for r in selected] == ['b','c']
    assert rows[0]['id'] == 'a'  # Original attempt is still available for archival.


@pytest.mark.parametrize('recover', [True, False])
def test_real_api_client_and_task_clock_agree_exactly_across_retries(monkeypatch, recover):
    import httpx
    from unittest.mock import Mock
    from src.models.client import GenerationClient
    from tests.baselines.test_api_connect_retry import reply
    clock = Clock()
    attempts = []
    def post(*args, **kwargs):
        attempts.append(len(attempts))
        clock.now += [5, 6, 7][len(attempts) - 1]
        if len(attempts) < 3 or not recover:
            raise httpx.ConnectTimeout('safe fixture')
        return reply()
    monkeypatch.setattr('src.models.client.time.monotonic', clock)
    monkeypatch.setattr('src.models.client.time.sleep', lambda seconds: setattr(clock, 'now', clock.now + seconds))
    monkeypatch.setenv('SCITOOLFLOW_API_EXTRA_BODY', '{}')
    monkeypatch.setenv('SCITOOLFLOW_API_TIMEOUT', '600')
    client = GenerationClient('api', session=Mock(post=post))
    client.model = 'offline-fixture'
    client._transport = 'httpx'
    client._api_connection = ('https://example.invalid', 'NOT_A_REAL_KEY')
    resources = TaskResources(clock=clock)
    failure = None
    with client.generation_scope():
        try:
            BudgetedClient(client, resources).request([{'role':'user','content':'Return JSON'}])
        except CommunicationError as error:
            failure = infrastructure_failure(error)
    metrics = task_metrics(resources.snapshot(), [], finished=True, infrastructure_failure=failure)
    assert len(attempts) == 3
    assert metrics['wall_runtime_seconds'] == 21  # 5+1+6+2+7, from one wall clock.
    if recover:
        assert metrics['communication_wait_seconds'] == 14  # 5+1+6+2, not all 21.
        assert metrics['runtime_seconds'] == 7
    else:
        assert metrics['communication_wait_seconds'] == 21  # Entire failed request, once.
        assert metrics['active_runtime_seconds'] == 0
        assert metrics['runtime_seconds'] is None


def test_embedding_retry_wait_excludes_only_failed_attempts_and_backoff(tmp_path, monkeypatch):
    import requests
    from unittest.mock import Mock
    from baselines.scitoolagent.retrieval import Embeddings
    clock = Clock()
    attempts = []
    def post(*args, **kwargs):
        attempts.append(len(attempts))
        clock.now += [5, 6, 7][len(attempts)-1]
        if len(attempts) < 3:
            raise requests.Timeout('safe fixture')
        return Mock(status_code=200, json=lambda: {'data': []})
    monkeypatch.setattr('baselines.scitoolagent.retrieval.time.monotonic', clock)
    monkeypatch.setattr('baselines.scitoolagent.retrieval.time.sleep', lambda seconds: setattr(clock, 'now', clock.now + seconds))
    resources = TaskResources(clock=clock)
    embedding = Embeddings({'dimension':3,'model':'test'}, tmp_path)
    embedding.request_batch(Mock(post=post), 'https://example.invalid', 'TEST', ['q'], 500)
    metrics = task_metrics(resources.snapshot(), [], communication_intervals=embedding.stats['communication_intervals'])
    assert metrics['wall_runtime_seconds'] == 21
    assert metrics['communication_wait_seconds'] == 14
    assert metrics['runtime_seconds'] == 7


def test_batch_pauses_and_explicit_resume_archives_failed_attempts(tmp_path, monkeypatch):
    import json
    from argparse import Namespace
    from baselines.react import runner
    from tests.integration.test_mini_dataset import options
    args = Namespace(**options(monkeypatch, tmp_path))
    args.tasks = 'SMAS-0103,SMAS-0104,SMAS-0105,SMAS-0106'
    args.baseline = 'scimas'
    recover = [False]
    class Client:
        backend, model = 'api', 'offline-test'
        def __init__(self, *args): pass
        def public_settings(self): return {'endpoint':'http://localhost/offline'}
        def close(self): pass
    def jobs(rows, function, concurrency, on_active, should_schedule=None):
        for tid, _ in rows:
            if should_schedule is not None and not should_schedule(): break
            failure = None if recover[0] else {'service':'generation','category':'ConnectTimeout'}
            prediction = {'id':tid, 'status':'completed' if recover[0] else 'failed',
                          'completed':recover[0], 'metrics': task_metrics({}, [],
                          runtime_seconds=30, finished=True, infrastructure_failure=failure)}
            if failure: prediction['infrastructure_failure'] = failure
            yield tid, {'ok':True,'result':prediction}
    monkeypatch.setattr(runner, 'GenerationClient', Client)
    monkeypatch.setattr(runner, 'actor_file_hashes', lambda *a: {})
    monkeypatch.setattr(runner, 'iter_tasks', jobs)
    path = runner.run_batch(args)
    first = json.loads(path.read_text())
    progress = json.loads(path.with_name('progress.json').read_text())
    assert len(first['predictions']) == 3
    assert progress['status'] == 'paused_infrastructure'
    assert all(p['metrics']['runtime_seconds'] is None for p in first['predictions'])
    recover[0] = True
    args.resume = args.retry_infrastructure = True
    runner.run_batch(args)
    resumed = json.loads(path.read_text())
    assert len(resumed['attempt_history']) == 3
    assert len(resumed['predictions']) == 4
    assert all(p['metrics']['runtime_seconds'] == 30 for p in resumed['predictions'])
    assert json.loads(path.with_name('progress.json').read_text())['status'] == 'finished'
    runner.run_batch(args)
    assert len(json.loads(path.read_text())['attempt_history']) == 3


def test_phase_clock_does_not_deduct_previous_phases_wait():
    usage = {'clock_started_monotonic':100, 'elapsed_seconds':30,
             'communication_intervals':[[101,104],[125,127]]}
    metrics = task_metrics(usage, [], runtime_seconds=10, runtime_started_monotonic=120)
    assert metrics['communication_wait_seconds'] == 2
    assert metrics['runtime_seconds'] == 8


def test_network_recovery_overlapping_parallel_tool_work_is_not_deducted_twice():
    usage = {'clock_started_monotonic':100, 'elapsed_seconds':10,
             'communication_intervals':[[101,105],[103,106]]}
    calls = [{'tool':'A','started_seconds':0,'finished_seconds':10},
             {'tool':'B','started_seconds':0,'finished_seconds':10}]
    metrics = task_metrics(usage, calls, finished=True)
    assert metrics['wall_runtime_seconds'] == 10
    assert metrics['communication_fault_seconds'] == 5
    assert metrics['communication_overlap_seconds'] == 5
    assert metrics['communication_wait_seconds'] == 0
    assert metrics['runtime_seconds'] == 10  # Neither 20 (summed branches) nor 5.


def test_only_the_uncovered_tail_of_a_network_wait_is_deducted():
    usage = {'clock_started_monotonic':100, 'elapsed_seconds':20,
             'communication_intervals':[[102,112],[108,115]]}
    calls = [{'tool':'A','started_seconds':0,'finished_seconds':8},
             {'tool':'B','started_seconds':0,'finished_seconds':10}]
    metrics = task_metrics(usage, calls)
    assert metrics['communication_fault_seconds'] == 13
    assert metrics['communication_overlap_seconds'] == 8
    assert metrics['excluded_communication_intervals'] == [[110,115]]
    assert metrics['runtime_seconds'] == 15


def test_inflight_parallel_call_protects_its_elapsed_work():
    usage = {'clock_started_monotonic':100, 'elapsed_seconds':10,
             'communication_intervals':[[101,105]]}
    pending = [{'tool':'A','started':102}]
    metrics = task_metrics(usage, [], pending_calls=pending)
    assert metrics['communication_wait_seconds'] == 1
    assert metrics['runtime_seconds'] == 9


def test_normal_model_work_intervals_exclude_their_own_failed_connections():
    usage = {'clock_started_monotonic':100, 'elapsed_seconds':20,
             'communication_intervals':[[102,115]],
             'model_work_intervals':[[108,120]]}
    metrics = task_metrics(usage, [])
    assert metrics['communication_wait_seconds'] == 6
    assert metrics['runtime_seconds'] == 14
