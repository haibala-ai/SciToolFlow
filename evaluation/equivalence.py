"""Opt-in, jointly verified mathematical representation changes (standard library).

Only copies used for comparison are canonicalized. Raw submissions and observations
stay intact. Components/scores and cluster labels/centers must change consistently;
scientific vectors are never globally sorted or compared by absolute value.
"""

import copy
import math


def close(a, b, atol=1e-8, rtol=1e-6):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(close(x, y, atol, rtol) for x, y in zip(a, b))
    return (
        type(a) in (int, float)
        and type(b) in (int, float)
        and math.isfinite(a)
        and math.isfinite(b)
        and abs(a - b) <= atol + rtol * abs(a)
    )


def transpose(a):
    return [list(row) for row in zip(*a)]


def product(a, b):
    return [
        [math.fsum(x * y for x, y in zip(row, col)) for col in zip(*b)] for row in a
    ]


def matrix(a):
    return (
        isinstance(a, list)
        and bool(a)
        and all(
            isinstance(row, list)
            and len(row) == len(a[0])
            and all(type(v) in (int, float) and math.isfinite(v) for v in row)
            for row in a
        )
        and bool(a[0])
    )


def walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (key,))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk(child, path + (i,))


def locate(value, path):
    for key in path:
        if not isinstance(value, (dict, list)):
            return None
        try:
            value = value[key]
        except (KeyError, IndexError, TypeError):
            return None
    return value


def remap_labels(actual, expected):
    if (
        not isinstance(actual, list)
        or len(actual) != len(expected)
        or any(type(v) is not int for v in actual + expected)
    ):
        return None
    mapping = {}
    for a, e in zip(actual, expected):
        if (a in mapping and mapping[a] != e) or (
            e in mapping.values() and mapping.get(a) != e
        ):
            return None
        mapping[a] = e
    return mapping


def normalize_answer_equivalences(reference, answer):
    try:
        return _normalize(reference, answer)
    except (ValueError, TypeError, IndexError, KeyError, ArithmeticError):
        # An ill-shaped submission is handled by ordinary schema/value validation.
        # A failed proof never turns an answer into an equivalent representation.
        return answer, []


