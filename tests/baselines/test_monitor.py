"""Monitoring stays outside actors, preserves evidence and reports live state."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from baselines.common import monitor
from baselines.common.metrics import task_metrics
from src.utils.io import atomic_json


def setup_run(folder, **changes):
    folder.mkdir(parents=True, exist_ok=True)
    progress = {'status':'running', 'dataset':'mini', 'baseline':'scimas', 'model':'offline-fixture',
                'runner_pid':os.getpid(), 'selected_tasks':3, 'concurrency':2,
                'tool_concurrency_per_task':4, 'active_tasks':['SMAS-0001','SMAS-0002'],
                'fingerprint':'fixture', **changes}
    atomic_json(folder/'progress.json', progress)
    row = {'id':'SMAS-0001','completed':True,'status':'completed','runtime_seconds':7,
           'input_tokens':10,'output_tokens':3,'observed_input_tokens':10,'observed_output_tokens':3,
           'tool_calls':2,'scientific_tool_calls':1,'discovery_tool_calls':1,
           'model_requests':1,'token_usage_complete':True}
    atomic_json(folder/'task_metrics.json', {'fingerprint':'fixture','tasks':[row]})
    trace = {'status':'running','started_at':datetime.now(timezone.utc).isoformat(),
             'steps':[{'role':'executor','model':{'response':None}}],
             'metrics':{'observed_input_tokens':7,'observed_output_tokens':2,
                        'tool_calls':3,'scientific_tool_calls':3,'discovery_tool_calls':0,'model_requests':2}}
    path = folder/'trajectories/SMAS-0002-fixture/trajectory.json'
    atomic_json(path, trace)
    return progress, path


def test_checkpoint_counts_costs_and_raw_evidence_are_preserved(tmp_path):
    _, path = setup_run(tmp_path)
    raw = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob('*.json')}
    view = monitor.Monitor(tmp_path).write()
    assert view['recorded_tasks'] == view['successful_tasks'] == 1
    assert view['active_tasks_count'] == view['queued_tasks'] == 1
    assert view['active_tasks'][0]['pending_model_response'] is True
    assert view['known_cost_lower_bounds']['input_tokens'] == 17
    assert view['known_cost_lower_bounds']['output_tokens'] == 5
    assert view['known_cost_lower_bounds']['tool_calls'] == 5
    assert view['known_cost_lower_bounds']['model_requests'] == 3
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p,digest in raw.items())
    text = (tmp_path/'monitor/monitor.md').read_text()
    assert '(../trajectories/SMAS-0002-fixture/trajectory.json)' in text
    assert '(../task_metrics.json)' in text
    assert '+08:00' in view['updated_at']
    assert path.read_text()  # The observer never consumes or removes a checkpoint.


def test_missing_usage_is_unknown_and_mismatched_attempts_are_not_combined(tmp_path):
    setup_run(tmp_path)
    atomic_json(tmp_path/'task_metrics.json', {'fingerprint':'fixture','tasks':[
        {'id':'SMAS-0001','completed':False,'status':'failed','input_tokens':None,
         'observed_input_tokens':4,'output_tokens':None,'failure_reason':'ConnectionError'}]})
    view = monitor.Monitor(tmp_path).snapshot()
    assert view['finished_tasks_with_incomplete_usage'] == 1
    assert view['failed_tasks'] == 1
    assert view['failures'][0]['failure_reason'] == 'ConnectionError'
    assert view['known_cost_lower_bounds']['input_tokens'] == 11
    atomic_json(tmp_path/'task_metrics.json', {'fingerprint':'old-attempt','tasks':[{'id':'OLD','completed':True}]})
    view = monitor.Monitor(tmp_path).snapshot()
    assert view['checkpoint_consistent'] is False and view['recorded_tasks'] == 0


def test_retry_does_not_read_the_previous_attempt_as_current_work(tmp_path):
    progress, path = setup_run(tmp_path)
    os.utime(path, (1, 1))
    atomic_json(tmp_path/'progress.json', {**progress,'session_started_at':datetime.now(timezone.utc).isoformat()})
    task = monitor.Monitor(tmp_path).snapshot()['active_tasks'][0]
    assert task['trace_path'] is None and task['metrics'] == {}


def test_active_trace_size_is_bounded_and_partial_json_keeps_last_good_checkpoint(tmp_path, monkeypatch):
    _, path = setup_run(tmp_path)
    observer = monitor.Monitor(tmp_path)
    assert observer.snapshot()['active_tasks'][0]['metrics']['model_requests'] == 2
    path.write_text('{')
    assert observer.snapshot()['active_tasks'][0]['metrics']['model_requests'] == 2
    monkeypatch.setattr(monitor, 'MAX_TRACE_BYTES', 0)
    assert observer.snapshot()['active_tasks'][0]['detail_unavailable'] is True


@pytest.mark.parametrize('stage,expected', [('waiting_for_model','waiting_for_model'),
    ('scimas','waiting_for_scoring'),('score','scoring'),('finished','finished'),('failed','failed')])
def test_supervisor_monitors_model_readiness_generation_and_scoring(tmp_path, stage, expected):
    setup_run(tmp_path, status='finished', active_tasks=[])
    atomic_json(tmp_path/'experiment.json', {'status':stage,'supervisor_pid':os.getpid()})
    assert monitor.Monitor(tmp_path, owner_pid=os.getpid()).snapshot()['status'] == expected


def test_missing_owner_and_stale_scores_are_explicit(tmp_path, monkeypatch):
    setup_run(tmp_path)
    atomic_json(tmp_path/'scores.json', {'summary':{'answer_accuracy':1}})
    os.utime(tmp_path/'scores.json', (1,1))
    monkeypatch.setattr(monitor, 'alive', lambda _:False)
    view = monitor.Monitor(tmp_path).write()
    assert view['status'] == 'runner_missing' and view['active_state_known'] is False
    assert view['score_stale'] is True and view['score_summary'] is None
    assert '批次进程已退出' in (tmp_path/'monitor/monitor.md').read_text()


def test_fresh_scores_appear_and_unknown_fields_never_leak_into_monitor(tmp_path):
    setup_run(tmp_path, status='finished', active_tasks=[])
    atomic_json(tmp_path/'scores.json', {'summary':{'answer_accuracy':.5},'private':'NOT_FOR_MONITOR'})
    atomic_json(tmp_path/'predictions.json', {'settings':{'api_key':'NOT_FOR_MONITOR'}})
    observer=monitor.Monitor(tmp_path)
    view = observer.write()
    assert view['score_summary'] == {'answer_accuracy':.5}
    assert 'NOT_FOR_MONITOR' not in (tmp_path/'monitor/monitor.json').read_text()
    (tmp_path/'scores.json').write_text('{')
    partial=observer.snapshot()
    assert partial['score_stale'] is True and partial['score_summary'] is None


def test_legacy_model_metadata_is_read_without_decoding_the_prediction_body(tmp_path):
    progress,_=setup_run(tmp_path)
    progress.pop('model');atomic_json(tmp_path/'progress.json',progress)
    (tmp_path/'predictions.json').write_text('  {"settings":{"model":"legacy-model","api_key":"SECRET","scimas_execution":{"config":{"tool_concurrency":4}}},"predictions":['+'x'*2000000)
    view=monitor.Monitor(tmp_path).write()
    assert view['model']=='legacy-model'
    assert view['tool_concurrency_per_task']==4
    assert 'SECRET' not in (tmp_path/'monitor/monitor.json').read_text()


def test_planning_summary_uses_the_same_dashboard(tmp_path):
    setup_run(tmp_path, stage='graph_planning', active_tasks=['SMAS-0002'])
    atomic_json(tmp_path/'summary.json', {'tasks':[{'id':'SMAS-0001','status':'planned','requests':3}]})
    view = monitor.Monitor(tmp_path).snapshot()
    assert view['successful_tasks'] == 1 and view['known_cost_lower_bounds']['model_requests'] == 5
    assert view['known_cost_lower_bounds']['tool_calls'] == 3


def test_only_one_background_monitor_writes_and_it_finishes_automatically(tmp_path):
    progress, _ = setup_run(tmp_path, active_tasks=[])
    process = monitor.start_monitor(tmp_path, interval=.05)
    assert process is not None
    try:
        assert monitor.start_monitor(tmp_path, interval=.05) is None
        deadline = time.monotonic()+5
        while not (tmp_path/'monitor/monitor.json').exists() and time.monotonic()<deadline:
            time.sleep(.02)
        assert (tmp_path/'monitor/monitor.md').is_file()
        atomic_json(tmp_path/'progress.json', {**progress,'status':'finished'})
        assert process.wait(timeout=5) == 0
        assert json.loads((tmp_path/'monitor/monitor.json').read_text())['status'] == 'finished'
    finally:
        if process.poll() is None:
            process.terminate();process.wait(timeout=5)


def test_resuming_during_old_monitor_shutdown_keeps_a_live_monitor(tmp_path):
    import fcntl
    progress,_=setup_run(tmp_path,active_tasks=[])
    folder=tmp_path/'monitor';folder.mkdir()
    atomic_json(folder/'monitor.json',{'status':'finished','owner_pid':os.getpid()})
    descriptor=os.open(folder/'.lock',os.O_CREAT|os.O_RDWR,0o600)
    fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
    process=monitor.start_monitor(tmp_path,interval=.05)
    assert process is not None
    os.close(descriptor)
    try:
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if json.loads((folder/'monitor.json').read_text()).get('status')=='running':break
            time.sleep(.02)
        assert json.loads((folder/'monitor.json').read_text())['status']=='running'
        atomic_json(tmp_path/'progress.json',{**progress,'status':'finished'})
        assert process.wait(timeout=5)==0
    finally:
        if process.poll()is None:process.terminate();process.wait(timeout=5)


@pytest.mark.parametrize('baseline,variant,parallel', [
    ('react','full',1), ('scitoolagent','full',1), ('scimas','full',4),
    ('scimas','wo-parallel',1), ('scimas','wo-all',1)])
def test_all_baselines_and_ablations_start_monitor_without_changing_metrics(tmp_path, monkeypatch, baseline, variant, parallel):
    from argparse import Namespace
    from baselines.react import runner
    from tests.integration.test_mini_dataset import options
    args = Namespace(**options(monkeypatch, tmp_path));args.baseline=baseline;args.scimas_ablation=variant
    class Client:
        backend, model = 'api', 'offline-fixture'
        def __init__(self, *a): pass
        def public_settings(self): return {'endpoint':'http://localhost/offline'}
        def close(self): pass
    calls=[];measured=task_metrics({},[],runtime_seconds=2,finished=True)
    def jobs(rows, function, concurrency, on_active, **kw):
        for tid,_ in rows:
            on_active([tid])
            yield tid, {'ok':True,'result':{'id':tid,'completed':True,'status':'completed','metrics':measured}}
    monkeypatch.setattr(runner,'GenerationClient',Client)
    monkeypatch.setattr(runner,'actor_file_hashes',lambda *a:{})
    monkeypatch.setattr(runner,'start_monitor',lambda directory:calls.append(directory))
    monkeypatch.setattr(runner,'iter_tasks',jobs)
    path=runner.run_batch(args)
    progress=json.loads(path.with_name('progress.json').read_text())
    assert calls==[path.parent] and progress['status']=='finished'
    assert progress['tool_concurrency_per_task']==parallel
    assert json.loads(path.read_text())['predictions'][0]['metrics']==measured


def test_manual_once_command_does_not_need_a_model_or_existing_monitor(tmp_path):
    setup_run(tmp_path,status='finished',active_tasks=[])
    subprocess.run([sys.executable,'-m','baselines.common.monitor','--directory',str(tmp_path),'--once'],
                   cwd=Path(__file__).resolve().parents[2], check=True, capture_output=True, timeout=10)
    assert json.loads((tmp_path/'monitor/monitor.json').read_text())['status']=='finished'


def test_removed_result_directory_is_not_recreated(tmp_path):
    folder=tmp_path/'removed';folder.mkdir();observer=monitor.Monitor(folder);folder.rmdir()
    with pytest.raises(FileNotFoundError):observer.write()
    assert not folder.exists()
