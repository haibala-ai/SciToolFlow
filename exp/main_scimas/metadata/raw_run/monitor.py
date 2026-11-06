"""Read cached checkpoints only; never call a model or modify raw evidence."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
sys.path.insert(0, str(ROOT))
from src.utils.io import atomic_json

CACHE = {}
FAILURES = {}


def read(path):
    try:
        stat = path.stat()
        identity = (stat.st_mtime_ns, stat.st_size)
        if path not in CACHE or CACHE[path][0] != identity:
            CACHE[path] = (identity, json.loads(path.read_text()))
        return CACHE[path][1]
    except (OSError, ValueError):
        return CACHE.get(path, (None, {}))[1]


def age(value, now):
    try:
        return max(0, (now - datetime.fromisoformat(value)).total_seconds())
    except (TypeError, ValueError):
        return None


def alive(pid):
    if not pid:
        return None
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def snapshot(sequence):
    now = datetime.now(timezone.utc)
    experiment = read(RUN / "experiment.json")
    progress = read(RUN / "progress.json")
    rows = read(RUN / "task_metrics.json").get("tasks", [])
    done = {r["id"] for r in rows}
    active_ids = [i for i in progress.get("active_tasks", []) if i not in done]
    latest = {}
    for path in (RUN / "trajectories").glob("*/trajectory.json"):
        identifier = path.parent.name.rsplit("-", 1)[0]
        if identifier not in active_ids:
            continue
        try:
            if (
                identifier not in latest
                or path.stat().st_mtime_ns > latest[identifier].stat().st_mtime_ns
            ):
                latest[identifier] = path
        except OSError:
            pass
    active = []
    for identifier in active_ids:
        path = latest.get(identifier)
        trace = read(path) if path else {}
        models = [s for s in trace.get("steps", []) if "model" in s]
        last = models[-1] if models else {}
        pending = bool(
            last
            and last["model"].get("response") is None
            and not last["model"].get("error")
        )
        phase = last.get("role", "initializing")
        if trace.get("pending_calls") and not pending:
            phase = "tools"
        active.append(
            {
                "id": identifier,
                "status": trace.get("status", "initializing"),
                "phase": phase,
                "task_age_seconds": age(trace.get("started_at"), now),
                "last_checkpoint_age_seconds": (
                    max(0, now.timestamp() - path.stat().st_mtime) if path else None
                ),
                "generation_steps": len(models),
                "responses_recorded": sum(
                    s["model"].get("response") is not None for s in models
                ),
                "pending_model_response": pending,
                "metrics": trace.get("metrics", {}),
                "trace_path": str(path) if path else None,
            }
        )
    known = rows + [r["metrics"] for r in active]
    lower = lambda key: sum(r.get(key) or 0 for r in known)
    incomplete = sum(not r.get("token_usage_complete", False) for r in rows)
    status = experiment.get("status", "starting")
    supervisor_alive = alive(experiment.get("supervisor_pid"))
    if (
        status not in {"finished", "failed", "interrupted"}
        and supervisor_alive is False
    ):
        status = "supervisor_missing"
    failures = []
    for row in rows:
        if row.get("completed"):
            continue
        key = (row["id"], row.get("trace_path"))
        if key not in FAILURES:
            trace = read(Path(row["trace_path"])) if row.get("trace_path") else {}
            FAILURES[key] = {
                "id": row["id"],
                "status": row["status"],
                "failure_reason": trace.get("failure_reason", "See generating.log"),
                "trace_path": row.get("trace_path"),
            }
        failures.append(FAILURES[key])
    active_paths = set(latest.values())
    for path in list(CACHE):
        if path.name == "trajectory.json" and path not in active_paths:
            del CACHE[path]
    return {
        "schema_version": "scimas.live_monitor.v1",
        "sequence": sequence,
        "updated_at": now.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(),
        "status": status,
        "dataset": "mini",
        "baseline": "scimas",
        "model": "deepseek-flash",
        "selected_tasks": 200,
        "recorded_tasks": len(rows),
        "successful_tasks": sum(bool(r.get("completed")) for r in rows),
        "failed_tasks": len(failures),
        "active_tasks_count": len(active),
        "queued_tasks": max(0, 200 - len(rows) - len(active)),
        "progress_percent": round(len(rows) / 2, 2),
        "experiment_age_seconds": age(experiment.get("started_at"), now),
        "supervisor_alive": supervisor_alive,
        "configured_task_concurrency": 2,
        "tool_concurrency_per_task": 4,
        "active_tasks": active,
        "failures": failures,
        "known_cost_lower_bounds": {
            "input_tokens": lower("observed_input_tokens"),
            "output_tokens": lower("observed_output_tokens"),
            "tool_calls": lower("tool_calls"),
            "scientific_tool_calls": lower("scientific_tool_calls"),
            "discovery_tool_calls": lower("discovery_tool_calls"),
            "model_requests_recorded": lower("model_requests"),
        },
        "finished_tasks_with_incomplete_usage": incomplete,
        "pending_model_responses": sum(r["pending_model_response"] for r in active),
        "score_summary": read(RUN / "scores.json").get("summary"),
        "note": "Running-task costs are latest checkpoint lower bounds; never interpret them as final totals. No model calls or raw trace writes are performed by this monitor.",
    }


def render(data):
    cost = data["known_cost_lower_bounds"]
    lines = [
        "# SciMas · Mini-200 实时进度",
        "",
        "更新时间：" + data["updated_at"] + "（每 10 秒刷新）",
        "",
        "状态：**"
        + data["status"]
        + "** · 模型：`deepseek-flash` · 任务并发：**2** · 单题工具并行：4",
        "",
        "| 已结束 | 成功完成 | 失败／中断 | 正在运行 | 等待运行 |",
        "| ---: | ---: | ---: | ---: | ---: |",
        f"| {data['recorded_tasks']}/200（{data['progress_percent']}%） | {data['successful_tasks']} | {data['failed_tasks']} | {data['active_tasks_count']} | {data['queued_tasks']} |",
        "",
        "## 当前任务",
        "",
        "| 任务 | 阶段 | 已运行秒数 | 模型响应／请求步骤 | 科学／查询调用 | 检查点距今秒数 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for task in data["active_tasks"]:
        m = task["metrics"]
        path = (
            Path(task["trace_path"]).relative_to(RUN).as_posix()
            if task["trace_path"]
            else None
        )
        label = "[" + task["id"] + "](" + path + ")" if path else task["id"]
        value = lambda k: "—" if task[k] is None else str(round(task[k], 1))
        wait = "（等待响应）" if task["pending_model_response"] else ""
        lines.append(
            f"| {label} | {task['phase']}{wait} | {value('task_age_seconds')} | {task['responses_recorded']}/{task['generation_steps']} | {m.get('scientific_tool_calls',0)}/{m.get('discovery_tool_calls',0)} | {value('last_checkpoint_age_seconds')} |"
        )
    if not data["active_tasks"]:
        lines.append("| — | 暂无活动任务 | — | — | — | — |")
    lines += [
        "",
        "## 已知运行成本",
        "",
        f"输入 token：**{cost['input_tokens']:,}**；输出 token：**{cost['output_tokens']:,}**；工具调用：**{cost['tool_calls']}**（科学 {cost['scientific_tool_calls']}＋查询 {cost['discovery_tool_calls']}）。",
        "",
        f"已结束任务中有 {data['finished_tasks_with_incomplete_usage']} 题用量不完整；当前等待模型响应 {data['pending_model_responses']} 个。上述成本包含已结束任务和活动任务最新检查点的已知小计，不能作为最终总量。",
        "",
        "完整逐题时间、调用数及输入／输出 token：[task_metrics.json](task_metrics.json)。机器可读实时状态：[monitor.json](monitor.json)。",
        "",
    ]
    if data["failures"]:
        lines += ["## 失败记录（前 10 项）", ""]
        for failure in data["failures"][:10]:
            lines += [
                "- `"
                + failure["id"]
                + "`："
                + str(failure["failure_reason"]).replace("\n", " ")[:600]
            ]
        lines.append("")
    if data["score_summary"] is not None:
        lines += [
            "## 离线评分",
            "",
            "```json",
            json.dumps(data["score_summary"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    lines += [
        "生成全部结束后自动离线评分；成功完成表示运行协议完成，科学答案与工具规划结果以评分文件为准。监控只读取已有检查点，不调用 LLM，不改写轨迹或任务计时。",
        "",
    ]
    return "\n".join(lines)


def write_snapshot(sequence):
    data = snapshot(sequence)
    atomic_json(RUN / "monitor.json", data)
    temp = RUN / "monitor.md.tmp"
    temp.write_text(render(data), encoding="utf-8")
    temp.replace(RUN / "monitor.md")
    return data


if __name__ == "__main__":
    sequence = 0
    while True:
        try:
            data = write_snapshot(sequence)
            print(
                data["updated_at"],
                data["status"],
                str(data["recorded_tasks"]) + "/200",
                "active=" + str(data["active_tasks_count"]),
                "failed=" + str(data["failed_tasks"]),
                flush=True,
            )
            sequence += 1
            if data["status"] in {
                "finished",
                "failed",
                "interrupted",
                "supervisor_missing",
            }:
                break
        except Exception as error:
            print("Monitor update failed: " + type(error).__name__, flush=True)
        time.sleep(10)
