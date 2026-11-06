"""Build a separate 2560D tool index for both retrieval baselines; no API index edits."""

import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time

from src.models.embedding_profiles import (
    LOCAL_API_BASE, LOCAL_DIMENSION, LOCAL_MODEL, QUERY_INSTRUCTION,
    graph_root, validate_identity, service_state,
)
from src.utils.io import atomic_json
from src.utils.paths import project_root
from baselines.scimas.knowledge import ToolKnowledge
from baselines.scimas.task_graph import digest
from baselines.scitoolagent.retrieval import unit
from tools.catalog import ToolCatalog


def build(batch_size=8):
    import httpx

    root = project_root()
    source, target = graph_root(root, "api"), graph_root(root, "local")
    if target.exists():
        raise ValueError("Local index already exists; preserve it or choose a fresh build before replacing it")
    if type(batch_size) is not int or not 1 <= batch_size <= 32:
        raise ValueError("batch_size must be between 1 and 32")
    catalog = ToolCatalog(root)
    # Verify source contracts/annotations before deriving a second vector space.
    original = ToolKnowledge(catalog=catalog, folder=source / "scimas")
    before = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in source.rglob("*") if p.is_file() and not p.name.startswith(".")}
    started = time.monotonic()
    texts = [str((name, "has the functionality that", spec["description"]))
             for name, spec in sorted(catalog.indexed_tools("embedding").items())]
    with httpx.Client(trust_env=False, timeout=httpx.Timeout(180, connect=5)) as client:
        response = client.get(LOCAL_API_BASE + "/models")
        response.raise_for_status()
        model = next(m for m in response.json()["data"] if m["id"] == LOCAL_MODEL)
        state = service_state(root)
        if Path(model["root"]).resolve() != Path(state["model_path"]).resolve():
            raise ValueError("Local vLLM endpoint serves a different model directory")
        identity = {
            "backend": "openai", "provider": "local_qwen3", "model": LOCAL_MODEL,
            "dimension": LOCAL_DIMENSION, "api_base": LOCAL_API_BASE,
            "normalization": "client_l2", "pooling": "last_token_endoftext",
            "query_instruction": QUERY_INSTRUCTION,
            "model_fingerprint": state["model_fingerprint"],
        }
        validate_identity(identity)
        vectors, tokens = {}, 0
        for offset in range(0, len(texts), batch_size):
            batch = texts[offset:offset + batch_size]
            response = client.post(LOCAL_API_BASE + "/embeddings", json={
                "model": LOCAL_MODEL, "input": batch, "dimensions": LOCAL_DIMENSION,
                "encoding_format": "float",
            })
            response.raise_for_status()
            data = response.json()
            if (service_state(root)["model_fingerprint"] != identity["model_fingerprint"]
                    or data.get("model") != LOCAL_MODEL):
                raise ValueError("Embedding service changed during index build")
            rows = data["data"]
            if (len(rows) != len(batch) or {r["index"] for r in rows} != set(range(len(batch)))):
                raise ValueError("Embedding batch indices are incomplete")
            for row in rows:
                vectors[batch[row["index"]]] = unit(row["embedding"], LOCAL_DIMENSION)
            tokens += data["usage"]["prompt_tokens"]
            print(json.dumps({"embedded": len(vectors), "total": len(texts), "dimension": LOCAL_DIMENSION}), flush=True)

    # Local graph topology and annotations remain the same; only vector artifacts differ.
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".qwen-embedding-", dir=target.parent) as temp:
        staging = Path(temp) / target.name
        (staging / "scimas").mkdir(parents=True)
        shutil.copy2(source / "graph_store.json", staging / "graph_store.json")
        store = json.loads((source / "index_store.json").read_text())
        entry = next(iter(store["index_store/data"].values()))
        index = json.loads(entry["__data__"])
        index["embedding_dict"] = vectors
        entry["__data__"] = json.dumps(index)
        atomic_json(staging / "index_store.json", store)
        manifest = json.loads((source / "tool_foundation_manifest.json").read_text())
        manifest.update(embedding_identity=identity, embedding_model=LOCAL_MODEL,
                        embedding_backend="local_qwen3", embedding_dimension=LOCAL_DIMENSION,
                        functionality_vectors=len(vectors),
                        text_sha256=hashlib.sha256(json.dumps(texts).encode()).hexdigest())
        atomic_json(staging / "tool_foundation_manifest.json", manifest)
        names = {ast.literal_eval(text)[0]: text for text in vectors}
        embedding = {"identity": identity, "texts": names,
                     "vectors": {name: vectors[text] for name, text in names.items()}}
        if set(names) != set(original.tools):
            raise ValueError("Local index does not cover exactly the current scientific tool graph")
        compressed = gzip.compress(json.dumps(embedding, separators=(",", ":")).encode(), mtime=0)
        for name in ("graph.json", "annotations.json"):
            shutil.copy2(source / "scimas" / name, staging / "scimas" / name)
        (staging / "scimas/embeddings.json.gz").write_bytes(compressed)
        scimas = dict(original.manifest, embedding_identity=identity,
                      embedding_file_sha256=hashlib.sha256(compressed).hexdigest(),
                      vectors=len(names), new_embedding_api_calls=0)
        atomic_json(staging / "scimas/manifest.json", scimas)
        report = {"identity": identity, "tools": len(names), "dimension": LOCAL_DIMENSION,
                  "prompt_tokens": tokens, "duration_seconds": time.monotonic() - started,
                  "source_api_indexes_unchanged": all(
                      hashlib.sha256((source / name).read_bytes()).hexdigest() == h
                      for name, h in before.items()), "read_benchmark_answers": False}
        if not report["source_api_indexes_unchanged"]:
            raise ValueError("API index changed during local index build")
        atomic_json(staging / "build_report.json", report)
        staging.rename(target)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(build(args.batch_size), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
