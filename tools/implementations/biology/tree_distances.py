"""Bounded literal Newick tree geometry; no phylogeny inference or clock test."""

import hashlib
import math
import re


def parse_newick_tree_distances(newick_text: str) -> dict:
    """Parse one explicitly branch-length-labelled restricted Newick tree.

    Accepts unquoted ASCII labels [A-Za-z0-9_.-]+, unique labelled tips,
    polytomies, optional literal internal labels, and strictly positive finite
    float64 edge lengths on every nonroot node. The serialization root has
    absent or zero stem length. No quoted labels, comments, support inference,
    negative/zero ordinary edges, missing lengths, trees forest or topology
    repair. Root is only the supplied reference root, not inferred biological
    rooting. Bounds: <=100000 characters, 2..100 tips, <=200 total nodes and
    depth <=100. Return ordered explicit node/edge records, root-to-tip path
    lengths and the complete patristic tip-distance matrix in the original
    input branch units. No ultrametricity decision, time conversion, tree fit,
    trait prediction, ancestral inference or model selection is performed.
    """
    if not isinstance(newick_text, str) or not 1 <= len(newick_text) <= 100000:
        raise ValueError("newick_text must contain 1..100000 characters")
    if not newick_text.isascii():
        raise ValueError("Restricted Newick accepts ASCII only")
    text = newick_text.strip()
    pos = 0
    nodes = []
    children = []
    label_re = re.compile(r"[A-Za-z0-9_.-]+")
    length_re = re.compile(r"[+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")

    def whitespace():
        nonlocal pos
        while pos < len(text) and text[pos].isspace():
            pos += 1

    def read_node(parent, depth):
        nonlocal pos
        if depth > 100 or len(nodes) >= 200:
            raise ValueError("Tree exceeds depth100 or total200 nodes")
        whitespace()
        index = len(nodes)
        nodes.append(
            {"node_id": index, "parent_id": parent, "label": None, "branch_length": 0.0}
        )
        children.append([])
        if pos < len(text) and text[pos] == "(":
            pos += 1
            children[index].append(read_node(index, depth + 1))
            whitespace()
            while pos < len(text) and text[pos] == ",":
                pos += 1
                children[index].append(read_node(index, depth + 1))
                whitespace()
            if len(children[index]) < 2 or pos >= len(text) or text[pos] != ")":
                raise ValueError(
                    "Every internal node requires at least two children and matched parentheses"
                )
            pos += 1
            whitespace()
            match = label_re.match(text, pos)
            if match:
                nodes[index]["label"] = match.group()
                pos = match.end()
        else:
            match = label_re.match(text, pos)
            if not match:
                raise ValueError("Every tip requires one nonempty unquoted ASCII label")
            nodes[index]["label"] = match.group()
            pos = match.end()
        whitespace()
        if pos < len(text) and text[pos] == ":":
            pos += 1
            whitespace()
            match = length_re.match(text, pos)
            if not match:
                raise ValueError(
                    "Every edge length must be finite positive numeric text"
                )
            lexical = match.group()
            value = float(lexical)
            if not math.isfinite(value) or (parent is not None and value <= 0):
                raise ValueError(
                    "Every nonroot edge requires a strictly positive representable finite length"
                )
            # A nonzero lexical stem may underflow to float0.  The grammar
            # permits a mathematically zero stem only, not a rounded one.
            zero_mantissa = not any(
                digit in "123456789"
                for digit in lexical.lstrip("+").lower().split("e", 1)[0]
            )
            if parent is None and not zero_mantissa:
                raise ValueError(
                    "Root stem must be absent or mathematically zero; no implicit stem interpretation"
                )
            nodes[index]["branch_length"] = value
            pos = match.end()
        elif parent is not None:
            raise ValueError("Every nonroot edge requires an explicit branch length")
        whitespace()
        return index

    if not text.startswith("("):
        raise ValueError("The complete tree must have an explicitly parenthesized root")
    read_node(None, 0)
    if pos >= len(text) or text[pos] != ";":
        raise ValueError("One complete semicolon-terminated tree is required")
    pos += 1
    whitespace()
    if pos != len(text):
        raise ValueError("No trailing text or multiple trees are permitted")
    tips = [i for i, cc in enumerate(children) if not cc]
    labels = [nodes[i]["label"] for i in tips]
    if not 2 <= len(tips) <= 100 or len(labels) != len(set(labels)):
        raise ValueError("Require 2..100 tips with unique exact labels")

    def finite_sum(values):
        try:
            result = math.fsum(values)
        except OverflowError as exc:
            raise ValueError(
                "Tree path or total exceeds finite representable range"
            ) from exc
        if not math.isfinite(result):
            raise ValueError("Tree path or total exceeds finite representable range")
        return result

    # Node paths retain explicit edge identities, so a very short terminal edge
    # is never lost by subtracting two large shared root distances.
    ancestors = []
    for i in tips:
        path = []
        current = i
        while current is not None:
            path.append(current)
            current = nodes[current]["parent_id"]
        ancestors.append(path)
    depths = [
        finite_sum(nodes[i]["branch_length"] for i in path[:-1]) for path in ancestors
    ]
    distances = [[0.0 for _ in tips] for _ in tips]
    for i in range(len(tips)):
        for j in range(i):
            other = set(ancestors[j])
            lca = next(v for v in ancestors[i] if v in other)
            path_nodes = []
            for path in [ancestors[i], ancestors[j]]:
                for current in path:
                    if current == lca:
                        break
                    path_nodes.append(current)
            value = finite_sum(nodes[k]["branch_length"] for k in path_nodes)
            if value <= 0:
                raise ValueError(
                    "Distinct tip distance is not positive in representable arithmetic"
                )
            distances[i][j] = distances[j][i] = value
    total = finite_sum(n["branch_length"] for n in nodes[1:])
    return {
        "tip_ids": labels,
        "tip_node_ids": tips,
        "root_to_tip_lengths": depths,
        "patristic_distances": distances,
        "nodes": [dict(n, child_ids=list(children[i])) for i, n in enumerate(nodes)],
        "tip_count": len(tips),
        "node_count": len(nodes),
        "total_branch_length": total,
        "source_text_sha256": hashlib.sha256(newick_text.encode("utf-8")).hexdigest(),
        "distance_definition": "Sum of explicit edge lengths along the unique undirected path between supplied tips; exact zero diagonal and copied symmetric entries. Root-to-tip lengths exclude an absent/zero root stem.",
        "scope": "Literal supplied topology and branch-length units only. Serialization root is not an inferred biological root. No clock test, ultrametric decision, divergence times, tree accuracy, causal/evolutionary conclusion or inferred missing edges.",
    }
