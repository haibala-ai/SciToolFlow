"""Serve Qwen3-Embedding-4B with vLLM in a foreground process suitable for tmux."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

from src.models.embedding_profiles import LOCAL_MODEL, LOCAL_DIMENSION, LOCAL_API_BASE, service_state
from src.utils.paths import project_root
from src.utils.io import atomic_json


def model_fingerprint(path):
    """Bind local indexes to verified weights/tokenizer, including standard HF downloads."""
    manifest_path = path / "download_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    files = sorted(p for p in path.rglob("*") if p.is_file()
                   and not any(part.startswith(".") for part in p.relative_to(path).parts)
                   and p != manifest_path and p.suffix in {".safetensors", ".json", ".txt"})
    identities = {}
    expected = {r["file"]: r["sha256"] for r in manifest["files"]} if manifest else {}
    for file in files:
        checksum = hashlib.sha256()
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                checksum.update(chunk)
        name = file.relative_to(path).as_posix()
        identities[name] = checksum.hexdigest()
        if expected and expected.get(name) != identities[name]:
            raise ValueError("Local model file differs from download manifest: " + name)
    if not any(name.endswith(".safetensors") for name in identities):
        raise ValueError("No model safetensors were downloaded")
    return hashlib.sha256(json.dumps(identities, sort_keys=True).encode()).hexdigest()


def process_birth(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return fields[19] if fields[0] not in {"Z", "X"} else None
    except (OSError, IndexError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpus", default="0,1", help="Physical GPU indices, e.g. 0,1")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(service_state(), ensure_ascii=False, indent=2))
        return
    gpus = args.gpus.split(",")
    if not gpus or any(not g.isdigit() for g in gpus) or len(set(gpus)) != len(gpus):
        parser.error("--gpus must be distinct nonnegative integer indices")
    root = project_root()
    config = json.loads((root / "configs/services/qwen3_embedding.json").read_text())
    if config["host"] != "127.0.0.1":
        parser.error("Embedding service must bind to loopback")
    if LOCAL_API_BASE != f"http://{config['host']}:{config['port']}/v1" or config["dimension"] != LOCAL_DIMENSION:
        parser.error("Embedding service address and dimension must match the local retrieval profile")
    model = (root / config["model_path"]).resolve()
    state_path = root / ".local/cache/qwen3_embedding/service.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if process_birth(state.get("pid")) == state.get("process_birth") and state.get("process_birth"):
            parser.error("A managed embedding service is already running")
    fingerprint = model_fingerprint(model)
    command = [sys.executable, "-m", "vllm.entrypoints.openai.api_server",
               "--model", str(model), "--served-model-name", LOCAL_MODEL,
               "--runner", "pooling", "--convert", "embed",
               "--tensor-parallel-size", str(len(gpus)),
               "--host", config["host"], "--port", str(config["port"]),
               "--dtype", config["dtype"], "--max-model-len", str(config["max_input_tokens"]),
               "--max-num-batched-tokens", str(config["batch_token_budget"]),
               "--max-num-seqs", str(config["max_batch_items"]),
               "--gpu-memory-utilization", str(config["gpu_memory_utilization"]),
               "--pooler-config", json.dumps({"pooling_type": "LAST", "use_activation": True}),
               "--hf-overrides", json.dumps({"is_matryoshka": True, "matryoshka_dimensions": [LOCAL_DIMENSION]}),
               "--enforce-eager", "--no-enable-log-requests"]
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=args.gpus, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    process = subprocess.Popen(command, cwd=root, env=env, start_new_session=True)
    state = {"pid": process.pid, "process_birth": process_birth(process.pid),
             "model": LOCAL_MODEL, "dimension": LOCAL_DIMENSION,
             "model_path": str(model), "model_fingerprint": fingerprint,
             "gpus": [int(g) for g in gpus], "pooling": "last_token_endoftext",
             "command": command}
    atomic_json(state_path, state)
    print(json.dumps(state, ensure_ascii=False), flush=True)
    try:
        code = process.wait()
    except KeyboardInterrupt:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            code = process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
