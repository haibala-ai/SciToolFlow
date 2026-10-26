"""Local inference over a persistent Python subprocess, without an HTTP API."""

import atexit
import json
import os
from pathlib import Path
import subprocess
import threading
import queue
import time

from src.models.config import Config


def local_gpu_devices():
    """Respect explicit worker settings, then the launcher's device allocation."""
    return os.getenv("SCITOOL_LLM_GPU", os.getenv("CUDA_VISIBLE_DEVICES", "0"))


class LocalRuntime:
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()
        self.log = None
        self.replies = None
        self.reader = None
        self.model_path = None

    def _start(self, model_path=None):
        config = Config()
        config.TRACE_DIR.mkdir(parents=True, exist_ok=True)
        self.log = (config.TRACE_DIR / "local_runtime.log").open("a")
        env = os.environ.copy()
        env["TOKENIZERS_PARALLELISM"] = "false"
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        env["PYTHONNOUSERSITE"] = "1"
        env["CUDA_VISIBLE_DEVICES"] = local_gpu_devices()
        worker = Path(__file__).with_name("local_worker.py")
        self.process = subprocess.Popen(
            [
                config.LLM_PYTHON,
                "-u",
                str(worker),
                "--model",
                model_path or config.LOCAL_MODEL_PATH,
                "--embedding",
                config.LOCAL_EMBED_PATH,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.log,
            text=True,
            bufsize=1,
            env=env,
        )
        self.replies = queue.Queue()
        self.reader = threading.Thread(
            target=self._read_replies, args=(self.process, self.replies), daemon=True
        )
        self.reader.start()
        self.model_path = model_path or config.LOCAL_MODEL_PATH

    @staticmethod
    def _read_replies(process, replies):
        for line in process.stdout:
            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "ok" in reply:
                replies.put(reply)
        replies.put(
            {
                "ok": False,
                "error": "Local inference worker stopped; inspect results/model_logs/local_runtime.log",
            }
        )

    def request(self, operation, **kwargs):
        from tools.runtime.context import TOOL_DEADLINE

        deadline = TOOL_DEADLINE.get() or (
            time.monotonic() + float(os.getenv("SCITOOL_LLM_REQUEST_TIMEOUT", "600"))
        )
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not self.lock.acquire(timeout=remaining):
            raise TimeoutError("Timed out waiting for the local inference worker")
        try:
            model_path = kwargs.pop("model_path", None)
            if model_path and self.model_path and model_path != self.model_path:
                self.close()
            if self.process is None or self.process.poll() is not None:
                self._start(model_path)
            self.process.stdin.write(
                json.dumps({"operation": operation, **kwargs}) + "\n"
            )
            self.process.stdin.flush()
            remaining = deadline - time.monotonic()
            try:
                reply = self.replies.get(timeout=max(0, remaining))
            except queue.Empty:
                self.close()
                raise TimeoutError(
                    "Local inference worker exceeded the request deadline"
                )
            if not reply["ok"]:
                raise RuntimeError(reply["error"])
            return reply
        finally:
            self.lock.release()

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        if self.reader:
            self.reader.join(timeout=1)
        if self.process:
            for stream in (
                self.process.stdin,
                self.process.stdout,
                self.process.stderr,
            ):
                if stream:
                    stream.close()
        if self.log:
            self.log.close()
        self.process = None
        self.log = None
        self.reader = None


RUNTIME = LocalRuntime()
atexit.register(RUNTIME.close)
