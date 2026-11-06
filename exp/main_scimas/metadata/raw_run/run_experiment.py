"""One persistent Mini-200 generation and offline scoring experiment."""

from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[1]
sys.path.insert(0, str(ROOT))
from src.utils.io import atomic_json
from src.utils.paths import load_environment
from src.models.client import GenerationClient


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    resume = sys.argv[1:] == ["--resume"]
    if sys.argv[1:] and not resume:
        raise ValueError("Only --resume is supported")
    config = json.loads((RUN / "launch.json").read_text())
    if (RUN / "experiment.json").exists() and not resume:
        raise ValueError("Experiment already exists; use --resume")
    load_environment()
    client = GenerationClient("api")
    provider = client.public_settings()
    if (
        client.model != config["model"]
        or provider["endpoint"] != "https://api.deepseek.com"
        or provider["trust_env"]
    ):
        raise ValueError("Expected the configured official direct DeepSeek client")
    client.close()
    previous = json.loads((RUN / "experiment.json").read_text()) if resume else {}
    state = {
        **previous,
        "status": "starting",
        "started_at": previous.get("started_at", now()),
        "updated_at": now(),
        "supervisor_pid": os.getpid(),
        "dataset": "mini",
        "selected_tasks": 200,
        "baseline": "scimas",
        "model": config["model"],
        "concurrency": 2,
        "provider": provider,
        "configuration": config,
        "stages": previous.get("stages", []),
    }
    for key in ("finished_at", "failure_reason", "score_summary"):
        state.pop(key, None)

    def save():
        state["updated_at"] = now()
        atomic_json(RUN / "experiment.json", state)

    def stage(name, arguments):
        command = [sys.executable, str(ROOT / "cli.py"), *arguments]
        state["status"] = name
        record = {"stage": name, "command": command, "started_at": now()}
        state["stages"].append(record)
        save()
        print("[" + now() + "] " + name, flush=True)
        with (RUN / (name + ".log")).open("a", buffering=1) as log:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            record["pid"] = process.pid
            save()
            try:
                for line in process.stdout:
                    log.write(line)
                    print(line, end="", flush=True)
                code = process.wait()
            except BaseException:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                record.update(returncode=process.returncode, finished_at=now())
                save()
                raise
            finally:
                process.stdout.close()
        record.update(returncode=code, finished_at=now())
        save()
        if code:
            raise RuntimeError(name + " exited with code " + str(code))

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    save()
    try:
        args = [
            "run",
            "--baseline",
            "scimas",
            "--dataset",
            "mini",
            "--tasks",
            "all",
            "--backend",
            "api",
            "--model",
            config["model"],
            "--concurrency",
            "2",
            "--max-context-chars",
            str(config["max_context_chars"]),
            "--max-output-tokens",
            str(config["max_output_tokens"]),
            "--max-model-requests",
            str(config["max_model_requests"]),
            "--task-timeout",
            str(config["task_timeout"]),
            "--output",
            str(RUN / "predictions.json"),
        ]
        if resume:
            args.append("--resume")
        stage("generating", args)
        metrics = json.loads((RUN / "task_metrics.json").read_text())["tasks"]
        if len(metrics) != 200:
            raise RuntimeError(
                "Generation returned before all 200 task results were recorded"
            )
        stage(
            "scoring",
            [
                "score",
                "--dataset",
                "mini",
                "--tasks",
                "all",
                "--predictions",
                str(RUN / "predictions.json"),
                "--output",
                str(RUN / "scores.json"),
            ],
        )
        state.update(
            status="finished",
            finished_at=now(),
            recorded_tasks=len(metrics),
            successful_tasks=sum(bool(r["completed"]) for r in metrics),
            score_summary=json.loads((RUN / "scores.json").read_text())["summary"],
        )
    except KeyboardInterrupt:
        state.update(status="interrupted", finished_at=now())
    except Exception as error:
        state.update(
            status="failed",
            finished_at=now(),
            failure_reason=type(error).__name__ + ": " + str(error),
        )
    finally:
        save()
    print(json.dumps(state, ensure_ascii=False, indent=2), flush=True)
    return 0 if state["status"] == "finished" else 1


if __name__ == "__main__":
    with (RUN / "supervisor.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(
                "This experiment is already running; refusing duplicate generation"
            )
        try:
            code = main()
        except (Exception, KeyboardInterrupt) as error:
            state = (
                json.loads((RUN / "experiment.json").read_text())
                if (RUN / "experiment.json").exists()
                else {}
            )
            state.update(
                status=(
                    "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
                ),
                supervisor_pid=os.getpid(),
                updated_at=now(),
                failure_reason=type(error).__name__ + ": " + str(error),
            )
            atomic_json(RUN / "experiment.json", state)
            print(state["failure_reason"], flush=True)
            code = 1
        raise SystemExit(code)