def _normalize(reference, answer):
    if not reference.get("scoring", {}).get(
        "mathematical_equivalence"
    ) or not isinstance(answer, dict):
        return answer, []
    gold = reference["expected_answer"]
    value = copy.deepcopy(answer)
    proofs = []
    pairs = []
    rotations = []
    # First verify whole eigenproblems / PCA representations, not separate signs.
    for path, g in walk(gold):
        a = locate(value, path)
        if not isinstance(g, dict) or not isinstance(a, dict):
            continue
        if {"eigenvalues", "eigenvectors"} <= g.keys() and {
            "eigenvalues",
            "eigenvectors",
        } <= a.keys():
            ev, gv, ae, av = (
                g["eigenvalues"],
                g["eigenvectors"],
                a["eigenvalues"],
                a["eigenvectors"],
            )
            if (
                not matrix(gv)
                or not matrix(av)
                or len(ev) != len(ae)
                or len(av) != len(gv)
                or len(av[0]) != len(ev)
            ):
                continue
            if not close(sorted(ev), sorted(ae)):
                continue
            identity = [[int(i == j) for j in range(len(ae))] for i in range(len(ae))]
            if not close(product(transpose(av), av), identity):
                continue
            gm = product(
                [[v * ev[j] for j, v in enumerate(row)] for row in gv], transpose(gv)
            )
            am = product(
                [[v * ae[j] for j, v in enumerate(row)] for row in av], transpose(av)
            )
            if not close(gm, am):
                continue
            if av != gv or ae != ev:
                pairs.extend([(gv, copy.deepcopy(av)), (ev, copy.deepcopy(ae))])
                proofs.append(
                    {"path": list(path), "kind": "orthonormal_eigenbasis_same_matrix"}
                )
        if (
            not {
                "components",
                "features",
                "explained_variance",
                "explained_variance_ratio",
            }
            <= g.keys()
            or not {
                "components",
                "features",
                "explained_variance",
                "explained_variance_ratio",
            }
            <= a.keys()
        ):
            continue
        gc, gs, ac, ss = g["components"], g["features"], a["components"], a["features"]
        if (
            not all(matrix(v) for v in [gc, gs, ac, ss])
            or len(gc) != len(ac)
            or len(gc[0]) != len(ac[0])
            or len(gs) != len(ss)
            or len(ss) < 2
        ):
            continue
        k = len(gc)
        identity = [[int(i == j) for j in range(k)] for i in range(k)]
        if not close(product(ac, transpose(ac)), identity) or not close(
            product(transpose(gc), gc), product(transpose(ac), ac)
        ):
            continue
        if not close(product(gs, gc), product(ss, ac)):
            continue
        means = [math.fsum(col) / len(ss) for col in zip(*ss)]
        centered = [[x - m for x, m in zip(row, means)] for row in ss]
        cov = [
            [x / (len(ss) - 1) for x in row]
            for row in product(transpose(centered), centered)
        ]
        diagonal = [
            [a["explained_variance"][i] if i == j else 0 for j in range(k)]
            for i in range(k)
        ]
        if (
            not close(cov, diagonal)
            or not close(
                sorted(g["explained_variance"]), sorted(a["explained_variance"])
            )
            or not close(
                sorted(g["explained_variance_ratio"]),
                sorted(a["explained_variance_ratio"]),
            )
        ):
            continue
        total_variance = sum(g["explained_variance"]) / sum(
            g["explained_variance_ratio"]
        )
        if not close(
            [v / total_variance for v in a["explained_variance"]],
            a["explained_variance_ratio"],
        ):
            continue
        rotation = product(gc, transpose(ac))
        scope = path[: path.index("branches") + 2] if "branches" in path else ()
        rotations.append((scope, rotation))
        if ac != gc or ss != gs:
            for key in [
                "components",
                "features",
                "explained_variance",
                "explained_variance_ratio",
            ]:
                pairs.append((g[key], copy.deepcopy(a[key])))
            proofs.append(
                {"path": list(path), "kind": "joint_pca_basis_scores_and_variances"}
            )

    # Rewrite duplicated numerical arrays only when BOTH complete arrays match a
    # previously verified pair. Scalars and unrelated/reordered vectors are untouched.
    def rewrite(g, a):
        if isinstance(g, list) and isinstance(a, list):
            for expected, actual in pairs:
                if g == expected and a == actual:
                    return copy.deepcopy(expected)
            return [rewrite(x, y) for x, y in zip(g, a)] if len(g) == len(a) else a
        if isinstance(g, dict) and isinstance(a, dict):
            return {
                key: rewrite(g[key], child) if key in g else child
                for key, child in a.items()
            }
        return a

    value = rewrite(gold, value)
    # Relabel each clustering only if partition AND corresponding centers agree.
    for path, g in walk(gold):
        a = locate(value, path)
        if not isinstance(g, dict) or not isinstance(a, dict):
            continue
        lk = next(
            (key for key in ["labels", "returned_labels"] if key in g and key in a),
            None,
        )
        ck = next(
            (
                key
                for key in ["centroids", "returned_centroids"]
                if key in g and key in a
            ),
            None,
        )
        if not lk:
            continue
        mapping = remap_labels(a[lk], g[lk])
        if mapping is None:
            continue
        if ck:
            centers = a[ck]
            expected = g[ck]
            if (
                not matrix(centers)
                or not matrix(expected)
                or len(centers) != len(expected)
                or set(mapping) != set(range(len(centers)))
                or set(mapping.values()) != set(range(len(expected)))
            ):
                continue
            options = [centers] + [
                product(centers, transpose(rotation))
                for scope, rotation in rotations
                if path[: len(scope)] == scope and len(rotation) == len(centers[0])
            ]
            aligned = None
            for candidate in options:
                if any(
                    key < 0
                    or key >= len(candidate)
                    or target < 0
                    or target >= len(expected)
                    for key, target in mapping.items()
                ):
                    continue
                if all(
                    close(expected[target], candidate[key])
                    for key, target in mapping.items()
                ):
                    aligned = candidate
                    break
            if aligned is None:
                continue
        else:
            # Standalone DBSCAN labels: preserve noise identity exactly.
            if "DBSCANClustering" not in reference.get("tool_path", []) or any(
                (x == -1) != (y == -1) for x, y in zip(a[lk], g[lk])
            ):
                continue
        if a[lk] == g[lk] and (not ck or close(a[ck], g[ck])):
            continue
        scope_path = (
            path[:-1]
            if path and ("artifact" in str(path[-1]) or "complete" in str(path[-1]))
            else path
        )
        scope = locate(value, scope_path)
        scope_gold = locate(gold, scope_path)
        original_labels = copy.deepcopy(a[lk])
        original_centers = copy.deepcopy(a.get(ck)) if ck else None

        def relabel(node, key=""):
            if isinstance(node, list):
                if key == "groups" and isinstance(scope_gold, dict):
                    expected_groups = scope_gold.get("groups")

                    def partition(groups):
                        if not isinstance(groups, list) or not all(
                            isinstance(group, list)
                            and all(type(member) in (int, str) for member in group)
                            for group in groups
                        ):
                            return None
                        return sorted(
                            tuple(
                                sorted(
                                    (type(member).__name__, member) for member in group
                                )
                            )
                            for group in groups
                        )

                    expected_partition = partition(expected_groups)
                    if (
                        expected_partition is not None
                        and partition(node) == expected_partition
                    ):
                        return copy.deepcopy(expected_groups)
                if node == original_labels and ("label" in key.lower()):
                    return copy.deepcopy(g[lk])
                if ck and node == original_centers and "centroid" in key.lower():
                    return copy.deepcopy(g[ck])
                if key == "cluster_sizes" and len(node) == len(mapping):
                    reordered = [None] * len(node)
                    for old, new in mapping.items():
                        reordered[new] = node[old]
                    return reordered
                return [relabel(v, key) for v in node]
            if isinstance(node, dict):
                result = {}
                for k, v in node.items():
                    newkey = k
                    if key in {"groups", "cluster_sizes"}:
                        try:
                            newkey = str(mapping.get(int(k), int(k)))
                        except ValueError:
                            pass
                    if type(v) is int and (k == "label" or "labels_aligned" in key):
                        result[newkey] = mapping.get(v, v)
                    else:
                        result[newkey] = relabel(v, k)
                return result
            return node

        revised = relabel(scope)
        if not scope_path:
            value = revised
        else:
            parent = locate(value, scope_path[:-1])
            parent[scope_path[-1]] = revised
        if reference["id"] == "FLOW-0484" and isinstance(
            value.get("label_grouping_derived"), dict
        ):
            value["label_grouping_derived"] = {
                (
                    ("label_" + str(mapping.get(int(k[6:]), int(k[6:]))))
                    if k.startswith("label_") and k[6:].isdigit()
                    else k
                ): v
                for k, v in value["label_grouping_derived"].items()
            }
        proofs.append(
            {
                "path": list(path),
                "kind": (
                    "same_partition_and_corresponding_centers"
                    if ck
                    else "same_dbscan_partition_and_noise"
                ),
                "label_mapping": mapping,
            }
        )
    return value, proofs
