"""Index a frozen catalogue and flag candidates for a source-based overlap audit.

Similarity scores only select pairs for review; they are never duplicate verdicts.
No scientific function is imported or executed.
"""

import argparse
import ast
from collections import Counter, defaultdict
import copy
import hashlib
import json
import math
from pathlib import Path
import re


def tokens(text):
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return [
        x
        for x in re.findall(r"[a-z][a-z0-9]+", text.lower())
        if x
        not in {
            "the",
            "and",
            "for",
            "from",
            "with",
            "this",
            "that",
            "tool",
            "return",
            "returns",
            "input",
            "output",
            "get",
            "calculate",
            "compute",
            "by",
            "to",
            "of",
            "as",
            "in",
            "str",
            "list",
            "dict",
            "none",
            "bool",
            "float",
            "int",
        }
    ]


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return prefix + "." + node.attr if prefix else node.attr
    return ""


def catalog_scope(catalog):
    """Read either catalog generation without treating kind as a discipline."""
    tools = catalog["tools"]
    scored = sum(name != "DescribeTools" for name in tools)
    return {
        "registered_tools": len(tools),
        "tool_count": len(tools),
        "scored_tool_count": scored,
        "metadata_lookup_tool_count": len(tools) - scored,
        "graph_tool_count": sum(
            spec.get("indexing", {}).get("graph", name != "DescribeTools")
            for name, spec in tools.items()
        ),
        "embedding_tool_count": sum(
            spec.get("indexing", {}).get("embedding", name != "DescribeTools")
            for name, spec in tools.items()
        ),
        "scientific_tools": scored,
        "discovery_tools": len(tools) - scored,
        "existing_aliases": len(catalog.get("aliases", {})),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--audit-root", type=Path, required=True)
    a = p.parse_args()
    root = a.audit_root
    catalog = json.loads((root / "catalog_snapshot.json").read_text())
    source_root = root / "source_snapshot"
    modules = {}
    inventory = {}
    bindings = defaultdict(list)
    bodies = defaultdict(list)
    for name, spec in catalog["tools"].items():
        file = spec["source"]["file"]
        if file not in modules:
            tree = ast.parse((source_root / file).read_text())
            modules[file] = {
                n.name: n
                for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
        fn = modules[file][spec["source"]["function"]]
        body = copy.deepcopy(fn)
        body.name = "TOOL_FUNCTION"
        if (
            body.body
            and isinstance(body.body[0], ast.Expr)
            and isinstance(body.body[0].value, ast.Constant)
            and isinstance(body.body[0].value.value, str)
        ):
            body.body.pop(0)
        digest = hashlib.sha256(
            ast.dump(body, include_attributes=False).encode()
        ).hexdigest()
        calls = sorted(
            {
                dotted(n.func)
                for n in ast.walk(fn)
                if isinstance(n, ast.Call) and dotted(n.func)
            }
        )
        local_helpers = sorted(
            {c for c in calls if "." not in c and c in modules[file] and c != fn.name}
        )
        binding = file + ":" + fn.name
        bindings[binding].append(name)
        bodies[digest].append(name)
        inventory[name] = {
            "name": name,
            "domain": spec["domain"],
            "kind": spec["kind"],
            "description": spec["description"],
            "call_signature": spec["call_signature"],
            "source": {
                "file": file,
                "function": fn.name,
                "line": fn.lineno,
                "end_line": fn.end_lineno,
                "sha256": spec["source"]["sha256"],
            },
            "called_functions": calls,
            "same_file_helpers": local_helpers,
            "ast_body_sha256": digest,
            "input_parameters": [q["name"] for q in spec["parameters"]],
            "aliases": spec.get("aliases", []),
        }
    documents = {
        k: Counter(
            tokens(
                v["name"]
                + " "
                + v["description"]
                + " "
                + " ".join(v["called_functions"])
            )
        )
        for k, v in inventory.items()
    }
    frequency = Counter(t for doc in documents.values() for t in doc)
    n = len(documents)
    vectors = {
        k: {
            t: (1 + math.log(count)) * (math.log((n + 1) / (frequency[t] + 1)) + 1)
            for t, count in d.items()
        }
        for k, d in documents.items()
    }
    norms = {k: math.sqrt(sum(x * x for x in v.values())) for k, v in vectors.items()}
    names = sorted(inventory)
    top = defaultdict(list)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            x, y = vectors[left], vectors[right]
            small, large = (x, y) if len(x) < len(y) else (y, x)
            score = (
                sum(w * large.get(k, 0) for k, w in small.items())
                / (norms[left] * norms[right])
                if norms[left] * norms[right]
                else 0
            )
            exact = (
                inventory[left]["source"]["file"] == inventory[right]["source"]["file"]
                and inventory[left]["source"]["function"]
                == inventory[right]["source"]["function"]
            )
            if score < 0.24 and not exact:
                continue
            pair = {
                "left": left,
                "right": right,
                "candidate_score": round(score, 5),
                "same_binding": exact,
                "cross_domain": inventory[left]["domain"] != inventory[right]["domain"],
            }
            top[left].append(pair)
            top[right].append(pair)
    candidates = {}
    for key, pairs in top.items():
        for pair in sorted(
            pairs, key=lambda x: (x["same_binding"], x["candidate_score"]), reverse=True
        )[:8]:
            candidates[(pair["left"], pair["right"])] = pair
    output = {
        "scope": catalog_scope(catalog),
        "tools": inventory,
        "same_execution_binding_groups": [
            {"binding": k, "members": v} for k, v in bindings.items() if len(v) > 1
        ],
        "same_ast_body_groups": [
            {"ast_body_sha256": k, "members": v}
            for k, v in bodies.items()
            if len(v) > 1
        ],
        "candidate_generation": "Description/name/call-symbol TF-IDF cosine, top8per tool above0.24, plus same bindings. Candidate scores are not duplicate verdicts.",
        "candidate_pairs": sorted(
            candidates.values(),
            key=lambda r: (r["same_binding"], r["candidate_score"]),
            reverse=True,
        ),
    }
    (root / "structural_inventory.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "tools": len(inventory),
                "same_binding_groups": len(output["same_execution_binding_groups"]),
                "same_body_groups": len(output["same_ast_body_groups"]),
                "candidate_pairs": len(output["candidate_pairs"]),
                "cross_domain_candidates": sum(
                    p["cross_domain"] for p in output["candidate_pairs"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
