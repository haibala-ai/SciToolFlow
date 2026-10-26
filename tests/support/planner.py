"""Explicit reusable test controls; never benchmark gold values."""

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "object",
            "properties": {"value": {"type": "number"}},
            "required": ["value"],
        }
    },
    "required": ["results"],
}


CALL = {
    "actions": [
        {"tool": "ParseJSONDocument", "arguments": {"json_text": '{"value":7}'}}
    ]
}


PLAN = {"finish": {"plan": ["ParseJSONDocument"]}}


FINISH = {
    "finish": {
        "results": {"value": {"$observation": "o001", "field": ["document", "value"]}}
    }
}


class StaticRetriever:
    def retrieve(self, question, deadline):
        return {
            "tools": [
                {
                    "name": "ParseJSONDocument",
                    "description": "Parse JSON",
                    "graph_triples": [],
                }
            ],
            "seed_tools": ["ParseJSONDocument"],
        }
