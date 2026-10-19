"""Detect a run of identical executed tool steps, never cumulative reuse."""

import hashlib
import json


class ConsecutiveToolSteps:
    def __init__(self, state=None):
        self.state = state if state is not None else {}

    def observe(self, step, number):
        calls = step.get("calls", [])
        if step.get("type") != "tools" or not calls or step.get("action_errors"):
            self.state.clear()
            return 0
        signatures = [
            hashlib.sha256(
                json.dumps(
                    [call["tool"], call["arguments"]],
                    sort_keys=True,
                    ensure_ascii=False,
                    allow_nan=False,
                ).encode()
            ).hexdigest()
            for call in calls
        ]
        if len(set(signatures)) != 1:
            self.state.clear()
            return 0
        signature = signatures[0]
        if self.state.get("signature") == signature:
            self.state["count"] += 1
        else:
            self.state.clear()
            self.state.update(
                signature=signature,
                count=1,
                first_step=number,
                tool=calls[0]["tool"],
                arguments=calls[0]["arguments"],
            )
        self.state["last_step"] = number
        return self.state["count"]
