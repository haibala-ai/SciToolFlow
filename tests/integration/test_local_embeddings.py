"""Separate vector spaces, query preprocessing and the loopback embedding contract."""

import json
import os
import hashlib
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.models.embedding_profiles import (
    LOCAL_API_BASE, LOCAL_MODEL, QUERY_INSTRUCTION, embedding_backend,
    graph_root, query_text, validate_identity, service_state,
)
from baselines.scitoolagent.retrieval import Embeddings, RetrievalError
from scripts.services.embedding_service import model_fingerprint, process_birth


def local_identity():
    return {
        "model": LOCAL_MODEL, "dimension": 2560, "provider": "local_qwen3",
        "api_base": LOCAL_API_BASE, "pooling": "last_token_endoftext",
        "model_fingerprint": "a" * 64, "query_instruction": QUERY_INSTRUCTION,
    }


def test_index_selection_and_vector_spaces_stay_separate(tmp_path, monkeypatch):
    monkeypatch.delenv("SCITOOL_EMBEDDING_BACKEND", raising=False)
    assert embedding_backend() == "api"
    assert graph_root(tmp_path) == tmp_path / "tools/graph"
    assert graph_root(tmp_path, "local") == tmp_path / ".local/indexes/qwen3-embedding-4b"
    assert query_text("invert a matrix", {"model": "text-embedding-3-large"}) == "invert a matrix"
    assert query_text("invert a matrix", local_identity()).endswith("\nQuery:invert a matrix")
    assert validate_identity(local_identity()) is True
    assert validate_identity({"model": "text-embedding-3-large", "dimension": 3072}) is False
    with pytest.raises(ValueError):
        validate_identity({**local_identity(), "dimension": 3072})
    with pytest.raises(ValueError):
        embedding_backend("typo")


@pytest.mark.parametrize("wrong_model", [False, True])
def test_local_queries_ignore_remote_credentials_and_check_service_identity(tmp_path, monkeypatch, wrong_model):
    import requests
    monkeypatch.setenv("SCITOOL_EMBEDDING_API_BASE", "https://remote.example/v1")
    monkeypatch.setenv("SCITOOL_EMBEDDING_API_KEY", "remote-secret-test")
    identity = local_identity()
    vector = [1.0] + [0.0] * 2559
    session = Mock()
    session.post.return_value = SimpleNamespace(status_code=200, json=lambda: {
        "model": LOCAL_MODEL, "model_fingerprint": "b" * 64 if wrong_model else "a" * 64,
        "data": [{"index": 0, "embedding": vector}], "usage": {"prompt_tokens": 9},
    })
    context = Mock()
    context.__enter__ = Mock(return_value=session)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(requests, "Session", lambda: context)
    encoder = Embeddings(identity, tmp_path)
    if wrong_model:
        with pytest.raises(RetrievalError, match="identity differs"):
            encoder.encode(["invert a matrix"], time.monotonic() + 5)
        assert not list(encoder.cache.glob("*.json"))
    else:
        assert encoder.encode(["invert a matrix"], time.monotonic() + 5) == [vector]
        assert encoder.encode(["invert a matrix"], time.monotonic() + 5) == [vector]
        assert session.post.call_count == 1
    assert session.trust_env is False
    url = session.post.call_args.args[0]
    options = session.post.call_args.kwargs
    assert url == LOCAL_API_BASE + "/embeddings"
    assert options["headers"]["Authorization"] == "Bearer local"
    assert options["json"]["input"] == [query_text("invert a matrix", identity)]
    assert options["json"]["dimensions"] == 2560


def test_model_weight_fingerprint_detects_corruption(tmp_path):
    weights = tmp_path / "model.safetensors"
    weights.write_bytes(b"small synthetic identity fixture")
    manifest = {"files": [{"file": weights.name,
                           "sha256": hashlib.sha256(weights.read_bytes()).hexdigest()}]}
    (tmp_path / "download_manifest.json").write_text(json.dumps(manifest))
    original = model_fingerprint(tmp_path)
    assert len(original) == 64
    weights.write_bytes(b"changed synthetic bytes")
    with pytest.raises(ValueError, match="differs from download manifest"):
        model_fingerprint(tmp_path)


def test_native_vllm_identity_requires_live_managed_process(tmp_path):
    path = tmp_path / ".local/cache/qwen3_embedding/service.json"
    path.parent.mkdir(parents=True)
    state = {"pid": os.getpid(), "process_birth": process_birth(os.getpid()),
             "model": LOCAL_MODEL, "dimension": 2560, "model_fingerprint": "a" * 64}
    path.write_text(json.dumps(state))
    assert service_state(tmp_path)["model_fingerprint"] == "a" * 64
    state["process_birth"] = "old-process"
    path.write_text(json.dumps(state))
    with pytest.raises(ValueError, match="unavailable or incompatible"):
        service_state(tmp_path)


@pytest.mark.parametrize("explicit_null", [False, True])
def test_native_embedding_payload_requires_matching_launcher_fingerprint(tmp_path, monkeypatch, explicit_null):
    import requests
    data = {"model": LOCAL_MODEL, "data": [{"index": 0, "embedding": [1.0] + [0.0] * 2559}]}
    if explicit_null:
        data["model_fingerprint"] = None
    session = Mock()
    session.post.return_value = SimpleNamespace(status_code=200, json=lambda: data)
    context = Mock()
    context.__enter__ = Mock(return_value=session)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(requests, "Session", lambda: context)
    monkeypatch.setattr("baselines.scitoolagent.retrieval.service_state",
                        lambda root: {"model_fingerprint": "b" * 64})
    encoder = Embeddings(local_identity(), tmp_path)
    with pytest.raises(RetrievalError, match="identity differs"):
        encoder.encode(["matrix inverse"], time.monotonic() + 5)
    assert not list(encoder.cache.glob("*.json"))
