"""Upstream-style semantic seeds, typed graph expansion and contextual reranking.

Adapted from HICAI-ZJU/SciToolAgent/scripts/custom_kg_retrievers.py,
commit ac1cf19fcef84e69f149db6da424afe4e9b2f11f (MIT, Jing Yu 2024).
No task answers or reference traces are read.
"""

import ast
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import time

from src.utils.paths import project_root, load_environment
from src.utils.io import atomic_json


class RetrievalError(RuntimeError):
    pass


def unit(vector, dimensions):
    if len(vector) != dimensions or any(
        isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
        for x in vector
    ):
        raise RetrievalError("Invalid embedding dimensions or values")
    norm = math.sqrt(math.fsum(x * x for x in vector))
    if not norm:
        raise RetrievalError("Zero embedding")
    return [x / norm for x in vector]


def dot(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


class Embeddings:
    """Use exactly the index model/provider; cache by identity and text hash."""

    def __init__(self, identity, root=None):
        self.root = Path(root or project_root())
        self.identity = identity
        self.dimensions = identity["dimension"]
        self.cache = self.root / ".local/cache/scitoolagent_embeddings"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.stats = {
            "requests": 0,
            "retries": 0,
            "texts": 0,
            "cached_texts": 0,
            "prompt_tokens": 0,
        }

    def request_batch(self, client, base, key, batch, deadline):
        """Retry only transport/rate-limit/transient server errors, within the task deadline."""
        import requests

        for attempt in range(3):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RetrievalError("Task deadline during embedding retrieval")
            self.stats["requests"] += 1
            try:
                response = client.post(
                    base + "/embeddings",
                    headers={"Authorization": "Bearer " + key},
                    json={
                        "model": self.identity["model"],
                        "input": batch,
                        "dimensions": self.dimensions,
                    },
                    timeout=min(60, remaining),
                )
            except requests.RequestException as error:
                failure = "Embedding transport failure: " + type(error).__name__
                retryable = True
            else:
                if response.status_code == 200:
                    try:
                        return response.json()
                    except ValueError:
                        raise RetrievalError(
                            "Embedding API returned invalid JSON"
                        ) from None
                failure = "Embedding API HTTP " + str(response.status_code)
                retryable = response.status_code in {408, 429, 500, 502, 503, 504}
            if not retryable or attempt == 2:
                raise RetrievalError(failure)
            pause = min(2**attempt, deadline - time.monotonic())
            if pause <= 0:
                raise RetrievalError("Task deadline during embedding retrieval")
            self.stats["retries"] += 1
            time.sleep(pause)

    def encode(self, texts, deadline):
        load_environment()
        base = (
            os.getenv("SCITOOL_EMBEDDING_API_BASE")
            or os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPENAI_API_BASE")
            or self.identity["api_base"]
        ).rstrip("/")
        if base != self.identity["api_base"].rstrip("/"):
            raise RetrievalError(
                "Query embedding provider differs from the frozen index identity"
            )
        key = os.getenv("SCITOOL_EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
        unique = list(dict.fromkeys(texts))
        values = {}
        missing = []
        paths = {}
        for text in unique:
            digest = hashlib.sha256(
                json.dumps([self.identity, text], sort_keys=True).encode()
            ).hexdigest()
            paths[text] = self.cache / (digest + ".json")
            if paths[text].exists():
                row = json.loads(paths[text].read_text())
                values[text] = unit(row["vector"], self.dimensions)
                self.stats["cached_texts"] += 1
            else:
                missing.append(text)
        if missing and not key:
            raise RetrievalError(
                "Configure SCITOOL_EMBEDDING_API_KEY in .local/credentials/services.env; no lexical fallback is used"
            )
        if missing:
            import requests

            with requests.Session() as client:
                for offset in range(0, len(missing), 32):
                    batch = missing[offset : offset + 32]
                    payload = self.request_batch(client, base, key, batch, deadline)
                    rows = payload.get("data", [])
                    if len(rows) != len(batch) or {
                        row.get("index") for row in rows
                    } != set(range(len(batch))):
                        raise RetrievalError(
                            "Embedding response indices are incomplete"
                        )
                    self.stats["texts"] += len(batch)
                    self.stats["prompt_tokens"] += (payload.get("usage") or {}).get(
                        "prompt_tokens", 0
                    )
                    for row in rows:
                        text = batch[row["index"]]
                        values[text] = unit(row["embedding"], self.dimensions)
                        atomic_json(
                            paths[text],
                            {"identity": self.identity, "vector": values[text]},
                        )
        return [values[t] for t in texts]


class GraphRetriever:
    RELATIONS = {
        "inputs",
        "outputs",
        "is the input of",
        "is the output of",
        "has the functionality that",
    }
    INVALID_PAIRS = {("inputs", "is the input of"), ("outputs", "is the output of")}

    def __init__(self, catalog, config, embedding=None, allowed=None):
        self.catalog = catalog
        self.config = config
        root = catalog.root
        self.graph = json.loads((root / "tools/graph/graph_store.json").read_text())[
            "graph_dict"
        ]
        manifest = json.loads(
            (root / "tools/graph/tool_foundation_manifest.json").read_text()
        )
        store = json.loads((root / "tools/graph/index_store.json").read_text())
        index = json.loads(next(iter(store["index_store/data"].values()))["__data__"])
        identity = manifest["embedding_identity"]
        if (
            identity["model"] != "text-embedding-3-large"
            or identity["dimension"] != 3072
        ):
            raise RetrievalError("Unexpected functionality embedding identity")
        self.embedding = embedding or Embeddings(identity, root)
        if allowed is None:
            from tools.runtime.scope import tool_allowed

            allowed = tool_allowed
        self.vectors = {}
        self.texts = {}
        indexed_names = set(catalog.indexed_tools("embedding"))
        for text, vec in index["embedding_dict"].items():
            name, relation, _ = ast.literal_eval(text)
            if name in catalog.tools and name in indexed_names and allowed(name):
                self.vectors[name] = unit(vec, identity["dimension"])
                self.texts[name] = text
        if not self.vectors:
            raise RetrievalError(
                "No callable scientific candidates in this execution scope"
            )

    def neighbors(self, seed):
        queue = deque([(seed, (), 0)])
        seen = set()
        found = set()
        edges = 0
        while queue and edges < self.config["graph_edge_limit"]:
            node, history, depth = queue.popleft()
            if depth >= self.config["graph_depth"]:
                continue
            for relation, target in self.graph.get(node, []):
                if relation not in self.RELATIONS:
                    continue
                edges += 1
                if edges > self.config["graph_edge_limit"]:
                    break
                if history and (history[-1], relation) in self.INVALID_PAIRS:
                    continue
                state = (target, relation, depth + 1)
                if state in seen:
                    continue
                seen.add(state)
                if target in self.vectors and target != seed:
                    found.add(target)
                queue.append((target, history + (relation,), depth + 1))
        return found

    def retrieve(self, question, deadline):
        started = time.monotonic()
        q = self.embedding.encode([question], deadline)[0]
        scores = {n: dot(q, v) for n, v in self.vectors.items()}
        seeds = sorted(scores, key=lambda n: (-scores[n], n))[
            : self.config["similarity_top_k"]
        ]
        weights = {n: scores[n] for n in seeds}
        contexts = []
        pairs = []
        for seed in seeds:
            related = sorted(self.neighbors(seed), key=lambda n: (-scores[n], n))[
                : self.config["context_candidates_per_seed"]
            ]
            for name in related:
                contexts.append(
                    self.texts[name] + " There is an existing tool: " + self.texts[seed]
                )
                pairs.append((seed, name))
        if contexts:
            vectors = self.embedding.encode(contexts, deadline)
            by_seed = {seed: [] for seed in seeds}
            for (seed, name), vector in zip(pairs, vectors):
                by_seed[seed].append((dot(q, vector), name))
            for seed, candidates in by_seed.items():
                for similarity, name in sorted(candidates, key=lambda x: (-x[0], x[1]))[
                    : self.config["similarity_top_k"]
                ]:
                    weights[name] = weights.get(name, 0) + scores[seed] * similarity
        names = sorted(weights, key=lambda n: (-weights[n], n))[
            : self.config["max_tools"]
        ]
        tools = []
        for name in names:
            spec = self.catalog.tools[name]
            triples = [
                [name, r, t] for r, t in self.graph.get(name, []) if r in self.RELATIONS
            ]
            tools.append(
                {
                    "name": name,
                    "description": spec["description"],
                    "graph_triples": triples,
                    "retrieval_score": weights[name],
                }
            )
        return {
            "tools": tools,
            "seed_tools": seeds,
            "context_pairs": len(contexts),
            "seconds": time.monotonic() - started,
            "algorithm": "semantic seeds + typed graph expansion + contextual embedding rerank + weighted accumulation",
            "embedding_usage": dict(self.embedding.stats),
        }
