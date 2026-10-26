"""Role-session settings; the concrete bounded decision loop lives in ReAct."""

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class SessionOptions:
    baseline: str = "react"
    phase: Optional[str] = None
    system_prompt: Optional[str] = None
    allowed_tools: Optional[set] = None
    allow_discovery: bool = True
    extra_inputs: dict = field(default_factory=dict)
    observations: dict = field(default_factory=dict)
    counter_offsets: dict = field(default_factory=dict)
    failures: dict = field(default_factory=dict)
    repetition_state: dict = field(default_factory=dict)
    yield_after_success: bool = False
    persist: bool = True
    on_update: Optional[Callable] = None
    resources: object = None
