"""Bounded task processes; only the caller writes the batch checkpoint."""

import json
import multiprocessing
import os
from pathlib import Path
import signal
import tempfile
import time

from src.utils.io import atomic_json
from src.models.communication import infrastructure_failure


def _worker(function, payload, destination):
    # Keep terminal interrupts in the scheduler; it forwards one interrupt to
    # each actor so the actor can save its trace and stop its tool subprocess.
    if hasattr(os, "setsid"):
        os.setsid()
    signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        value = {"ok": True, "result": function(payload)}
    except KeyboardInterrupt:
        return
    except Exception as error:
        value = {"ok": False, "error": type(error).__name__ + ": " + str(error)[:1000]}
        if infrastructure_failure(error):
            value["infrastructure_failure"] = infrastructure_failure(error)
    atomic_json(destination, value)


def iter_tasks(jobs, function, concurrency, on_active=None, should_schedule=None):
    """Yield (job, result) in completion order without sharing model clients.

    Jobs are (unique task ID, pickleable payload). No unbounded future queue is
    created. Result files avoid pipe deadlocks for large scientific outputs.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    context = multiprocessing.get_context("spawn")
    remaining = iter(jobs)
    active = {}
    exhausted = False

    def notify():
        if on_active:
            on_active(list(active))

    with tempfile.TemporaryDirectory(prefix="scitoolflow-batch-") as directory:
        try:
            while active or not exhausted:
                while len(active) < concurrency and not exhausted:
                    if should_schedule is not None and not should_schedule():
                        exhausted = True
                        break
                    try:
                        task_id, payload = next(remaining)
                    except StopIteration:
                        exhausted = True
                        break
                    if task_id in active:
                        raise ValueError("Duplicate active task ID: " + task_id)
                    destination = Path(directory) / (
                        str(len(active)) + "-" + task_id + ".json"
                    )
                    process = context.Process(
                        target=_worker, args=(function, payload, destination)
                    )
                    process.start()
                    active[task_id] = (process, destination, payload)
                    notify()
                finished = [
                    key for key, (p, _, _) in active.items() if not p.is_alive()
                ]
                for task_id in finished:
                    process, destination, payload = active.pop(task_id)
                    process.join()
                    if destination.exists():
                        response = json.loads(destination.read_text())
                        destination.unlink()
                    else:
                        response = {
                            "ok": False,
                            "error": "Task worker exited without a result (exitcode="
                            + str(process.exitcode)
                            + ")",
                        }
                    notify()
                    yield task_id, response
                if active and not finished:
                    time.sleep(0.05)
        finally:
            # Ignore a second Ctrl-C while the first is being propagated.
            previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
            try:
                for process, _, _ in active.values():
                    if process.is_alive():
                        try:
                            os.kill(process.pid, signal.SIGINT)
                        except ProcessLookupError:
                            pass
                deadline = time.monotonic() + 5
                for process, _, _ in active.values():
                    process.join(timeout=max(0, deadline - time.monotonic()))
                    if process.is_alive():
                        process.terminate()
                for process, _, _ in active.values():
                    process.join(timeout=2)
                    if process.is_alive():
                        process.kill()
                        process.join()
                active.clear()
                notify()
            finally:
                signal.signal(signal.SIGINT, previous)
