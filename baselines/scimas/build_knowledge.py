"""Build the independent SciMas port graph from public contracts and annotations.

Existing functionality vectors are reused by exact text and provider identity;
SciToolAgent graph files are never modified or read by the SciMas query runtime.
"""

import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
from tools.catalog import ToolCatalog
from tools.catalog.discovery import PUBLIC_FIELDS
from tools.catalog.ports import validate_ports
from src.utils.io import atomic_json
from .task_graph import digest
from .validation import output_schema, path_schema
from baselines.scitoolagent.retrieval import unit


def build(catalog, folder=None):
    root = catalog.root
    folder = Path(folder or root / "tools/graph/scimas")
    folder.mkdir(parents=True, exist_ok=True)
    annotation_path = folder / "annotations.json"
    source_annotations = (
        annotation_path
        if annotation_path.exists()
        else root / "tools/graph/scimas/annotations.json"
    )
    annotations = (
        json.loads(source_annotations.read_text())
        if source_annotations.exists()
        else {"tools": {}}
    )
    indexed = catalog.indexed_tools("graph")
    if set(annotations["tools"]) - set(indexed):
        raise ValueError("Annotations reference excluded or missing tools")
    nodes, edges, records = {}, [], {}
    for name, spec in sorted(indexed.items()):
        validate_ports(name, spec)
        source = spec.get("source", {})
        if (
            source.get("file")
            and hashlib.sha256((root / source["file"]).read_bytes()).hexdigest()
            != source["sha256"]
        ):
            raise ValueError("Source changed; review contract before building: " + name)
        public = {k: spec[k] for k in (*PUBLIC_FIELDS, "failure_feedback") if k in spec}
        contract_sha = digest(spec)
        annotation = annotations["tools"].get(name)
        if annotation and annotation.get("contract_sha256") != contract_sha:
            raise ValueError("Stale SciMas annotation: " + name)
        execution = spec["execution"]
        encoding = spec.get("output_encoding", {})
        planning = {
            "basis": "derived_from_current_contract",
            "required_inputs": spec["input_schema"].get("required", []),
            "output_access": (
                "reviewer_extraction"
                if encoding.get("decoded_type") == "text"
                else (
                    "declared_json_decode"
                    if encoding.get("decoded_type") in {"json_object", "json_array"}
                    else "native_fields"
                )
            ),
            "environment": execution.get("environment"),
            "declared_resources": execution.get("requires", []),
            "reuse_requirements": [
                "same_inputs_and_parameters",
                "same_tool_and_source_version",
                "same_environment_and_model",
                "valid_dependencies",
                "resource_content_identity",
            ],
            "cache_safe": "unknown",
            "parallel_safe": "unknown",
            "cost_class": "unknown",
            "scientific_substitution": "requires_task_specific_review",
            "limitations": spec.get("limitations", []),
        }
        if annotation:
            planning["reviewed_annotation"] = annotation
            planning.update(annotation.get("execution_hints", {}))
        tool_id = "tool:" + name
        nodes[tool_id] = {"type": "tool", "name": name, "domain": spec["domain"]}
        records[name] = {
            "contract": public,
            "contract_sha256": contract_sha,
            "planning": planning,
            "source_sha256": source.get("sha256"),
            "ports": {"inputs": [], "outputs": []},
        }
        for direction in ("inputs", "outputs"):
            ports = [dict(p) for p in spec["dataflow"][direction]]
            for enhancement in (annotation or {}).get("ports", {}).get(direction, []):
                identity_key = "parameter" if direction == "inputs" else "path"
                matches = [
                    p
                    for p in ports
                    if p.get(identity_key) == enhancement.get(identity_key)
                ]
                if matches:
                    matches[0]["source_concept"] = matches[0]["concept"]
                    matches[0].update(enhancement)
                else:
                    ports.append(dict(enhancement))
            for index, port in enumerate(ports):
                pid = f"port:{name}:{direction}:{index}"
                if direction == "inputs":
                    schema = spec["input_schema"]["properties"][port["parameter"]]
                else:
                    schema = path_schema(
                        output_schema(spec, port.get("decoded", False)),
                        port["path"],
                        allow_wildcards=True,
                    )
                record = {
                    **port,
                    "type": "port",
                    "tool": name,
                    "direction": direction,
                    "schema": schema,
                    "contract_sha256": contract_sha,
                }
                records[name]["ports"][direction].append({"id": pid, **record})
                nodes[pid] = record
                edges.append([tool_id, "has_" + direction + "_port", pid])
                for concept in port.get("concepts", [port["concept"]]):
                    cid = "concept:" + concept
                    nodes.setdefault(cid, {"type": "concept", "name": concept})
                    edges.append([pid, "represents", cid])
        annotation_constraints = (annotation or {}).get("constraints", [])
        for index, constraint in enumerate(annotation_constraints):
            cid = f"constraint:{name}:{index}"
            nodes[cid] = {
                "type": "constraint",
                **constraint,
                "tool": name,
                "contract_sha256": contract_sha,
            }
            edges.append([tool_id, "requires", cid])
    graph = {
        "schema_version": "scimas.tool_kg.v1",
        "catalog_sha256": digest(catalog.tools),
        "annotations_sha256": digest(annotations),
        "nodes": nodes,
        "edges": edges,
        "tools": records,
    }
    # Copy only identity-matching functionality vectors to a separate, compact index.
    prior = json.loads((root / "tools/graph/tool_foundation_manifest.json").read_text())
    store = json.loads((root / "tools/graph/index_store.json").read_text())
    index = json.loads(next(iter(store["index_store/data"].values()))["__data__"])
    vectors, texts = {}, {}
    for text, vector in index["embedding_dict"].items():
        name, relation, description = ast.literal_eval(text)
        if (
            name in records
            and relation == "has the functionality that"
            and description == indexed[name]["description"]
        ):
            vectors[name] = unit(vector, prior["embedding_identity"]["dimension"])
            texts[name] = text
    if set(vectors) != set(records):
        raise ValueError(
            "Functionality texts changed; rebuild the common source embeddings before importing"
        )
    embedding = {
        "identity": prior["embedding_identity"],
        "texts": texts,
        "vectors": vectors,
    }
    compressed = gzip.compress(
        json.dumps(embedding, separators=(",", ":"), allow_nan=False).encode(), mtime=0
    )
    temporary = folder / "embeddings.json.gz.tmp"
    temporary.write_bytes(compressed)
    temporary.replace(folder / "embeddings.json.gz")
    atomic_json(folder / "graph.json", graph)
    if not annotation_path.exists():
        atomic_json(annotation_path, annotations)
    manifest = {
        "schema_version": "scimas.tool_kg_manifest.v1",
        "tools": len(records),
        "ports": sum(v["type"] == "port" for v in nodes.values()),
        "nodes": len(nodes),
        "edges": len(edges),
        "graph_sha256": digest(graph),
        "catalog_sha256": graph["catalog_sha256"],
        "annotations_sha256": graph["annotations_sha256"],
        "embedding_file_sha256": hashlib.sha256(compressed).hexdigest(),
        "embedding_identity": embedding["identity"],
        "vectors": len(vectors),
        "reviewed_annotations": len(annotations["tools"]),
        "new_embedding_api_calls": 0,
        "embedding_text_basis": "unchanged_tool_functionality; enriched metadata is used in port queries and planning",
        "excluded": sorted(set(catalog.tools) - set(indexed)),
    }
    atomic_json(folder / "manifest.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(ToolCatalog(), args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
