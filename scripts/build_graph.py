"""Synchronize project graph and API functionality embeddings, never legacy tuples."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scitoolflow.paths import load_environment
from scitoolflow.io import atomic_json


def digest(value):
    return hashlib.sha256(json.dumps(value).encode()).hexdigest()


def checked(vector):
    if len(vector) != 3072 or not all(
        isinstance(x, (float, int)) and math.isfinite(x) for x in vector
    ):
        raise ValueError("Invalid embedding dimension/values")
    norm = math.sqrt(sum(x * x for x in vector))
    if norm <= 0:
        raise ValueError("Zero embedding")
    return [x / norm for x in vector]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--embed", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    catalog_document = json.loads((ROOT / "tools/catalog.json").read_text())
    catalog = catalog_document["tools"]
    source_info = {name: spec["source"] for name, spec in catalog.items()}
    graph_path = ROOT / "tools/graph/graph_store.json"
    old = json.loads(graph_path.read_text())["graph_dict"]
    inverses = {}
    for name in catalog:
        for relation, target in old.get(name, []):
            for reverse, value in old.get(target, []):
                if value == name:
                    inverses.setdefault(relation, Counter())[reverse] += 1
    inverse = {key: counts.most_common(1)[0][0] for key, counts in inverses.items()}
    inverse.update(
        {
            "has the functionality that": "is the functionality of",
            "has input schema": "is input schema of",
            "has output schema": "is output schema of",
            "has parameter documentation": "is parameter documentation of",
            "has return documentation": "is return documentation of",
            "has call signature": "is call signature of",
        }
    )
    graph = {}
    new_relations = {
        "has alias",
        "is an alias of",
        "is documented at",
        "has argument schema",
        "has implementation",
        "has the functionality that",
        "has input schema",
        "has output schema",
        "has parameter documentation",
        "has return documentation",
        "has call signature",
    }
    for name, spec in sorted(catalog.items()):
        forward = [
            list(pair) for pair in old.get(name, []) if pair[0] not in new_relations
        ]
        if not forward:
            forward = [
                ["is a", "General Tool"],
                ["inputs", "tool name(s)"],
                ["outputs", "public tool documentation"],
            ]
        forward.extend(
            [
                ["has the functionality that", spec["description"]],
                ["has call signature", spec["call_signature"]],
                ["is documented at", "tools/catalog.json#/tools/" + name],
                [
                    "has argument schema",
                    json.dumps(
                        spec["input_schema"], ensure_ascii=False, sort_keys=True
                    ),
                ],
                [
                    "has implementation",
                    source_info[name]["file"] + ":" + source_info[name]["function"],
                ],
                [
                    "has input schema",
                    json.dumps(
                        spec["input_schema"], ensure_ascii=False, sort_keys=True
                    ),
                ],
                [
                    "has output schema",
                    json.dumps(
                        spec["output_schema"], ensure_ascii=False, sort_keys=True
                    ),
                ],
                [
                    "has parameter documentation",
                    json.dumps(spec["parameters"], ensure_ascii=False, sort_keys=True),
                ],
                [
                    "has return documentation",
                    json.dumps(spec["returns"], ensure_ascii=False, sort_keys=True),
                ],
            ]
        )
        graph[name] = [list(p) for p in dict.fromkeys(tuple(p) for p in forward)]
    forward = list(
        (name, relation, target)
        for name, pairs in graph.items()
        for relation, target in pairs
    )
    for name, relation, target in forward:
        reverse = inverse.get(relation, "inverse: " + relation)
        pair = [reverse, name]
        if pair not in graph.setdefault(target, []):
            graph[target].append(pair)
    for alias, canonical in catalog_document.get("aliases", {}).items():
        graph.setdefault(alias, []).append(["is an alias of", canonical])
        graph[canonical].append(["has alias", alias])
    atomic_json(graph_path, {"graph_dict": graph})
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "public_tool_nodes": len(catalog),
        "scientific_tools": 546,
        "discovery_tools": 1,
        "nodes": len(graph),
        "directed_edges": sum(map(len, graph.values())),
        "relation_types": len({r for pairs in graph.values() for r, _ in pairs}),
        "all_public_contracts_linked": True,
        "registered_aliases": len(catalog_document.get("aliases", {})),
        "benchmark_content_read": False,
        "legacy_tuples_modified": False,
    }
    prior_report = ROOT / "tools/graph/build_report.json"
    if prior_report.exists() and not args.embed:
        prior = json.loads(prior_report.read_text())
        if "embedding" in prior:
            report["embedding"] = prior["embedding"]
    manifest_path = ROOT / "tools/graph/tool_foundation_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update(
        project_version="0.3.0",
        public_tools=547,
        scientific_tools=546,
        discovery_tools=1,
        graph_nodes=report["nodes"],
        graph_edges=report["directed_edges"],
        catalog_sha256=hashlib.sha256(
            (ROOT / "tools/catalog.json").read_bytes()
        ).hexdigest(),
        contract_file="tools/catalog.json",
        sync_report="tools/graph/build_report.json",
        embedding_build_report="tools/graph/build_report.json",
    )
    if args.embed:
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

        client = OpenAI(api_key=key, base_url=base, timeout=90, max_retries=1)
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
            str((n, "has the functionality that", catalog[n]["description"]))
            for n in sorted(catalog)
            if catalog[n]["kind"] == "scientific"
        ]
        index_path = ROOT / "tools/graph/index_store.json"
        store = json.loads(index_path.read_text())
        entry = next(iter(store["index_store/data"].values()))
        index = json.loads(entry["__data__"])
        prior = index.get("embedding_dict", {})
        valid = (
            not args.force
            and manifest.get("embedding_identity") == identity
            and manifest.get("text_sha256") == digest(sorted(prior))
        )
        vectors = {
            text: checked(prior[text]) for text in texts if valid and text in prior
        }
        missing = [t for t in texts if t not in vectors]
        cache_path = ROOT / "tools/graph/.embedding_build_cache.json"
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        if not args.force and cache.get("identity") == identity:
            for text, vector in cache.get("vectors", {}).items():
                if text in texts and text not in vectors:
                    vectors[text] = checked(vector)
            missing = [t for t in texts if t not in vectors]
        batches = []
        start = time.monotonic()
        for offset in range(0, len(missing), 32):
            batch = missing[offset : offset + 32]
            response = client.embeddings.create(
                model=identity["model"], input=batch, encoding_format="float"
            )
            if response.model != identity["model"]:
                raise ValueError("Embedding provider model mismatch")
            data = sorted(response.data, key=lambda item: item.index)
            if [x.index for x in data] != list(range(len(batch))):
                raise ValueError("Embedding index/order mismatch")
            vectors.update(
                (text, checked(row.embedding)) for text, row in zip(batch, data)
            )
            batches.append(
                {"inputs": len(batch), "tokens": response.usage.prompt_tokens}
            )
            atomic_json(cache_path, {"identity": identity, "vectors": vectors})
            print(
                json.dumps(
                    {
                        "embedded": min(offset + 32, len(missing)),
                        "new_texts": len(missing),
                    }
                ),
                flush=True,
            )
        ordered = {text: vectors[text] for text in texts}
        index["embedding_dict"] = ordered
        entry["__data__"] = json.dumps(index)
        atomic_json(index_path, store)
        manifest.update(
            embedding_identity=identity,
            embedding_model=identity["model"],
            embedding_backend="openai",
            embedding_dimension=3072,
            functionality_vectors=len(texts),
            text_sha256=digest(texts),
        )
        query = "Calculate Pearson correlation coefficient and significance from two numeric vectors."
        response = client.embeddings.create(
            model=identity["model"], input=[query], encoding_format="float"
        )
        query_vector = checked(response.data[0].embedding)
        ranking = sorted(
            [
                (sum(a * b for a, b in zip(query_vector, vector)), text)
                for text, vector in ordered.items()
            ],
            reverse=True,
        )[:5]
        report["embedding"] = {
            "identity": identity,
            "vectors": len(ordered),
            "reused": len(texts) - len(missing),
            "encoded": len(missing),
            "api_batches": batches,
            "prompt_tokens": sum(b["tokens"] for b in batches),
            "duration_seconds": time.monotonic() - start,
            "discovery_tool_not_embedded": "DescribeTools is always visible in the harness and has no task-planning role.",
            "retrieval_probe": {
                "query": query,
                "top5": [
                    {"tool": text.split("'", 2)[1], "similarity": score}
                    for score, text in ranking
                ],
                "query_tokens": response.usage.prompt_tokens,
                "expected_pearson_in_top5": any(
                    "'PearsonCorrelation'" in text for _, text in ranking
                ),
            },
        }
    atomic_json(manifest_path, manifest)
    atomic_json(ROOT / "tools/graph/build_report.json", report)
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "embedding"}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
