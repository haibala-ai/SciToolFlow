"""One task-wide ledger for generation requests, time and observed token usage."""

import math
import time
from src.models.communication import infrastructure_failure
from src.utils.timing import interval_seconds, subtract_intervals

POLICY_VERSION = "task-resources.v1"
DEFAULT_MODEL_REQUESTS = 400
DEFAULT_TASK_SECONDS = 7200


class ResourceLimit(RuntimeError):
    pass


class TaskResources:
    def __init__(
        self,
        max_model_requests=DEFAULT_MODEL_REQUESTS,
        task_seconds=DEFAULT_TASK_SECONDS,
        clock=time.monotonic,
    ):
        if type(max_model_requests) is not int or max_model_requests < 1:
            raise ValueError("max_model_requests must be a positive integer")
        if (
            isinstance(task_seconds, bool)
            or not isinstance(task_seconds, (int, float))
            or not math.isfinite(task_seconds)
            or task_seconds <= 0
        ):
            raise ValueError("task_seconds must be finite and positive")
        self.max_model_requests = max_model_requests
        self.task_seconds = task_seconds
        self.clock = clock
        self.started = clock()
        self.deadline = self.started + task_seconds
        self.requests = []
        self.completed_elapsed = None

    def check(self):
        self.check_deadline()
        if len(self.requests) >= self.max_model_requests:
            raise ResourceLimit("ModelRequestBudget")

    def check_deadline(self):
        if self.clock() >= self.deadline:
            raise ResourceLimit("TaskDeadline")

    def remaining_requests(self):
        return max(0, self.max_model_requests - len(self.requests))

    def complete(self):
        finished = self.clock()
        if finished >= self.deadline:
            raise ResourceLimit("TaskDeadline")
        self.completed_elapsed = finished - self.started

    def snapshot(self):
        prompt = completion = 0
        missing_prompt = missing_completion = 0
        for row in self.requests:
            usage = row["usage"] if isinstance(row.get("usage"), dict) else {}
            for key in ["prompt_tokens", "completion_tokens"]:
                value = usage.get(key)
                valid = type(value) is int and value >= 0
                if key == "prompt_tokens":
                    prompt += value if valid else 0
                    missing_prompt += not valid
                else:
                    completion += value if valid else 0
                    missing_completion += not valid
        return {
            "policy_version": POLICY_VERSION,
            "model_requests": len(self.requests),
            "max_model_requests": self.max_model_requests,
            "task_seconds": self.task_seconds,
            "clock_started_monotonic": self.started,
            "elapsed_seconds": (
                self.completed_elapsed
                if self.completed_elapsed is not None
                else max(0, self.clock() - self.started)
            ),
            "prompt_tokens": None if missing_prompt else prompt,
            "completion_tokens": None if missing_completion else completion,
            "observed_prompt_tokens": prompt,
            "observed_completion_tokens": completion,
            "requests_missing_prompt_usage": missing_prompt,
            "requests_missing_completion_usage": missing_completion,
            "token_usage_complete": not (missing_prompt or missing_completion),
            "requests": [dict(row) for row in self.requests],
            "communication_intervals": [span for row in self.requests
                                        for span in row.get("communication_intervals", [])],
            "communication_fault_seconds": interval_seconds(
                [span for row in self.requests for span in row.get("communication_intervals", [])]
            ),
            "model_work_intervals": [
                span for row in self.requests if row.get("status") == "returned"
                and "started_monotonic" in row and "finished_monotonic" in row
                for span in subtract_intervals(
                    [[row["started_monotonic"], row["finished_monotonic"]]],
                    row.get("communication_intervals", []),
                )
            ],
        }


class BudgetedClient:
    """Preserve backend interfaces while charging every actual request attempt."""

    def __init__(self, client, resources, phase=None):
        self.client = client
        self.resources = resources
        self.phase = phase or "react"

    def __getattr__(self, name):
        return getattr(self.client, name)

    def _preflight(self, name, *args, timeout=None):
        self.resources.check_deadline()
        method = getattr(self.client, name)
        kwargs = {}
        if getattr(self.client, "supports_preflight_timeout", False):
            remaining = self.resources.deadline - self.resources.clock()
            kwargs["timeout"] = (
                min(timeout, remaining) if timeout is not None else remaining
            )
        try:
            result = method(*args, **kwargs)
        except Exception:
            self.resources.check_deadline()
            raise
        self.resources.check_deadline()
        return result

    def input_budget(self, output_tokens, *, timeout=None):
        return self._preflight("input_budget", output_tokens, timeout=timeout)

    def count_tokens(self, messages, *, timeout=None):
        return self._preflight("count_tokens", messages, timeout=timeout)

    def request(self, messages, **kwargs):
        self.resources.check()
        remaining = self.resources.deadline - self.resources.clock()
        kwargs["timeout"] = min(kwargs.get("timeout") or remaining, remaining)
        entry = {
            "request": len(self.resources.requests) + 1,
            "phase": self.phase,
            "status": "pending",
            "usage": None,
        }
        self.resources.requests.append(entry)
        started = self.resources.clock()
        entry["started_monotonic"] = started
        try:
            reply = self.client.request(messages, **kwargs)
            entry.update(
                status="returned",
                usage=reply.get("usage"),
                response_id=reply.get("response_id"),
                communication_wait_seconds=reply.get("communication_wait_seconds", 0),
                communication_intervals=reply.get("communication_intervals", []),
            )
            if self.resources.clock() >= self.resources.deadline:
                raise ResourceLimit("TaskDeadline")
            return reply
        except (Exception, KeyboardInterrupt) as error:
            interrupted = isinstance(error, KeyboardInterrupt)
            failure = None if interrupted else infrastructure_failure(error)
            if failure:
                entry["infrastructure_failure"] = failure
            if getattr(error, "generation_usage", None) is not None:
                entry["usage"] = error.generation_usage
            entry["status"] = "error"
            if interrupted:
                entry["interrupted"] = True
            raise
        finally:
            finished = self.resources.clock()
            entry["duration_seconds"] = max(0, finished - started)
            entry["finished_monotonic"] = finished
            if entry.get("infrastructure_failure"):
                # The whole failed request already includes every internal
                # reconnect/backoff. Replace, never add, its retry intervals.
                entry["communication_intervals"] = [[started, finished]]
                entry["communication_wait_seconds"] = entry["duration_seconds"]


def remaining(limit, used):
    return None if limit is None else max(0, limit - used)


def available(value):
    return value is None or value > 0
