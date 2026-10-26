"""Explicit reusable test controls; never benchmark gold values."""

import copy
import json


class ScriptedClient:
    model = "scripted-protocol-control"
    backend = "injected"

    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    def request(self, messages, **kwargs):
        self.requests.append(copy.deepcopy(messages))
        return {
            "text": json.dumps(next(self.replies)),
            "model": self.model,
            "usage": None,
        }

    def generation_scope(self):
        from contextlib import nullcontext

        return nullcontext()
