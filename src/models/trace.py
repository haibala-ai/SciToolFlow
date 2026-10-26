"""Per-run machine-readable execution records."""

from contextvars import ContextVar
from datetime import datetime, timezone

CURRENT_TRACE = ContextVar("scitool_trace", default=None)


def record(event, **fields):
    trace = CURRENT_TRACE.get()
    if trace is not None:
        trace["events"].append(
            {"event": event, "time": datetime.now(timezone.utc).isoformat(), **fields}
        )
