"""Offline identical-evidence comparison; does not generate or evaluate answers."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import statistics
import tempfile
import time
from baselines.scimas.context import (
    encode_payload,
    ordered_context,
    request_diagnostics,
)
from baselines.scimas.context import role_messages, request_payload
from baselines.scimas.knowledge import ToolKnowledge
from src.utils.io import atomic_json


def optimize(messages):
    result = deepcopy(messages)
    body = json.loads(result[-1]["content"])
    if "context" in body:
        result = role_messages(
            messages[0]["content"],
            body["context"],
            body["response_schema"],
            body["format_feedback"],
        )
        assert request_payload(result) == body
        return result
    elif "task" in body and "stage" in body:
        body = {
            k: body[k]
            for k in (
                "task",
                "public_assets",
                "stage",
                "response_schema",
                "instructions",
                "format_feedback",
            )
        }
    result[-1]["content"] = encode_payload(body)
    assert json.loads(result[-1]["content"]) == json.loads(messages[-1]["content"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectories", nargs="+", type=Path, required=True)
    parser.add_argument("--tokenizer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    rows = []
    for path in args.trajectories:
        trace = json.loads(path.read_text())
        previous = {"before": {}, "after": {}}
        for step in trace["steps"]:
            if not step.get("model", {}).get("messages"):
                continue
            role = step["role"]
            before = step["model"]["messages"]
            after = optimize(before)
            item = {"task": trace["task_id"], "role": role}
            for name, messages in [("before", before), ("after", after)]:
                diag = request_diagnostics(messages, previous[name].get(role))
                item[name] = {
                    **diag,
                    "content_tokens": sum(
                        len(
                            tokenizer.encode(m["content"], add_special_tokens=False).ids
                        )
                        for m in messages
                    ),
                }
                previous[name][role] = messages
            rows.append(item)
    totals = {
        name: {
            k: sum(r[name][k] for r in rows)
            for k in ("input_chars", "same_role_prefix_chars", "content_tokens")
        }
        for name in ("before", "after")
    }
    kg = ToolKnowledge()
    names = ["MatrixMultiply", "MatrixInverse", "MatrixSVD"]

    def retrieval(cold):
        if cold:
            kg._connection_cache.clear()
        start = time.perf_counter()
        value = [
            kg.connections(n, d) for n in names for d in ("predecessors", "successors")
        ]
        return time.perf_counter() - start, value

    cold, warm = [], []
    for _ in range(5):
        a, expected = retrieval(True)
        b, actual = retrieval(False)
        assert actual == expected
        cold.append(a)
        warm.append(b)
    trace = json.loads(args.trajectories[-1].read_text())
    io = {}
    with tempfile.TemporaryDirectory() as folder:
        for label, indent in [("pretty", 2), ("compact", None)]:
            elapsed = []
            path = Path(folder) / "trajectory.json"
            for _ in range(3):
                start = time.perf_counter()
                atomic_json(path, trace, indent=indent)
                elapsed.append(time.perf_counter() - start)
                assert json.loads(path.read_text()) == trace
            io[label] = {
                "bytes": path.stat().st_size,
                "median_seconds": statistics.median(elapsed),
            }
    report = {
        "comparison": "same historical messages; JSON values unchanged; offline only",
        "requests": len(rows),
        "totals": totals,
        "input_content_token_reduction_fraction": 1
        - totals["after"]["content_tokens"] / totals["before"]["content_tokens"],
        "tokenizer": str(args.tokenizer),
        "token_scope": "Qwen tokenizer over message content, excluding chat-template overhead; not Terra/provider billing",
        "cache_scope": "common prefix characters with preceding request of the same role; not cache hits",
        "connections": {
            "cold_median_seconds": statistics.median(cold),
            "warm_median_seconds": statistics.median(warm),
            "outputs_equal": True,
        },
        "trace_checkpoint": io,
        "requests_detail": rows,
    }
    atomic_json(args.output, report)
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "requests_detail"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
