"""Run either baseline and deterministic workflow.v1 scoring."""

import argparse
from datetime import datetime, timezone
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.utils.io import atomic_json
from src.models.client import GenerationClient
from src.utils.paths import load_environment
from tasks.datasets import DATASETS, DEFAULT_DATASET, load_dataset
from baselines.common.monitor import start_monitor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tasks", default="all")
    parser.add_argument("--dataset", choices=DATASETS, default=DEFAULT_DATASET)
    parser.add_argument(
        "--baseline", choices=["react", "scitoolagent", "scimas"], default="react"
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--backend", choices=["api", "vllm", "local"], default="vllm")
    parser.add_argument("--model")
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("concurrency must be positive")
    dataset = load_dataset(args.dataset, ROOT)
    selected = dataset.select(args.tasks)
    load_environment()
    client = GenerationClient(args.backend)
    if args.model:
        client.model = args.model
    if not client.model:
        parser.error("Specify --model or SCITOOLFLOW_API_MODEL for the API actor")
    provider = client.public_settings()
    model = client.model
    client.close()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    status_file = output / "experiment.json"
    if status_file.exists() and not args.resume:
        parser.error("Experiment exists; choose another output or --resume")
    if status_file.exists():
        previous = json.loads(status_file.read_text())
        if previous.get("dataset", "full") != args.dataset:
            parser.error("Cannot resume an experiment from a different dataset")
    started = datetime.now(timezone.utc).isoformat()
    state = {
        "started_at": started,
        "supervisor_pid": os.getpid(),
        "tasks": args.tasks,
        "dataset": args.dataset,
        "denominator": len(selected),
        "model": model,
        "baseline": args.baseline,
        "concurrency": args.concurrency,
        "backend": args.backend,
        "provider": provider,
        "stages": [],
        "status": "waiting_for_model",
        "output_dir": str(output),
    }
    atomic_json(status_file, state)
    start_monitor(output)

    def wait_for_model(backend):
        if backend != "vllm":
            return
        import os
        from urllib.parse import urlparse

        base = os.getenv("SCITOOLFLOW_VLLM_BASE", "http://127.0.0.1:8016/v1").rstrip(
            "/"
        )
        if urlparse(base).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("vLLM must use a loopback service")
        url = base.removesuffix("/v1") + "/health"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        deadline = time.monotonic() + 900
        while True:
            try:
                with opener.open(url, timeout=3) as response:
                    if response.status == 200:
                        return
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("Model readiness timed out")
            time.sleep(3)

    try:
        wait_for_model(args.backend)
    except (ValueError, TimeoutError) as error:
        state.update(status="failed", failure_reason=str(error))
        atomic_json(status_file, state)
        return 1

    def stage(name, arguments):
        command = [sys.executable, str(ROOT / "cli.py"), *arguments]
        state["status"] = name
        record = {
            "stage": name,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "command": command,
        }
        state["stages"].append(record)
        atomic_json(status_file, state)
        print(f'[{record["started_at"]}] {name}', flush=True)
        with (output / (name + ".log")).open("a", buffering=1) as log:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            try:
                for line in process.stdout:
                    log.write(line)
                    print(line, end="", flush=True)
            except KeyboardInterrupt:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                record.update(
                    returncode=process.returncode,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                state.update(
                    status="interrupted",
                    stopped_at=datetime.now(timezone.utc).isoformat(),
                )
                atomic_json(status_file, state)
                raise
            process.stdout.close()
            returncode = process.wait()
        record.update(
            returncode=returncode,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        atomic_json(status_file, state)
        return returncode

    predictions = output / "predictions.json"
    scores = output / "scores.json"
    run = [
        "run",
        "--dataset",
        args.dataset,
        "--baseline",
        args.baseline,
        "--tasks",
        args.tasks,
        "--output",
        str(predictions),
        "--concurrency",
        str(args.concurrency),
        "--backend",
        args.backend,
        "--model",
        model,
    ]
    if args.resume:
        run.append("--resume")
    run_code = stage(args.baseline, run)
    if run_code:
        state.update(
            status="failed",
            failure_reason="Actor stage failed; inspect its log before scoring or retrying.",
        )
        atomic_json(status_file, state)
        return 1
    # Individual task failures still receive scores over the requested denominator.
    if not predictions.exists():
        atomic_json(predictions, {"predictions": []})
    score_code = stage(
        "score",
        [
            "score",
            "--dataset",
            args.dataset,
            "--tasks",
            args.tasks,
            "--predictions",
            str(predictions),
            "--output",
            str(scores),
        ],
    )
    rows = json.loads(predictions.read_text()).get("predictions", [])
    state.update(
        status=(
            "finished" if not any([run_code, score_code]) else "finished_with_errors"
        ),
        finished_at=datetime.now(timezone.utc).isoformat(),
        recorded_predictions=len(rows),
        completed_tasks=sum(bool(row.get("completed")) for row in rows),
    )
    atomic_json(status_file, state)
    print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)
    return int(any([run_code, score_code]))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
