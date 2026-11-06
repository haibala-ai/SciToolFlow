"""SciMas-only knowledge queries over explicit ports and planning annotations."""

import gzip
import hashlib
import json
from collections import defaultdict, OrderedDict
from pathlib import Path
import time
from copy import deepcopy
from tools.catalog import ToolCatalog
from tools.runtime.scope import tool_allowed
from .task_graph import digest
from .validation import compatible
from src.models.embedding_profiles import graph_root, validate_identity

# Share the transport/cache only; the SciToolAgent graph and search policy are not used.
from baselines.scitoolagent.retrieval import Embeddings, RetrievalError, dot, unit


def fresh_queries(queries, completed):
    """Skip repeated/blank queries without conflating scientific letter case."""
    fresh, skipped = [], []
    for query in queries:
        key = " ".join(query.split())
        if not key or key in completed:
            skipped.append(query)
        else:
            completed.add(key)
            fresh.append(query)
    return fresh, skipped


def embedding_usage_since(embedding, baseline):
    """Per-invocation counters when a retriever is reused sequentially."""
    usage = {}
    for key, value in embedding.stats.items():
        previous = baseline.get(key)
        if type(value) in (int, float):
            previous = previous if type(previous) in (int, float) else 0
            usage[key] = value - previous if value >= previous else value
        elif isinstance(value, list):
            offset = len(previous) if isinstance(previous, list) and len(value) >= len(previous) else 0
            usage[key] = deepcopy(value[offset:])
        else:
            usage[key] = deepcopy(value)
    return usage


