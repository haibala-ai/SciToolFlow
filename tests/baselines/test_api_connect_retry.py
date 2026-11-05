"""Retry only proven pre-send failures, never potentially billed generations."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
import httpx
import pytest
from src.models.client import GenerationClient


def reply(status=200):
    return SimpleNamespace(
        status_code=status,
        json=lambda: {
            "choices": [
                {"finish_reason": "stop", "message": {"content": '{"ok":true}'}}
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


def request(outcomes):
    env = {
        "SCITOOLFLOW_API_BASE": "https://api.example.com/v1",
        "SCITOOLFLOW_API_KEY": "TEST_ONLY",
        "SCITOOLFLOW_API_MODEL": "test",
        "SCITOOLFLOW_API_TRANSPORT": "httpx",
        "SCITOOLFLOW_API_EXTRA_BODY": "{}",
    }
    with patch.dict("os.environ", env), patch("src.models.client.time.sleep"):
        client = GenerationClient("api")
        client._session = Mock()
        client._session.post.side_effect = outcomes
        try:
            with client.generation_scope():
                result = client.request([{"role": "user", "content": "Return JSON"}])
            return result, client._session.post.call_count
        except RuntimeError as e:
            return e, client._session.post.call_count
        finally:
            client.close()


def test_connect_errors_retry_before_any_generation():
    result, count = request(
        [httpx.ConnectError("TLS"), httpx.ConnectTimeout("connect"), reply()]
    )
    assert count == 3 and result["connection_attempts"] == 3


@pytest.mark.parametrize(
    "error",
    [
        httpx.ReadTimeout("read"),
        httpx.ReadError("read"),
        httpx.WriteError("write"),
        httpx.RemoteProtocolError("response"),
    ],
)
def test_potentially_billed_requests_are_not_retried(error):
    result, count = request([error, reply()])
    assert count == 1 and isinstance(result, RuntimeError)


def test_http_error_is_not_retried():
    result, count = request([reply(503), reply()])
    assert count == 1 and isinstance(result, RuntimeError)


def test_connect_retries_are_bounded():
    result, count = request([httpx.ConnectError("TLS")] * 4)
    assert count == 3 and isinstance(result, RuntimeError)
