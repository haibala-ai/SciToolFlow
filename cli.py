"""SciToolFlow command line; offline evaluation imports no scientific implementation."""

import argparse
import json
import math
from pathlib import Path
from src.utils.paths import project_root
from tasks.datasets import DATASETS, load_dataset


def main():
    root = project_root()
    react = json.loads((root / "baselines/react/config.json").read_text())
    parser = argparse.ArgumentParser(prog="scitoolflow")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser(
        "task", help="View a public benchmark task, or list tasks by domain"
    )
    p.add_argument("id", nargs="?")
    p.add_argument("--dataset", choices=DATASETS, default="full")
    p.add_argument(
        "--domain", choices=["Biology", "Chemical", "Material", "MachineLearning"]
    )
    sub.add_parser(
        "validate", help="Verify data, code, contracts and reference integrity"
    )
    p = sub.add_parser("describe", help="Query public DescribeTools contracts")
    p.add_argument("tools", nargs="+")
    p = sub.add_parser("call", help="Execute a registered tool")
    p.add_argument("tool")
    p.add_argument("--arguments", default="{}")
    p.add_argument("--files", nargs="*", default=[])
    p.add_argument("--timeout", type=float, default=180)
    p = sub.add_parser("run", help="Run a baseline using only public tasks")
    p.add_argument("--baseline", choices=["react", "scitoolagent"], default="react")
    p.add_argument("--dataset", choices=DATASETS, default="full")
    p.add_argument("--tasks", default="all")
    p.add_argument("--output")
    p.add_argument("--backend", choices=["vllm", "local", "api"], default="vllm")
    p.add_argument("--model")
    p.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Independent task processes (default: 1)",
    )
    p.add_argument("--resume", action="store_true")
    p.add_argument("--retry-failed", action="store_true")
    p.add_argument(
        "--max-steps",
        type=int,
        default=react["max_steps"],
        help="Optional experimental decision cap; default unlimited",
    )
    p.add_argument(
        "--max-model-requests",
        type=int,
        default=react["max_model_requests"],
        help="Task-wide generation request limit across all baseline roles",
    )
    p.add_argument("--max-calls", type=int)
    p.add_argument("--max-actions", type=int, default=react["max_actions"])
    p.add_argument(
        "--max-protocol-errors", type=int, default=react["max_protocol_errors"]
    )
    p.add_argument(
        "--max-failures-per-action", type=int, default=react["max_failures_per_action"]
    )
    p.add_argument(
        "--max-identical-tool-steps",
        type=int,
        default=react["max_identical_tool_steps"],
    )
    p.add_argument(
        "--answer-schema-guard",
        action=argparse.BooleanOptionalAction,
        default=react["answer_schema_guard"],
        help="Use supported structured decoding after an invalid final-answer format",
    )
    p.add_argument(
        "--protocol-schema-guard",
        action=argparse.BooleanOptionalAction,
        default=react.get("protocol_schema_guard", True),
        help="Constrain public decision syntax and catalogue names from the first request",
    )
    p.add_argument(
        "--max-discovery-calls", type=int, default=react["max_discovery_calls"]
    )
    p.add_argument("--max-think-steps", type=int, default=react["max_think_steps"])
    p.add_argument(
        "--max-consecutive-thinks", type=int, default=react["max_consecutive_thinks"]
    )
    p.add_argument("--max-input-tokens", type=int, default=react["max_input_tokens"])
    p.add_argument("--max-context-chars", type=int, default=react["max_context_chars"])
    p.add_argument("--max-output-tokens", type=int, default=react["max_output_tokens"])
    p.add_argument("--task-timeout", type=float, default=react["task_timeout_seconds"])
    p.add_argument("--tool-timeout", type=float, default=react["tool_timeout_seconds"])
    p.add_argument(
        "--enable-model-thinking",
        action="store_true",
        help="Enable backend-native reasoning separately from explicit think steps",
    )
    p = sub.add_parser(
        "score", help="Score the selected dataset or an explicit selection within it"
    )
    p.add_argument("--predictions", required=True, type=Path)
    p.add_argument("--output", type=Path, default=Path("scores.json"))
    p.add_argument("--tasks", default="all")
    p.add_argument("--dataset", choices=DATASETS, default="full")
    args = parser.parse_args()
    if args.command == "task":
        rows = load_dataset(args.dataset, root).questions
        if args.domain:
            rows = [row for row in rows if row["domain"] == args.domain]
        if args.id:
            selected = next((row for row in rows if row["id"] == args.id), None)
            if selected is None:
                parser.error(
                    "Unknown task ID or task outside selected domain: " + args.id
                )
            print(json.dumps(selected, ensure_ascii=False, indent=2))
        else:
            print(
                json.dumps(
                    [
                        {
                            "id": row["id"],
                            "domain": row["domain"],
                            "question_preview": row["question"][:160],
                        }
                        for row in rows
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
    elif args.command == "validate":
        from evaluation.integrity.package import validate_package

        print(json.dumps(validate_package(root), ensure_ascii=False, indent=2))
    elif args.command == "describe":
        from tools.catalog import ToolCatalog

        print(
            json.dumps(ToolCatalog().describe(args.tools), ensure_ascii=False, indent=2)
        )
    elif args.command == "call":
        from tools import execute

        print(
            json.dumps(
                execute(
                    args.tool, json.loads(args.arguments), args.files, args.timeout
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "run":
        if any(
            not math.isfinite(getattr(args, k)) or getattr(args, k) <= 0
            for k in [
                "concurrency",
                "max_model_requests",
                "max_actions",
                "max_protocol_errors",
                "max_identical_tool_steps",
                "max_input_tokens",
                "max_context_chars",
                "max_output_tokens",
                "task_timeout",
                "tool_timeout",
            ]
        ):
            parser.error("Limits must be positive")
        if args.max_failures_per_action < 0:
            parser.error(
                "max-failures-per-action must be nonnegative; 0 disables the cumulative limit"
            )
        for name in [
            "max_steps",
            "max_calls",
            "max_discovery_calls",
            "max_think_steps",
            "max_consecutive_thinks",
        ]:
            value = getattr(args, name)
            minimum = 0 if name in {"max_think_steps", "max_discovery_calls"} else 1
            if value is not None and value < minimum:
                parser.error(name.replace("_", "-") + " is outside its allowed range")
        from baselines.react.runner import run_batch

        run_batch(args)
    elif args.command == "score":
        from evaluation.runner import evaluate_package

        selection = (
            None
            if args.tasks == "all"
            else [x.strip() for x in args.tasks.split(",") if x.strip()]
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        result = evaluate_package(
            root,
            args.predictions,
            args.output,
            task_ids=selection,
            dataset=args.dataset,
        )
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