class ToolKnowledge:
    def __init__(self, catalog=None, folder=None, embedding=None, allowed=None):
        self.catalog = catalog or ToolCatalog()
        self.folder = Path(folder or graph_root(self.catalog.root) / "scimas")
        self.manifest = json.loads((self.folder / "manifest.json").read_text())
        self.graph = json.loads((self.folder / "graph.json").read_text())
        raw = (self.folder / "embeddings.json.gz").read_bytes()
        annotations = json.loads((self.folder / "annotations.json").read_text())
        if (
            digest(self.graph) != self.manifest["graph_sha256"]
            or digest(self.catalog.tools) != self.manifest["catalog_sha256"]
            or digest(annotations) != self.manifest["annotations_sha256"]
            or hashlib.sha256(raw).hexdigest() != self.manifest["embedding_file_sha256"]
        ):
            raise ValueError("Stale/corrupt SciMas KG; rebuild its artifacts")
        index = json.loads(gzip.decompress(raw))
        if index["identity"] != self.manifest["embedding_identity"]:
            raise ValueError("SciMas vector identity mismatch")
        validate_identity(index["identity"])
        self.allowed = allowed or tool_allowed
        self.tools = {n: r for n, r in self.graph["tools"].items() if self.allowed(n)}
        dimensions = index["identity"]["dimension"]
        self.vectors = {
            n: unit(v, dimensions)
            for n, v in index["vectors"].items()
            if n in self.tools
        }
        if set(self.vectors) != set(self.tools):
            raise ValueError("Incomplete SciMas functionality index")
        self.embedding = embedding or Embeddings(index["identity"], self.catalog.root)
        self._connection_cache = OrderedDict()
        self.inputs, self.outputs = defaultdict(list), defaultdict(list)
        for name, record in self.tools.items():
            for direction, target in (
                ("inputs", self.inputs),
                ("outputs", self.outputs),
            ):
                for port in record["ports"][direction]:
                    for concept in port.get("concepts", [port["concept"]]):
                        target[concept].append(port)

    def describe(self, names):
        """Full public contract plus SciMas planning information; DescribeTools stays callable."""
        names = [names] if isinstance(names, str) else names
        result = {}
        for requested in names:
            canonical = self.catalog.canonical(requested)
            if canonical in self.tools:
                result[canonical] = self.tools[canonical]
            elif (
                canonical == "DescribeTools"
                and canonical in self.catalog.tools
                and self.allowed(canonical)
            ):
                result[canonical] = {
                    "contract": self.catalog.describe(canonical)["tools"][canonical],
                    "planning": {"graph_indexed": False, "scientific_path": False},
                }
            else:
                raise ValueError("Unknown, retired or excluded tool: " + requested)
        return deepcopy(result)

    def alternatives(self, name, *, limit=12):
        """Find repair candidates by shared outputs, never assert scientific equivalence."""
        source = self.tools[name]
        concepts = {p["concept"] for p in source["ports"]["outputs"]}
        scores = {}
        for concept in concepts:
            for port in self.outputs[concept]:
                if port["tool"] != name:
                    scores.setdefault(port["tool"], set()).add(concept)
        ordered = sorted(scores, key=lambda n: (-len(scores[n]), n))[:limit]
        return [
            {
                "tool": n,
                "shared_output_concepts": sorted(scores[n]),
                "status": "candidate_only_not_method_equivalence",
                "required_review": [
                    "user_specified_method",
                    "scientific_estimand",
                    "input_availability",
                    "units",
                    "output_completeness",
                ],
                "planning": deepcopy(self.tools[n]["planning"]),
            }
            for n in ordered
        ]

    def planning_view(self, names):
        """Keep full argument/result schemas, omit duplicate documentation and schemas."""
        view = self.describe(names)
        for record in view.values():
            record["contract"] = {
                k: v
                for k, v in record["contract"].items()
                if k
                in {
                    "name",
                    "domain",
                    "description",
                    "call_signature",
                    "input_schema",
                    "output_schema",
                    "output_encoding",
                    "limitations",
                    "failure_feedback",
                }
            }
            if "ports" in record:
                record["ports"] = {
                    d: [
                        {
                            k: v
                            for k, v in p.items()
                            if k
                            not in {
                                "schema",
                                "contract_sha256",
                                "type",
                                "direction",
                                "tool",
                            }
                        }
                        for p in ports
                    ]
                    for d, ports in record["ports"].items()
                }
        return view

    def connections(self, name, direction="predecessors", *, limit=40, relevance=None):
        if direction not in {"predecessors", "successors"}:
            raise ValueError("Unknown connection direction")
        if limit < 1:
            raise ValueError("Connection limit must be positive")
        key = (name, direction)
        if key not in self._connection_cache:
            self._connection_cache[key] = self._connection_candidates(name, direction)
            if len(self._connection_cache) > 64:
                self._connection_cache.popitem(last=False)
        self._connection_cache.move_to_end(key)
        # Relevance is query-dependent; never cache the ranking or expose mutable
        # cached records to callers. The cache belongs to this validated KG only.
        candidates = list(self._connection_cache[key])
        other_key = "source_tool" if direction == "predecessors" else "target_tool"
        candidates.sort(
            key=lambda x: (
                -(relevance or {}).get(x[other_key], 0),
                x["source_tool"],
                x["target_tool"],
                x["source_port"],
                x["target_port"],
            )
        )
        return {
            "connections": deepcopy(candidates[:limit]),
            "total": len(candidates),
            "truncated": len(candidates) > limit,
        }

    def _connection_candidates(self, name, direction):
        record = self.tools[name]
        own_direction = "inputs" if direction == "predecessors" else "outputs"
        index = self.outputs if direction == "predecessors" else self.inputs
        candidates = []
        for port in record["ports"][own_direction]:
            others = {
                p["id"]: p
                for concept in port.get("concepts", [port["concept"]])
                for p in index[concept]
            }
            for other in others.values():
                if other["tool"] == name:
                    continue
                out, inp = (
                    (other, port) if direction == "predecessors" else (port, other)
                )
                if not compatible(out["schema"], inp["schema"]):
                    continue
                mismatches = [
                    key
                    for key in ("unit", "method", "object_id")
                    if out.get(key) is not None
                    and inp.get(key) is not None
                    and out[key] != inp[key]
                ]
                if mismatches:
                    continue
                candidates.append(
                    {
                        "source_tool": out["tool"],
                        "source_port": out["id"],
                        "output_path": out["path"],
                        "decoded": out.get("decoded", False),
                        "target_tool": inp["tool"],
                        "target_port": inp["id"],
                        "input_parameter": inp["parameter"],
                        "concepts": sorted(
                            set(out.get("concepts", [out["concept"]]))
                            & set(inp.get("concepts", [inp["concept"]]))
                        ),
                        "status": "candidate_requires_scientific_review",
                        "conditions": [
                            p["condition"] for p in (out, inp) if p.get("condition")
                        ],
                        "checks": [
                            "object_identity",
                            "units",
                            "method",
                            "completeness",
                            "actual_shape",
                        ],
                        "provenance": [out["contract_sha256"], inp["contract_sha256"]],
                    }
                )
        return candidates

    def search(self, queries, deadline, *, top_k=5, depth=1, max_tools_per_query=12):
        if (
            not queries
            or not 1 <= len(queries) <= 24
            or not 1 <= top_k <= max_tools_per_query
            or not 0 <= depth <= 3
        ):
            raise ValueError("Invalid bounded subtask retrieval configuration")
        if time.monotonic() >= deadline:
            raise TimeoutError("Planning deadline")
        vectors = self.embedding.encode(queries, deadline)
        if len(vectors) != len(queries):
            raise RetrievalError("Incomplete query embeddings")
        selected, reports = set(), []
        for query, vector in zip(queries, vectors):
            q = unit(vector, self.manifest["embedding_identity"]["dimension"])
            scores = {n: dot(q, v) for n, v in self.vectors.items()}
            seeds = sorted(scores, key=lambda n: (-scores[n], n))[:top_k]
            found, frontier, links = set(seeds), set(seeds), []
            for _ in range(depth):
                next_frontier = set()
                for name in sorted(frontier):
                    for direction in ("predecessors", "successors"):
                        result = self.connections(
                            name, direction, limit=40, relevance=scores
                        )
                        links.extend(result["connections"])
                        next_frontier.update(
                            (
                                c["source_tool"]
                                if direction == "predecessors"
                                else c["target_tool"]
                            )
                            for c in result["connections"]
                        )
                next_frontier -= found
                next_frontier = set(
                    sorted(next_frontier, key=lambda n: (-scores[n], n))[
                        :max_tools_per_query
                    ]
                )
                found |= next_frontier
                frontier = next_frontier
            ranked = seeds + sorted(found - set(seeds), key=lambda n: (-scores[n], n))
            chosen = ranked[:max_tools_per_query]
            selected.update(chosen)
            reports.append(
                {
                    "query": query,
                    "seeds": seeds,
                    "selected": chosen,
                    "candidate_connections": [
                        c
                        for c in links
                        if c["source_tool"] in chosen and c["target_tool"] in chosen
                    ],
                    "truncated": len(ranked) > len(chosen),
                }
            )
        return {
            "tools": self.planning_view(sorted(selected)),
            "queries": reports,
            "kg_sha256": self.manifest["graph_sha256"],
            "embedding_usage": dict(self.embedding.stats),
        }
