"""Read-only batch monitor; its process never performs model or tool requests."""
from datetime import datetime, timezone
import argparse
import fcntl
import glob
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

from src.utils.io import atomic_json

TERMINAL = {'finished', 'finished_with_errors', 'failed', 'interrupted', 'paused_infrastructure'}
MAX_TRACE_BYTES = 64 * 1024 * 1024


def alive(pid):
    if type(pid) is not int or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
        status = Path('/proc')/str(pid)/'stat'
        if status.exists() and status.read_text().rsplit(')', 1)[-1].split()[0] == 'Z':
            return False
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _age(timestamp, now):
    try:
        value = datetime.fromisoformat(timestamp)
        if value.tzinfo is None:
            return None
        return max(0, (now-value).total_seconds())
    except (TypeError, ValueError):
        return None


def _count(value):
    return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else 0


class Monitor:
    def __init__(self, directory, *, owner_pid=None, interval=10):
        self.directory = Path(directory).resolve()
        self.owner_pid = owner_pid
        self.interval = interval
        self.cache = {}
        self.sequence = 0
        self.legacy_metadata = None

    def metadata(self):
        """Read only a bounded JSON header for attaching to older runs."""
        if self.legacy_metadata is not None:
            return self.legacy_metadata
        try:
            with (self.directory/'predictions.json').open() as stream:
                text = stream.read(1024*1024)
            decoder = json.JSONDecoder()
            cursor = len(text)-len(text.lstrip())+1 if text.lstrip().startswith('{') else len(text)
            while cursor < len(text):
                while cursor < len(text) and text[cursor] in ' \r\n\t,':
                    cursor += 1
                key, cursor = decoder.raw_decode(text, cursor)
                while cursor < len(text) and text[cursor] in ' \r\n\t:':
                    cursor += 1
                if key in {'predictions', 'attempt_history'}:
                    break
                value, cursor = decoder.raw_decode(text, cursor)
                if key == 'settings' and isinstance(value, dict):
                    self.legacy_metadata = {k:value.get(k) for k in ['model','backend','baseline','dataset','concurrency']}
                    execution = value.get('scimas_execution', {})
                    if isinstance(execution, dict) and isinstance(execution.get('config'), dict):
                        self.legacy_metadata['tool_concurrency_per_task'] = execution['config'].get('tool_concurrency')
                    return self.legacy_metadata
            self.legacy_metadata = {}
        except (OSError, ValueError):
            return {}
        return self.legacy_metadata

    def read(self, path, *, limit=None):
        path = Path(path)
        try:
            stat = path.stat()
            if limit is not None and stat.st_size > limit:
                return {}
            identity = stat.st_mtime_ns, stat.st_size
            if path not in self.cache or self.cache[path][0] != identity:
                data = json.loads(path.read_text())
                if not isinstance(data, dict):
                    return {}
                self.cache[path] = identity, data
            return self.cache[path][1]
        except (OSError, ValueError):
            return self.cache.get(path, (None, {}))[1]

    def snapshot(self):
        folder = self.directory
        now = datetime.now(timezone.utc)
        progress = self.read(folder/'progress.json')
        experiment = self.read(folder/'experiment.json')
        metadata = self.metadata() if not progress.get('model') and not experiment.get('model') else {}
        metrics = self.read(folder/'task_metrics.json')
        consistent = not (progress.get('fingerprint') and metrics.get('fingerprint')
                          and progress['fingerprint'] != metrics['fingerprint'])
        rows = metrics.get('tasks', []) if consistent else []
        if progress.get('stage') == 'graph_planning':
            rows = [{**row, 'completed':row.get('status') == 'planned',
                     'model_requests':row.get('requests'), 'tool_calls':0,
                     'scientific_tool_calls':0, 'discovery_tool_calls':0}
                    for row in self.read(folder/'summary.json').get('tasks', [])]
        rows = [row for row in rows if isinstance(row, dict) and isinstance(row.get('id'), str)]
        # Compact task metrics, rather than potentially enormous prediction
        # bodies, are the source of completed-attempt counts and costs.
        done = {row['id'] for row in rows}
        selected = progress.get('selected_tasks', experiment.get('denominator', len(rows)))
        selected = int(_count(selected))
        owner_pid = self.owner_pid or progress.get('runner_pid') or experiment.get('supervisor_pid')
        supervised = bool(experiment.get('supervisor_pid') == owner_pid and owner_pid)
        state = progress.get('status', 'initializing')
        if supervised:
            stage = experiment.get('status', 'initializing')
            if stage in TERMINAL or stage in {'waiting_for_model', 'score'}:
                state = 'scoring' if stage == 'score' else stage
                if stage == 'finished' and progress.get('status') == 'paused_infrastructure':
                    state = 'paused_infrastructure'
            elif state == 'finished':
                state = 'waiting_for_scoring'
        owner_alive = alive(owner_pid)
        if owner_alive is False and state not in TERMINAL:
            state = 'runner_missing'
        active = []
        retained = set()
        for identifier in dict.fromkeys(progress.get('active_tasks', [])):
            if not isinstance(identifier, str) or identifier in done:
                continue
            candidates = []
            for path in (folder/'trajectories').glob(glob.escape(identifier)+'-*/trajectory.json'):
                try:
                    started_age = _age(progress.get('session_started_at'), now)
                    if started_age is None or path.stat().st_mtime >= now.timestamp()-started_age-1:
                        candidates.append(path)
                except OSError:
                    pass
            path = max(candidates, key=lambda p:p.stat().st_mtime_ns) if candidates else None
            trace = self.read(path, limit=MAX_TRACE_BYTES) if path else {}
            if path:
                retained.add(path)
            steps = [s for s in trace.get('steps', []) if isinstance(s, dict) and isinstance(s.get('model'), dict)]
            last = steps[-1] if steps else {}
            model = last.get('model', {})
            pending = bool(last and model.get('response') is None and not model.get('error'))
            phase = last.get('role', last.get('type', progress.get('stage', 'initializing')))
            if trace.get('pending_calls') and not pending:
                phase = 'tools'
            active.append({'id':identifier, 'status':trace.get('status', 'initializing'),
                           'phase':phase, 'pending_model_response':pending,
                           'task_age_seconds':_age(trace.get('started_at'), now),
                           'last_checkpoint_age_seconds':max(0, now.timestamp()-path.stat().st_mtime) if path else None,
                           'generation_steps':len(steps),
                           'responses_recorded':sum(s['model'].get('response') is not None for s in steps),
                           'metrics':trace.get('metrics', {}),
                           'trace_path':str(path.relative_to(folder)) if path else None,
                           'detail_unavailable':bool(path and not trace)})
        for path in list(self.cache):
            if path.name == 'trajectory.json' and path not in retained:
                del self.cache[path]
        known = [*rows, *(t['metrics'] for t in active)]
        def total(name, fallback=None):
            return sum(_count(row.get(name) if row.get(name) is not None else row.get(fallback)) for row in known)
        failures = [{'id':row['id'], 'status':row.get('status'),
                     'failure_reason':str(row.get('failure_reason') or 'See task trajectory')[:600],
                     'trace_path':row.get('trace_path')} for row in rows if not row.get('completed')]
        scores = self.read(folder/'scores.json')
        score_stale = False
        try:
            score_stat = (folder/'scores.json').stat()
            parsed_identity = self.cache.get(folder/'scores.json', (None, {}))[0]
            score_stale = bool(scores) and (parsed_identity != (score_stat.st_mtime_ns, score_stat.st_size)
                                           or score_stat.st_mtime_ns < (folder/'task_metrics.json').stat().st_mtime_ns)
        except OSError:
            pass
        result = {'schema_version':'scitoolflow.live_monitor.v1', 'sequence':self.sequence,
                  'updated_at':now.astimezone(ZoneInfo('Asia/Shanghai')).isoformat(),
                  'refresh_interval_seconds':self.interval, 'status':state,
                  'dataset':progress.get('dataset') or experiment.get('dataset') or metadata.get('dataset'),
                  'baseline':progress.get('baseline') or experiment.get('baseline') or metadata.get('baseline'),
                  'ablation':progress.get('ablation'),
                  'model':progress.get('model') or experiment.get('model') or metadata.get('model'),
                  'backend':progress.get('backend') or experiment.get('backend') or metadata.get('backend'),
                  'configured_task_concurrency':progress.get('concurrency', experiment.get('concurrency', metadata.get('concurrency'))),
                  'tool_concurrency_per_task':progress.get('tool_concurrency_per_task', metadata.get('tool_concurrency_per_task')),
                  'owner_pid':owner_pid, 'owner_alive':owner_alive,
                  'experiment_status':experiment.get('status') if supervised else None,
                  'selected_tasks':selected, 'recorded_tasks':len(rows),
                  'successful_tasks':sum(bool(row.get('completed')) for row in rows),
                  'failed_tasks':len(failures), 'active_tasks_count':len(active),
                  'queued_tasks':max(0, selected-len(rows)-len(active)),
                  'progress_percent':100*len(rows)/selected if selected else 0,
                  'checkpoint_consistent':consistent,
                  'active_state_known':owner_alive is not False,
                  'active_tasks':active, 'failures':failures,
                  'communication_circuit':progress.get('communication_circuit'),
                  'known_cost_lower_bounds':{
                      'input_tokens':total('observed_input_tokens', 'input_tokens'),
                      'output_tokens':total('observed_output_tokens', 'output_tokens'),
                      **{name:total(name) for name in ['tool_calls','scientific_tool_calls','discovery_tool_calls','model_requests']}},
                  'finished_tasks_with_incomplete_usage':sum(not row.get('token_usage_complete', False) for row in rows),
                  'score_summary':None if score_stale else scores.get('summary'),
                  'score_stale':score_stale,
                  'note':'Latest retained attempts only. Running costs are checkpoint lower bounds; missing usage is unknown. This process never changes task timing, predictions or trajectories.'}
        self.sequence += 1
        return result

    def write(self):
        if not self.directory.is_dir():
            raise FileNotFoundError(self.directory)
        data = self.snapshot()
        destination = self.directory/'monitor'
        destination.mkdir(exist_ok=True)
        atomic_json(destination/'monitor.json', data)
        temporary = destination/'monitor.md.tmp'
        temporary.write_text(render(data), encoding='utf-8')
        temporary.replace(destination/'monitor.md')
        return data


