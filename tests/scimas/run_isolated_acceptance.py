"""Drive the production runner with one fresh, information-bounded subagent per request.

This is an acceptance adapter, not a hosted API or a benchmark reference generator.
Only public role messages enter the mailbox. The external orchestrator supplies
actual gpt-6.1-terra replies; token usage remains unknown unless genuinely provided.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.utils.io import atomic_json
from baselines.react import runner
from baselines.scimas.task_graph import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["full", "mini"], required=True)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mailbox", type=Path, required=True)
    parser.add_argument("--max-model-requests", type=int, default=400)
    args = parser.parse_args()
    mailbox = args.mailbox.resolve()
    mailbox.mkdir(parents=True, exist_ok=True)
    if list(mailbox.iterdir()):
        raise ValueError("Use a fresh isolated mailbox")

    class MailboxClient:
        backend = "isolated-subagent"
        model = "gpt-6.1-terra"
        supports_response_schema = True

        def __init__(self, backend=None):
            self.sequence = 0

        def public_settings(self):
            return {
                "endpoint": "isolated-subagent-mailbox",
                "model": self.model,
                "sampling": {
                    "provider": "Codex collaboration",
                    "fresh_context_per_request": True,
                    "temperature": "not exposed",
                    "token_usage": "not exposed",
                },
            }

        def close(self):
            pass

        def request(
            self, messages, max_tokens=8192, timeout=None, response_schema=None
        ):
            self.sequence += 1
            folder = mailbox / ("%04d" % self.sequence)
            folder.mkdir()
            request = {
                "messages": messages,
                "max_output_tokens_requested": max_tokens,
                "response_schema": response_schema,
                "model": self.model,
            }
            identity = digest(request)
            atomic_json(folder / "request.json", dict(request, request_sha256=identity))
            print("[isolated request] " + str(folder / "request.json"), flush=True)
            deadline = time.monotonic() + (timeout or 600)
            while time.monotonic() < deadline:
                response_file = folder / "response.json"
                if response_file.exists():
                    response = json.loads(response_file.read_text())
                    if (
                        response.get("request_sha256") != identity
                        or response.get("model") != self.model
                    ):
                        raise ValueError("Foreign subagent reply")
                    if not isinstance(response.get("text"), str):
                        raise ValueError("Subagent response must contain JSON text")
                    # No synthetic token counts. The task-wide ledger records this actual
                    # generation request and its wall time, with unknown token usage.
                    response["usage"] = None
                    return response
                time.sleep(0.1)
            raise TimeoutError("Isolated subagent request deadline")

    def isolated_tasks(jobs, function, concurrency, on_active=None):
        if concurrency != 1:
            raise ValueError("Each acceptance driver owns one isolated task process")
        for task_id, payload in jobs:
            if on_active:
                on_active([task_id])
            try:
                value = {"ok": True, "result": function(payload)}
            except Exception as error:
                value = {"ok": False, "error": type(error).__name__ + ": " + str(error)}
            if on_active:
                on_active([])
            yield task_id, value

    original_hashes = runner.actor_file_hashes

    def hashes(root, dataset="full"):
        files = original_hashes(root, dataset)
        file = Path(__file__).resolve()
        files[str(file.relative_to(root))] = hashlib.sha256(
            file.read_bytes()
        ).hexdigest()
        return files

    runner.GenerationClient = MailboxClient
    runner.iter_tasks = isolated_tasks
    runner.actor_file_hashes = hashes
    sys.argv = [
        "cli.py",
        "run",
        "--baseline",
        "scimas",
        "--dataset",
        args.dataset,
        "--tasks",
        args.tasks,
        "--backend",
        "api",
        "--model",
        "gpt-6.1-terra",
        "--output",
        args.output,
        "--concurrency",
        "1",
        "--max-model-requests",
        str(args.max_model_requests),
        "--task-timeout",
        "3600",
        "--max-output-tokens",
        "8192",
    ]
    from cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
