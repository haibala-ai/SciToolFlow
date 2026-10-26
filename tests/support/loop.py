"""Explicit reusable test controls; never benchmark gold values."""

import copy
import json
from .clients import ScriptedClient


def action(value=7):
    return {
        "tool": "ParseJSONDocument",
        "arguments": {"json_text": json.dumps({"value": value})},
    }


A = {"actions": [action()]}


FINISH = {"finish": {"value": 7}}


SCHEMA = {
    "type": "object",
    "properties": {"value": {"type": "number"}},
    "required": ["value"],
}


class SchemaClient(ScriptedClient):
    supports_response_schema = True

    def __init__(self, replies):
        super().__init__(replies)
        self.options = []

    def request(self, messages, **kwargs):
        self.options.append(copy.deepcopy(kwargs))
        return super().request(messages, **kwargs)