def render(data):
    def cell(value):
        return str(value if value is not None else '—').replace('|', '\\|').replace('\n', ' ')
    def seconds(value):
        return '—' if value is None else str(round(value, 1))
    cost = data['known_cost_lower_bounds']
    lines = ['# Benchmark 实时监控', '',
             f"更新时间：{data['updated_at']}（运行期间每 {data['refresh_interval_seconds']:g} 秒刷新）", '',
             f"状态：**{cell(data['status'])}** · Baseline：**{cell(data['baseline'])}** · 题库：**{cell(data['dataset'])}** · 模型：`{cell(data['model'])}`", '',
             f"任务并发：{cell(data['configured_task_concurrency'])} · 单题工具并行：{cell(data['tool_concurrency_per_task'])}", '',
             '| 已结束 | 正常完成 | 失败／中断 | 正在运行 | 等待运行 |',
             '| ---: | ---: | ---: | ---: | ---: |',
             f"| {data['recorded_tasks']}/{data['selected_tasks']}（{data['progress_percent']:.1f}%） | {data['successful_tasks']} | {data['failed_tasks']} | {data['active_tasks_count']} | {data['queued_tasks']} |", '',
             '## 当前任务', '', '| 任务 | 阶段 | 墙钟已运行秒数 | 模型响应／请求步骤 | 科学／查询调用 | 检查点距今秒数 |',
             '| --- | --- | ---: | ---: | ---: | ---: |']
    if data.get('ablation'):
        lines[6:6] = ['消融设置：`'+cell(data['ablation'].get('variant'))+'`', '']
    if not data['active_state_known']:
        lines[8:8] = ['批次进程已退出；活动项是最后检查点记录，不表示任务仍在执行。', '']
    for task in data['active_tasks']:
        path = task['trace_path']
        label = f"[{cell(task['id'])}](../{path})" if path else cell(task['id'])
        metrics = task['metrics']
        phase = cell(task['phase'])+('（等待模型响应）' if task['pending_model_response'] else '')
        if task['detail_unavailable']:
            phase += '（检查点过大或暂不可读）'
        lines.append(f"| {label} | {phase} | {seconds(task['task_age_seconds'])} | {task['responses_recorded']}/{task['generation_steps']} | {cell(metrics.get('scientific_tool_calls'))}/{cell(metrics.get('discovery_tool_calls'))} | {seconds(task['last_checkpoint_age_seconds'])} |")
    if not data['active_tasks']:
        lines.append('| — | 暂无活动任务 | — | — | — | — |')
    lines += ['', '## 已知运行成本', '',
              f"输入 token：**{cost['input_tokens']:,}**；输出 token：**{cost['output_tokens']:,}**；工具调用：**{cost['tool_calls']:,}**（科学 {cost['scientific_tool_calls']:,}＋查询 {cost['discovery_tool_calls']:,}）。", '',
              f"已结束任务中有 {data['finished_tasks_with_incomplete_usage']} 题 token 用量不完整；活动任务仅统计最新检查点中已知的部分，不能作为最终总量。", '',
              '逐题时间、调用数及 token：[task_metrics.json](../task_metrics.json) · 原始进度：[progress.json](../progress.json) · 机器可读监控：[monitor.json](monitor.json)', '']
    if not data['checkpoint_consistent']:
        lines += ['检查点正在切换，等待同一实验指纹的进度与用量记录。', '']
    if data['score_stale']:
        lines += ['已有评分早于最新任务记录，等待重新评分。', '']
    if data['failures']:
        lines += ['## 失败记录（前 10 项）', '']
        lines += ['- `'+cell(row['id'])+'`：'+cell(row['failure_reason']) for row in data['failures'][:10]]
        lines.append('')
    if data['score_summary'] is not None:
        lines += ['## 离线评分', '', '```json', json.dumps(data['score_summary'], ensure_ascii=False, indent=2), '```', '']
    lines += ['正常完成只表示运行正常结束；工具规划与答案正确性以评分文件为准。监控只读已有检查点，不调用模型、不重算或改写任务计时；墙钟已运行时间仅供查看进展。历史重试开销见 predictions.json 的 attempt_history。', '']
    return '\n'.join(lines)


