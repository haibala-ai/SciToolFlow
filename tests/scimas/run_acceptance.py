"""Reproducible phase-one integration checks using real, bounded scientific calls.

This is a test driver, not the SciMas executor or a benchmark reference generator.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from tools import ToolCatalog, execute
from src.utils.io import atomic_json
from baselines.scimas.task_graph import TaskGraph
from baselines.scimas.validation import validate_graph


def run(output):
    catalog = ToolCatalog()
    task = {
        "id": "SCIMAS-ACCEPTANCE",
        "question": "Report inverse, singular values and identity-product check. For screening, require condition number <= 1.5.",
        "inputs": {"matrix": [[2.0, 0.0], [0.0, 4.0]], "molecules": ["CCO", "CO"]},
    }
    task_binding = {"kind": "task", "path": ["inputs", "matrix"]}
    nodes = [
        {
            "id": "inverse",
            "tool": "MatrixInverse",
            "purpose": "Invert matrix",
            "object": "matrix",
            "arguments": {"values": task_binding},
        },
        {
            "id": "svd",
            "tool": "MatrixSVD",
            "purpose": "Independent factorization",
            "object": "matrix",
            "arguments": {"values": task_binding},
        },
        {
            "id": "product",
            "tool": "MatrixMultiply",
            "purpose": "Check inverse",
            "object": "matrix",
            "arguments": {
                "left": task_binding,
                "right": {"kind": "node", "node": "inverse", "path": ["inverse"]},
            },
        },
    ]
    requirements = [
        {
            "id": "report",
            "description": "Report all requested matrix results",
            "evidence": "Report inverse, singular values and identity-product check.",
            "mode": "complete",
        }
    ]
    plan = {
        "nodes": nodes,
        "deliverables": [
            {
                "requirement": "report",
                "nodes": ["inverse", "svd", "product"],
                "description": "Complete numerical report",
            }
        ],
    }
    graph = TaskGraph.create(task, requirements, plan, catalog, "custom")
    validation = validate_graph(graph, catalog)
    assert validation["valid"], validation
    evidence = {}
    calls = []
    groups = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        while len(evidence) < len(nodes):
            ready = graph.ready(evidence, catalog)
            assert ready, "No ready calls in valid numerical example"
            groups.append(ready)
            arguments = {nid: graph.arguments(nid, evidence, catalog) for nid in ready}
            started = time.monotonic()
            futures = {
                nid: pool.submit(
                    execute, graph.node(nid)["tool"], arguments[nid], timeout=60
                )
                for nid in ready
            }
            for nid, future in futures.items():
                response = future.result()
                evidence[nid] = graph.accept_result(
                    nid, response, catalog, environment=response.get("environment")
                )
                calls.append(
                    {
                        "node": nid,
                        "arguments": arguments[nid],
                        "response": response,
                        "elapsed_since_group_start": time.monotonic() - started,
                    }
                )
    assert groups[0] == ["inverse", "svd"] and groups[1] == ["product"]
    product = evidence["product"]["output"]["product"]
    assert all(
        abs(product[i][j] - float(i == j)) < 1e-12 for i in range(2) for j in range(2)
    )
    # A failed computation cannot serve as a scientific rejection.
    failed = execute("MatrixInverse", {"values": [[1, 2], [2, 4]]}, timeout=60)
    assert failed["status"] != "success"
    try:
        graph.accept_result("inverse", failed, catalog)
    except ValueError:
        rejected = True
    else:
        rejected = False
    assert rejected
    # Real template inputs become separately evidenced tool calls.
    req = [
        {
            "id": "convert",
            "description": "Convert public input structures",
            "evidence": "molecules",
            "mode": "complete",
        }
    ]
    template = {
        "id": "convert",
        "tool": "SMILESToInChI",
        "purpose": "Convert each structure",
        "object": "molecule",
        "for_each": {"kind": "task", "path": ["inputs", "molecules"]},
        "arguments": {"smiles": {"kind": "item", "path": []}},
    }
    mapped = TaskGraph.create(
        task,
        req,
        {
            "nodes": [template],
            "deliverables": [
                {
                    "requirement": "convert",
                    "nodes": ["convert"],
                    "description": "Identifiers",
                }
            ],
        },
        catalog,
        "custom",
    )
    assert validate_graph(mapped, catalog)["valid"]
    expanded, _ = mapped.expand("convert", {}, catalog)
    template_calls = []
    for nid in expanded.ready({}, catalog):
        args = expanded.arguments(nid, {}, catalog)
        response = execute("SMILESToInChI", args, timeout=60)
        result = expanded.accept_result(nid, response, catalog)
        assert result["output"]["inchi"].startswith("InChI=")
        template_calls.append({"node": nid, "arguments": args, "response": response})
    assert (
        len(template_calls) == 2
        and template_calls[0]["response"]["output"]["inchi"]
        != template_calls[1]["response"]["output"]["inchi"]
    )
    # Real scientific rejection differs from runtime failure.
    screen_nodes = [
        nodes[0],
        {
            **nodes[2],
            "when": {
                "op": "le",
                "left": {
                    "kind": "node",
                    "node": "inverse",
                    "path": ["condition_number"],
                },
                "right": {"kind": "literal", "value": 1.5},
                "evidence": "require condition number <= 1.5",
            },
        },
    ]
    screen_req = [
        {
            "id": "screen",
            "description": "Conditional product check",
            "evidence": "For screening, require condition number <= 1.5.",
            "mode": "screen",
        }
    ]
    screen = TaskGraph.create(
        task,
        screen_req,
        {
            "nodes": screen_nodes,
            "deliverables": [
                {
                    "requirement": "screen",
                    "nodes": ["inverse", "product"],
                    "description": "Screening evidence",
                }
            ],
        },
        catalog,
        "custom",
    )
    assert validate_graph(screen, catalog)["valid"]
    observed = screen.accept_result("inverse", calls[0]["response"], catalog)
    approval = {"product": screen.node_identity("product")}
    assert (
        screen.condition_state(
            "product", {"inverse": observed}, approved_gates=approval
        )
        is False
    )
    assert (
        screen.condition_state("product", {"inverse": failed}, approved_gates=approval)
        is None
    )
    report = {
        "status": "passed",
        "driver": "phase-one integration fixture, not a full agent runtime",
        "graph": graph.document(),
        "validation": validation,
        "ready_groups": groups,
        "calls": calls,
        "rejected_failure": failed,
        "expanded_graph": expanded.document(),
        "template_calls": template_calls,
        "screening": {
            "valid_negative": False,
            "failed_call": None,
            "review_approval_basis": "literal numeric condition, manually reviewed",
        },
        "scientific_calls": len(calls) + 1 + len(template_calls),
    }
    atomic_json(output, report)
    return {
        "status": "passed",
        "scientific_calls": report["scientific_calls"],
        "output": str(output),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
