"""Generation can bypass proxy variables without rerouting embeddings or tools."""

import os
from unittest.mock import Mock

import pytest

from src.models.client import GenerationClient
from .test_api_connect_retry import reply


@pytest.mark.parametrize("transport", ["requests", "httpx"])
@pytest.mark.parametrize("flag", ["0", "1", None])
def test_generation_proxy_selection_is_local_to_its_client(
    monkeypatch, transport, flag
):
    for name, value in {
        "SCITOOLFLOW_API_BASE": "https://api.example.com",
        "SCITOOLFLOW_API_KEY": "TEST_ONLY",
        "SCITOOLFLOW_API_MODEL": "fixture",
        "SCITOOLFLOW_API_TRANSPORT": transport,
        "SCITOOLFLOW_API_EXTRA_BODY": "{}",
        "HTTPS_PROXY": "http://127.0.0.1:9",
    }.items():
        monkeypatch.setenv(name, value)
    if flag is None:
        monkeypatch.delenv("SCITOOLFLOW_API_TRUST_ENV", raising=False)
    else:
        monkeypatch.setenv("SCITOOLFLOW_API_TRUST_ENV", flag)
    session = Mock()
    session.trust_env = True
    session.post.return_value = reply()
    constructor = Mock(return_value=session)
    monkeypatch.setattr(
        "httpx.Client" if transport == "httpx" else "requests.Session", constructor
    )
    client = GenerationClient("api")
    try:
        with client.generation_scope():
            result = client.request([{"role": "user", "content": "Return JSON"}])
        expected = flag != "0"
        assert client.public_settings()["trust_env"] is expected
        if transport == "httpx":
            constructor.assert_called_once_with(trust_env=expected)
        else:
            assert session.trust_env is expected
        assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:9"
        assert result["text"] == '{"ok":true}'
    finally:
        client.close()


@pytest.mark.parametrize("transport", ["requests", "httpx"])
def test_connection_deadline_is_separate_from_generation_wait(monkeypatch, transport):
    for name, value in {
        "SCITOOLFLOW_API_BASE": "https://api.example.com",
        "SCITOOLFLOW_API_KEY": "TEST_ONLY",
        "SCITOOLFLOW_API_MODEL": "fixture",
        "SCITOOLFLOW_API_TRANSPORT": transport,
        "SCITOOLFLOW_API_CONNECT_TIMEOUT": "7",
        "SCITOOLFLOW_API_TIMEOUT": "600",
        "SCITOOLFLOW_API_EXTRA_BODY": "{}",
    }.items():
        monkeypatch.setenv(name, value)
    session = Mock()
    session.post.return_value = reply()
    monkeypatch.setattr(
        "httpx.Client" if transport == "httpx" else "requests.Session",
        Mock(return_value=session),
    )
    client = GenerationClient("api")
    try:
        with client.generation_scope():
            client.request([{"role": "user", "content": "Return JSON"}], timeout=31)
        timeout = session.post.call_args.kwargs["timeout"]
        if transport == "httpx":
            assert timeout.connect == 7 and 7 < timeout.read <= 31
        else:
            assert timeout[0] == 7 and 7 < timeout[1] <= 31
        assert client.public_settings()["connect_timeout_seconds"] == 7
    finally:
        client.close()