def start_monitor(directory, *, owner_pid=None, interval=10):
    """Reserve a single-writer lock before spawning; failures never stop actors."""
    folder = Path(directory).resolve()/'monitor'
    descriptor = None
    try:
        if not folder.parent.is_dir():
            raise FileNotFoundError(folder.parent)
        folder.mkdir(exist_ok=True)
        descriptor = os.open(folder/'.lock', os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _launch(folder, owner_pid, interval, descriptor=descriptor)
    except BlockingIOError:
        # A resumed run can start while the prior monitor is publishing its
        # final snapshot. Wait in a separate process, never in the actor path.
        try:
            previous = json.loads((folder/'monitor.json').read_text())
            if previous.get('status') in TERMINAL | {'runner_missing'} or alive(previous.get('owner_pid')) is False:
                return _launch(folder, owner_pid, interval, wait=True)
        except (OSError, ValueError):
            pass
        return None
    except OSError as error:
        print('Monitor unavailable: '+type(error).__name__, file=sys.stderr, flush=True)
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _launch(folder, owner_pid, interval, *, descriptor=None, wait=False):
    command = [sys.executable, '-m', 'baselines.common.monitor', '--directory', str(folder.parent),
               '--owner-pid', str(owner_pid or os.getpid()), '--interval', str(interval)]
    if descriptor is not None:
        command += ['--lock-fd', str(descriptor)]
    if wait:
        command.append('--wait-for-lock')
    try:
        with (folder/'monitor.log').open('a') as log:
            return subprocess.Popen(command, cwd=Path(__file__).resolve().parents[2],
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                    start_new_session=True,
                                    pass_fds=() if descriptor is None else (descriptor,))
    except OSError as error:
        print('Monitor unavailable: '+type(error).__name__, file=sys.stderr, flush=True)
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--owner-pid', type=int)
    parser.add_argument('--interval', type=float, default=10)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--lock-fd', type=int, help=argparse.SUPPRESS)
    parser.add_argument('--wait-for-lock', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error('--interval must be positive and finite')
    if args.owner_pid is not None and args.owner_pid <= 0:
        parser.error('--owner-pid must be positive')
    folder = args.directory.resolve()/'monitor'
    if not folder.parent.is_dir():
        parser.error('--directory must name an existing result directory')
    folder.mkdir(exist_ok=True)
    descriptor = args.lock_fd
    if descriptor is None:
        descriptor = os.open(folder/'.lock', os.O_CREAT | os.O_RDWR, 0o600)
        deadline = time.monotonic()+max(15, args.interval+1)
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not args.wait_for_lock or time.monotonic() >= deadline or not folder.parent.is_dir():
                    os.close(descriptor)
                    return
                try:
                    current = json.loads((folder/'monitor.json').read_text())
                    if current.get('status') not in TERMINAL | {'runner_missing'} and alive(current.get('owner_pid')) is True:
                        os.close(descriptor)
                        return
                except (OSError, ValueError):
                    pass
                time.sleep(.05)
    monitor = Monitor(args.directory, owner_pid=args.owner_pid, interval=args.interval)
    try:
        while True:
            if not monitor.directory.is_dir():
                return
            try:
                data = monitor.write()
                print(data['updated_at'], data['status'], f"{data['recorded_tasks']}/{data['selected_tasks']}", flush=True)
                draining = data['status'] == 'paused_infrastructure' and data['active_tasks_count'] > 0 and data['owner_alive'] is not False
                supervised = data['experiment_status'] is not None and data['experiment_status'] not in TERMINAL and data['owner_alive'] is not False
                if args.once or data['status'] == 'runner_missing' or data['status'] in TERMINAL and not draining and not supervised:
                    return
            except (OSError, ValueError, TypeError) as error:
                print('Monitor update failed: '+type(error).__name__, file=sys.stderr, flush=True)
                if args.once:
                    raise
            time.sleep(args.interval)
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    main()
