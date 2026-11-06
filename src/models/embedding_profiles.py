"""Embedding selection keeps incompatible vector spaces in separate indexes."""

import os
import json
from pathlib import Path
from src.utils.paths import project_root

LOCAL_MODEL = "Qwen3-Embedding-4B"
LOCAL_DIMENSION = 2560
LOCAL_API_BASE = "http://127.0.0.1:18081/v1"
QUERY_INSTRUCTION = (
    "Given a scientific task requirement, retrieve scientific tools whose "
    "functions and input/output contracts can fulfill the requirement."
)


def embedding_backend(value=None):
    backend = value or os.getenv("SCITOOL_EMBEDDING_BACKEND", "api")
    if backend not in {"api", "local"}:
        raise ValueError("Embedding backend must be api or local")
    return backend


def graph_root(root=None, backend=None):
    root = Path(root or project_root())
    if embedding_backend(backend) == "local":
        return root / ".local/indexes/qwen3-embedding-4b"
    return root / "tools/graph"


def validate_identity(identity):
    local = identity.get("provider") == "local_qwen3"
    if local:
        valid = (
            identity.get("model") == LOCAL_MODEL
            and identity.get("dimension") == LOCAL_DIMENSION
            and identity.get("api_base") == LOCAL_API_BASE
            and identity.get("query_instruction") == QUERY_INSTRUCTION
            and identity.get("pooling") == "last_token_endoftext"
            and isinstance(identity.get("model_fingerprint"), str)
            and len(identity["model_fingerprint"]) == 64
        )
    else:
        valid = identity.get("model") == "text-embedding-3-large" and identity.get("dimension") == 3072
    if not valid:
        raise ValueError("Unexpected or incompatible functionality embedding identity")
    return local


def query_text(text, identity):
    if identity.get("provider") == "local_qwen3":
        return "Instruct: " + identity["query_instruction"] + "\nQuery:" + text
    return text


def service_state(root=None):
    """Native vLLM has no weight fingerprint field; bind it to our live launcher."""
    root = Path(root or project_root())
    path = root / ".local/cache/qwen3_embedding/service.json"
    if not path.is_file():
        raise ValueError("Start the local embedding service before building or querying its index")
    state = json.loads(path.read_text())
    try:
        fields = Path(f"/proc/{state['pid']}/stat").read_text().rsplit(")", 1)[1].split()
        live = fields[0] not in {"Z", "X"} and fields[19] == state["process_birth"]
    except (OSError, KeyError, IndexError):
        live = False
    if not live or state.get("model") != LOCAL_MODEL or state.get("dimension") != LOCAL_DIMENSION:
        raise ValueError("The managed local embedding process is unavailable or incompatible")
    return state
