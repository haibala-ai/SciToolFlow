"""The complete SciMas role loop uses the shared real HTTP transport."""

from src.models.client import GenerationClient
from tools import execute
from tests.baselines.test_model_backends import api_server
from .test_knowledge_planner import decomposition, valid_plan
from .test_runtime import run


def test_complete_workflow_through_api_transport(tmp_path):
    approve = {
        "approve": {"reason": "Public scientific requirements checked", "gates": []}
    }
    accept = {"accept": {"reason": "Actual output checked", "semantics": []}}
    replies = [
        decomposition(),
        {"plan": valid_plan()},
        approve,
        {"dispatch": ["inverse"]},
        accept,
        {"dispatch": ["check"]},
        accept,
        {"finish": {"inverse": [[0.5, 0], [0, 0.25]], "product": [[1, 0], [0, 1]]}},
        approve,
    ]
    with api_server(replies, SCITOOLFLOW_API_STRUCTURED_OUTPUT="0") as sent:
        client = GenerationClient("api")
        try:
            result = run(tmp_path, client, invoke=execute)
        finally:
            client.close()
    assert result["status"] == "completed", result["failure_reason"]
    assert len(sent) == 9
    assert all(r["path"] == "/v1/chat/completions" for r in sent)
    assert all(r["payload"]["model"] == "mock-model" for r in sent)
    assert all("max_tokens" in r["payload"] for r in sent)
    assert any(len(r["payload"]["messages"]) == 3 for r in sent)
    assert result["stats"]["scientific_calls"] == 2
