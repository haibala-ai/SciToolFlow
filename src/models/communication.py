"""Credential-free communication diagnostics shared by actors and scheduling."""

from copy import deepcopy


class CommunicationError(RuntimeError):
    def __init__(self, message, *, service, category, retryable=True,
                 request_may_have_been_sent=True, attempts=1, http_status=None):
        super().__init__(message)
        self.infrastructure_failure = {
            "service": service,
            "category": category,
            "retryable": retryable,
            "request_may_have_been_sent": request_may_have_been_sent,
            "attempts": attempts,
        }
        if http_status is not None:
            self.infrastructure_failure["http_status"] = http_status


def infrastructure_failure(error):
    """Keep typed diagnostics through Planner wrappers without parsing messages."""
    seen, pending = set(), [error]
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        value = getattr(current, "infrastructure_failure", None)
        if value:
            return deepcopy(value)
        pending.extend([current.__cause__, current.__context__])
    return None


class CommunicationCircuit:
    """Stop admitting tasks after consecutive terminal infrastructure failures.

    Active tasks drain normally. A successful/non-infrastructure result resets
    the streak before opening; once open, explicit batch resume is required.
    """

    def __init__(self, threshold=3):
        if type(threshold) is not int or threshold < 0:
            raise ValueError("Network failure threshold must be a nonnegative integer")
        self.threshold, self.consecutive = threshold, 0
        self.open = False
        self.last_failure = None

    def observe(self, prediction):
        failure = prediction.get("infrastructure_failure")
        if not failure:
            if not self.open:
                self.consecutive = 0
            return
        self.consecutive += 1
        self.last_failure = deepcopy(failure)
        if self.threshold and self.consecutive >= self.threshold:
            self.open = True

    def snapshot(self):
        return {"open": self.open, "threshold": self.threshold,
                "consecutive_failures": self.consecutive,
                "last_failure": self.last_failure}
