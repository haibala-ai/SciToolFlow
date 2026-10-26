"""Concurrent scheduling, writable isolation and interrupted-worker cleanup."""

import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P))
from baselines.common.batch import iter_tasks


def isolated_job(payload):
    from src.utils.paths import work_root, artifacts_root

    root, task_id = payload
    os.environ["SCITOOLFLOW_WORK_DIR"] = str(Path(root) / task_id / "work")
    os.environ["SCITOOLFLOW_ARTIFACTS_DIR"] = str(Path(root) / task_id / "artifacts")
    work_root().mkdir(parents=True)
    artifacts_root().mkdir(parents=True)
    file = work_root() / "same_name.txt"
    file.write_text(task_id)
    start = time.monotonic()
    time.sleep(0.6)
    if task_id == "error":
        raise ValueError("expected task failure")
    return {
        "id": task_id,
        "pid": os.getpid(),
        "start": start,
        "end": time.monotonic(),
        "value": file.read_text(),
        "work": str(work_root()),
        "artifacts": str(artifacts_root()),
    }


def slow_job(path):
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        Path(path).write_text("interrupted")
        raise


class BatchTests(unittest.TestCase):
    def test_bounded_parallelism_and_distinct_writable_namespaces(self):
        activity = []
        with tempfile.TemporaryDirectory() as directory:
            jobs = [
                (task_id, (directory, task_id)) for task_id in ["A", "B", "error", "C"]
            ]
            result = dict(
                iter_tasks(
                    jobs, isolated_job, 2, lambda ids: activity.append(list(ids))
                )
            )
            self.assertEqual(set(result), {"A", "B", "error", "C"})
            self.assertFalse(result["error"]["ok"])
            self.assertIn("expected task failure", result["error"]["error"])
            a, b, c = [result[key]["result"] for key in ["A", "B", "C"]]
            self.assertLess(max(a["start"], b["start"]), min(a["end"], b["end"]))
            self.assertEqual(len({a["pid"], b["pid"], c["pid"]}), 3)
            self.assertEqual([a["value"], b["value"], c["value"]], ["A", "B", "C"])
            self.assertEqual(max(map(len, activity)), 2)
            self.assertEqual(activity[-1], [])
            self.assertNotEqual(a["work"], b["work"])
            self.assertNotEqual(a["artifacts"], b["artifacts"])

    def test_stopping_scheduler_interrupts_active_task_and_cleans_up(self):
        # The first task finishes while the second is still active. Closing the
        # consumer must not wait for the second task's 30-second timeout.
        with tempfile.TemporaryDirectory() as directory:
            started = time.monotonic()
            # Both workers need importable targets under spawn.
            jobs = [("first", (directory, "first")), ("slow", (directory, "slow"))]
            iterator = iter_tasks(jobs, cancellable_job, 2)
            next(iterator)
            iterator.close()
            self.assertLess(time.monotonic() - started, 10)
            self.assertEqual(
                (Path(directory) / "slow-interrupted.txt").read_text(), "interrupted"
            )
            self.assertFalse(multiprocessing.active_children())


def cancellable_job(payload):
    directory, task_id = payload
    if task_id == "slow":
        return slow_job(str(Path(directory) / "slow-interrupted.txt"))
    time.sleep(1)
    return {"id": task_id}


if __name__ == "__main__":
    unittest.main()
