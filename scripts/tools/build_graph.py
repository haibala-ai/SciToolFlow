"""Build current tool-contract graph and cached API functionality embeddings."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.utils.paths import load_environment
from src.utils.io import atomic_json
from tools.catalog import ToolCatalog
from tools.catalog.ports import validate_ports
from src import __version__


def digest(value):
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def checked(vector):
    if len(vector) != 3072 or any(
        type(x) not in (int, float) or not math.isfinite(x) for x in vector
    ):
        raise ValueError("Invalid embedding dimension or nonfinite values")
    norm = math.sqrt(math.fsum(x * x for x in vector))
    if not norm > 0 or not math.isfinite(norm):
        raise ValueError("Invalid embedding norm")
    return [x / norm for x in vector]


def functionality_text(name, spec):
    return str((name, "has the functionality that", spec["description"]))


def make_graph(catalog):
    """Only current contracts define nodes; no stale legacy edges survive."""
    domains = {
        "Chemical": "Chemical Tool",
        "Material": "Material Tool",
        "Biology": "Biological Tool",
        "MachineLearning": "Machine Learning Tool",
        "General": "General Tool",
    }
    graph = {}
    inverse = {
        "is a": "has tool",
        "has the functionality that": "is the functionality of",
        "has call signature": "is call signature of",
        "is documented at": "documents tool",
        "has implementation": "implements tool",
        "has input schema": "is input schema of",
        "has output schema": "is output schema of",
        "has parameter documentation": "is parameter documentation of",
        "has return documentation": "is return documentation of",
        "has observed output format": "is output format of",
        "has failure feedback": "is failure feedback of",
        "runs in": "runs tool",
        "inputs": "is the input of",
        "outputs": "is the output of",
        "has input type": "is input type of",
        "has output type": "is output type of",
        "has alias": "is an alias of",
        "has parameter summary": "is parameter summary of",
        "has output description": "is output description of",
        "has dataflow contract": "is dataflow contract of",
    }

    def link(source, relation, target):
        for a, r, b in [
            (source, relation, target),
            (target, inverse[relation], source),
        ]:
            pair = [r, b]
            if pair not in graph.setdefault(a, []):
                graph[a].append(pair)

    def type_text(value):
        if isinstance(value, str):
            return value
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return " | ".join(value)
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    indexed = catalog.indexed_tools("graph")
    for name, spec in sorted(indexed.items()):
        link(name, "is a", domains[spec["domain"]])
        link(name, "has the functionality that", spec["description"])
        link(name, "has call signature", spec["call_signature"])
        link(name, "is documented at", "tools/catalog/catalog.json#/tools/" + name)
        link(
            name,
            "has implementation",
            spec["source"]["file"] + ":" + spec["source"]["function"],
        )
        validate_ports(name, spec)
        link(
            name,
            "has parameter summary",
            "; ".join(f'{p["name"]}: {p["type"]}' for p in spec["parameters"])
            or "no arguments",
        )
        link(name, "has output description", spec["output_description"])
        for port in spec["dataflow"]["inputs"]:
            link(name, "inputs", port["concept"])
        for port in spec["dataflow"]["outputs"]:
            link(name, "outputs", port["concept"])
        link(
            name,
            "has dataflow contract",
            json.dumps(spec["dataflow"], ensure_ascii=False, sort_keys=True),
        )
        for parameter in spec["parameters"]:
            link(name, "has input type", type_text(parameter["type"]))
        for returned in spec["returns"]:
            link(name, "has output type", type_text(returned["type"]))
        for key, relation in [
            ("input_schema", "has input schema"),
            ("output_schema", "has output schema"),
            ("parameters", "has parameter documentation"),
            ("returns", "has return documentation"),
            ("output_encoding", "has observed output format"),
            ("failure_feedback", "has failure feedback"),
        ]:
            if key in spec:
                link(
                    name,
                    relation,
                    json.dumps(spec[key], ensure_ascii=False, sort_keys=True),
                )
        if spec["execution"].get("environment"):
            link(name, "runs in", spec["execution"]["environment"])
    for alias, target in catalog.aliases.items():
        canonical = catalog.canonical(target)
        if canonical in indexed:
            link(canonical, "has alias", alias)
    # A metadata lookup is available directly, and must never leak in as an alias/node/edge.
    excluded = set(catalog.tools) - set(indexed)
    if excluded & set(graph) or any(
        target in excluded for pairs in graph.values() for _, target in pairs
    ):
        raise ValueError("Non-indexed tool leaked into graph")
    return graph


def embed(catalog, manifest, force=False):
    load_environment()
    base = (
        os.getenv("SCITOOL_EMBEDDING_API_BASE")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("OPENAI_API_BASE")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    key = os.getenv("SCITOOL_EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "Configure SCITOOL_EMBEDDING_API_KEY in .local/credentials/services.env"
        )
    from openai import OpenAI

    client = OpenAI(api_key=key, base_url=base, timeout=90, max_retries=2)
    identity = {
        "backend": "openai",
        "model": "text-embedding-3-large",
        "dimension": 3072,
        "api_base": base,
        "provider": (
            "official_openai"
            if base == "https://api.openai.com/v1"
            else "openai_compatible"
        ),
        "normalization": "client_l2",
    }
    texts = [
        functionality_text(n, spec)
        for n, spec in sorted(catalog.indexed_tools("embedding").items())
    ]
    index_path = ROOT / "tools/graph/index_store.json"
    store = json.loads(index_path.read_text())
    entry = next(iter(store["index_store/data"].values()))
    index = json.loads(entry["__data__"])
    prior = index.get("embedding_dict", {})
    valid = (
        not force
        and manifest.get("embedding_identity") == identity
        and manifest.get("text_sha256") == digest(sorted(prior))
    )
    vectors = {text: checked(prior[text]) for text in texts if valid and text in prior}
    cache_path = ROOT / "tools/graph/.embedding_build_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if not force and cache.get("identity") == identity:
        for text, vector in cache.get("vectors", {}).items():
            if text in texts and text not in vectors:
                vectors[text] = checked(vector)
    missing = [text for text in texts if text not in vectors]
    batches = []
    history = (
        cache.get("batch_history", []) if cache.get("identity") == identity else []
    )
    started = time.monotonic()
    for offset in range(0, len(missing), 32):
        batch = missing[offset : offset + 32]
        response = client.embeddings.create(
            model=identity["model"], input=batch, encoding_format="float"
        )
        if response.model != identity["model"]:
            raise ValueError("Embedding model mismatch")
        data = sorted(response.data, key=lambda item: item.index)
        if [item.index for item in data] != list(range(len(batch))):
            raise ValueError("Embedding response index/order mismatch")
        vectors.update(
            (text, checked(item.embedding)) for text, item in zip(batch, data)
        )
        batches.append({"inputs": len(batch), "tokens": response.usage.prompt_tokens})
        history.append(
            {
                "inputs": len(batch),
                "input_sha256": digest(batch),
                "prompt_tokens": response.usage.prompt_tokens,
            }
        )
        atomic_json(
            cache_path,
            {"identity": identity, "vectors": vectors, "batch_history": history},
        )
        print(
            json.dumps(
                {"embedded": min(offset + 32, len(missing)), "new_texts": len(missing)}
            ),
            flush=True,
        )
    ordered = {text: vectors[text] for text in texts}
    index["embedding_dict"] = ordered
    entry["__data__"] = json.dumps(index)
    # Save the index only after all requested vectors have passed validation.
    atomic_json(index_path, store)
    manifest.update(
        embedding_identity=identity,
        embedding_model=identity["model"],
        embedding_backend="openai",
        embedding_dimension=3072,
        functionality_vectors=len(texts),
        text_sha256=digest(texts),
    )
    return {
        "identity": identity,
        "vectors": len(ordered),
        "reused": len(texts) - len(missing),
        "encoded": len(missing),
        "api_batches": batches,
        "prompt_tokens": sum(b["tokens"] for b in batches),
        "duration_seconds": time.monotonic() - started,
        "excluded_tools": sorted(
            set(catalog.tools) - set(catalog.indexed_tools("embedding"))
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--embed", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    catalog = ToolCatalog(ROOT)
    manifest_path = ROOT / "tools/graph/tool_foundation_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "public_tools": len(catalog.tools),
        "public_tool_nodes": len(catalog.indexed_tools("graph")),
        "domain_counts": dict(
            __import__("collections").Counter(
                s["domain"] for s in catalog.tools.values()
            )
        ),
        "excluded_graph_tools": sorted(
            set(catalog.tools) - set(catalog.indexed_tools("graph"))
        ),
        "registered_aliases": len(catalog.aliases),
        "retired_names": len(catalog.retired),
        "benchmark_content_read": False,
    }
    # Validate graph shape before making paid API requests or replacing vectors.
    graph = make_graph(catalog)
    if args.embed:
        report["embedding"] = embed(catalog, manifest, args.force)
    else:
        expected = {
            functionality_text(n, s)
            for n, s in catalog.indexed_tools("embedding").items()
        }
        store = json.loads((ROOT / "tools/graph/index_store.json").read_text())
        index = json.loads(next(iter(store["index_store/data"].values()))["__data__"])
        if set(index.get("embedding_dict", {})) != expected:
            raise ValueError(
                "Functionality vectors are stale; run build_graph.py --embed"
            )
    report.update(
        nodes=len(graph),
        directed_edges=sum(map(len, graph.values())),
        relation_types=len({r for pairs in graph.values() for r, _ in pairs}),
        all_indexed_contracts_linked=True,
    )
    manifest.update(
        public_tools=len(catalog.tools),
        indexed_tools=len(catalog.indexed_tools("graph")),
        excluded_graph_tools=report["excluded_graph_tools"],
        graph_nodes=len(graph),
        graph_edges=report["directed_edges"],
        catalog_sha256=hashlib.sha256(
            (ROOT / "tools/catalog/catalog.json").read_bytes()
        ).hexdigest(),
        contract_file="tools/catalog/catalog.json",
        sync_report="tools/graph/build_report.json",
        embedding_build_report="tools/graph/build_report.json",
    )
    manifest["project_version"] = __version__
    atomic_json(ROOT / "tools/graph/graph_store.json", {"graph_dict": graph})
    atomic_json(manifest_path, manifest)
    atomic_json(ROOT / "tools/graph/build_report.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
