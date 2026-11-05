"""Lightweight step identity; detailed case files are exported offline."""

from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import argparse

from src.utils.io import atomic_json


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def append_step(trace, step, resources):
    step.update(
        step_id="s%06d" % (len(trace["steps"]) + 1),
        recorded_at=timestamp(),
        recorded_seconds=max(0, resources.clock() - resources.started),
    )
    trace["steps"].append(step)
    return step


def persist_request(trace_path, step):
    path = Path(trace_path).parent / "requests" / (step["step_id"] + ".json")
    step["request_path"] = str(path)
    atomic_json(path, step, indent=None)


def write_report(trace, path, source):
    """Render recorded facts only; previews point to full, unmodified JSON."""
    folder = Path(path).parent

    def preview(value, limit=1600):
        text = json.dumps(value, ensure_ascii=False, indent=2)
        if len(text) > limit:
            text = text[:limit] + "\n…（预览截断；完整内容见 JSON）"
        return text

    lines = [
        "# " + trace["task_id"] + " · SciMas 运行记录",
        "",
        "- 状态：`" + trace["status"] + "`",
        "- 模型：`" + str(trace["model"]) + "`",
        "- 完整原始记录：[trajectory.json]("
        + Path(os.path.relpath(source, folder)).as_posix()
        + ")",
        "- 步骤按主循环记录顺序排列；并行调用的实际起止时间见调用记录。",
        "",
        "## 问题",
        "",
        trace.get("task", {}).get("question", ""),
        "",
        "## 运行统计",
        "",
        "````json",
        preview(trace.get("metrics")),
        "````",
        "",
    ]
    if trace.get("failure_reason"):
        lines += ["## 失败信息", "", "````text", trace["failure_reason"], "````", ""]
    lines += ["## 逐步轨迹", ""]
    for step in trace["steps"]:
        heading = "### " + step["step_id"] + " · " + step["type"]
        if step.get("role"):
            heading += " · " + step["role"]
        lines += [heading, "", "记录时间：" + step["recorded_at"], ""]
        if step.get("request_path"):
            relative = Path(step["request_path"]).relative_to(folder)
            lines += ["[完整模型输入、响应和校验记录](" + relative.as_posix() + ")", ""]
        model = step.get("model", {})
        if model:
            detail = {
                k: step[k] for k in ("decision", "validation_errors") if k in step
            }
            detail.update(
                {
                    k: model[k]
                    for k in ("error", "usage", "duration_seconds")
                    if k in model
                }
            )
            if not detail.get("decision") and model.get("response"):
                detail["response"] = model["response"]
        else:
            detail = step
        lines += ["````json", preview(detail), "````", ""]
        for call in step.get("calls", []):
            for name in ("request_path", "response_path"):
                if call.get(name):
                    relative = Path(call[name]).relative_to(folder)
                    lines += ["[" + name + "](" + relative.as_posix() + ")", ""]
    lines += [
        "## 状态索引",
        "",
        "`trajectory.json` 的 planning、retrievals、graphs、reviews、repairs、"
        "results、pruned、experiences 和 resource_usage 保存规划、检索、图版本、"
        "审查、修复、采纳结果、淘汰依据、任务内经验和逐请求用量。",
        "",
    ]
    destination = Path(path)
    temporary = destination.with_suffix(".md.tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    temporary.replace(destination)


def export_case(source, output=None):
    """Read an existing trace without rewriting it or invoking tools/models."""
    source = Path(source).resolve()
    raw = source.read_bytes()
    trace = json.loads(raw)
    if trace.get("baseline") != "scimas":
        raise ValueError("Expected a SciMas trajectory")
    if "task" not in trace:
        # Old traces already contain public task inputs inside request messages.
        # Recover only those recorded values, never infer missing scientific data.
        for step in trace["steps"]:
            for message in step.get("model", {}).get("messages", []):
                if message.get("role") != "user":
                    continue
                try:
                    payload = json.loads(message["content"])
                except (ValueError, TypeError):
                    continue
                if not isinstance(payload, dict):
                    continue
                task = payload.get("task") or payload.get("context", {}).get("task")
                if isinstance(task, dict) and task.get("id") == trace["task_id"]:
                    trace["task"] = task
                    break
            if "task" in trace:
                break
    folder = Path(output).resolve() if output else source.parent / "analysis"
    if folder == source.parent:
        raise ValueError("Use a separate analysis directory to preserve raw artifacts")
    folder.mkdir(parents=True, exist_ok=True)
    for index, step in enumerate(trace["steps"], 1):
        step.setdefault("step_id", "s%06d" % index)
        step.setdefault("recorded_at", "未记录（历史轨迹）")
        if step.get("model"):
            persist_request(folder / "trajectory.json", step)
        for call in step.get("calls", []):
            directory = folder / "calls" / call["observation_id"]
            request_path = directory / "request.json"
            response_path = directory / "response.json"
            atomic_json(
                request_path,
                {
                    k: call[k]
                    for k in (
                        "tool",
                        "arguments",
                        "node",
                        "node_sha256",
                        "files",
                        "timeout_seconds",
                        "started_seconds",
                        "directory",
                    )
                    if k in call
                },
                indent=None,
            )
            response = dict(call.get("dispatcher_metadata", {}))
            response.update(
                status=call.get("dispatcher_status", call["status"]),
                output=call["output"],
            )
            for key in ("error", "error_type"):
                if key in call:
                    response[key] = call[key]
            atomic_json(response_path, response, indent=None)
            call.update(
                request_path=str(request_path), response_path=str(response_path)
            )
    report = folder / "trajectory.md"
    write_report(trace, report, source)
    manifest = {
        "source": str(source),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "report": str(report),
        "steps": len(trace["steps"]),
        "note": "Offline export only; missing historical fields are not inferred.",
    }
    atomic_json(folder / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            export_case(args.trajectory, args.output), ensure_ascii=False, indent=2
        )
    )
