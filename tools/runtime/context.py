"""Per-call deadlines shared by in-process tools and the inference client."""

from contextvars import ContextVar

TOOL_DEADLINE = ContextVar("toolkg_deadline", default=None)

CALL_CANCEL = ContextVar("toolkg_call_cancel", default=None)
