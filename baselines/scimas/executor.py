"""Bounded concurrent calls, isolated directories, and cooperative worker cancellation."""

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextvars import copy_context
from pathlib import Path
from threading import Event
import time
from src.utils.paths import CALL_DIRECTORIES
from tools.runtime.context import CALL_CANCEL


class Executor:
    def __init__(self, invoke, folder, concurrency=4):
        self.invoke, self.folder = invoke, Path(folder)
        self.pool = ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="scimas-tool"
        )
        self.running, self.serial = {}, 0
        self.concurrency = concurrency

    def can_submit(self, parallel):
        # Unknown/shared-state tools run exclusively. Reviewed process-isolated tools
        # can overlap. This does not assert thread safety for arbitrary tool libraries.
        return len(self.running) < self.concurrency and (
            not self.running
            or parallel
            and all(r["parallel"] for r in self.running.values())
        )

    def submit(self, node, identity, arguments, *, parallel, files, timeout):
        if not self.can_submit(parallel):
            raise ValueError("Resource isolation conflict")
        self.serial += 1
        directory = self.folder / ("call_%04d" % self.serial)
        for leaf in ("work", "artifacts"):
            (directory / leaf).mkdir(parents=True, exist_ok=False)
        cancel = Event()
        record = {
            "node": node["id"],
            "tool": node["tool"],
            "node_sha256": identity,
            "arguments": arguments,
            "files": list(files),
            "timeout_seconds": timeout,
            "parallel": parallel,
            "cancel": cancel,
            "started": time.monotonic(),
            "directory": str(directory),
            "stale": False,
        }

        def call():
            token = CALL_DIRECTORIES.set(
                {k: str(directory / k) for k in ("work", "artifacts")}
            )
            cancellation = CALL_CANCEL.set(cancel)
            try:
                return self.invoke(
                    node["tool"], arguments, files=files, timeout=timeout
                )
            except Exception as error:
                return {
                    "status": "error",
                    "output": None,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            finally:
                record["finished"] = time.monotonic()
                CALL_CANCEL.reset(cancellation)
                CALL_DIRECTORIES.reset(token)

        future = self.pool.submit(copy_context().run, call)
        self.running[future] = record
        return record

    def completed(self, timeout=0.1):
        if not self.running:
            return []
        done, _ = wait(self.running, timeout=timeout, return_when=FIRST_COMPLETED)
        rows = []
        for future in sorted(
            done, key=lambda f: self.running[f].get("finished", float("inf"))
        ):
            record = self.running.pop(future)
            response = future.result()
            rows.append((record, response))
        return rows

    def invalidate(self, ids):
        for record in self.running.values():
            if record["node"] in ids:
                record["stale"] = True
                record["cancel"].set()

    def cancel_all(self):
        self.invalidate({r["node"] for r in self.running.values()})

    def close(self):
        self.pool.shutdown(wait=True, cancel_futures=True)
