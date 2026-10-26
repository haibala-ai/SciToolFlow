"""Equivalent degree-one polynomial routes for scientific affine fits."""

import copy


def _rewrite(value):
    if isinstance(value, list):
        return [_rewrite(x) for x in value]
    if not isinstance(value, dict):
        return value
    out = {k: _rewrite(v) for k, v in value.items()}
    if out.get("source") == "call_arguments" and isinstance(out.get("path"), str):
        path = out["path"]
        if path.startswith("/training_features/") and path.endswith("/0"):
            out["path"] = "/x/" + path.split("/")[2]
        elif path == "/targets":
            out["path"] = "/y"
    return out


def add_polynomial_alternatives(nodes):
    changed = False
    for node in nodes:
        alternatives = node.get("alternatives", [])
        if any(a.get("tools") == ["PolynomialLeastSquaresFit"] for a in alternatives):
            continue
        original = next(
            (a for a in alternatives if a.get("tools") == ["FitLinearRegression"]), None
        )
        if original is None:
            continue
        rules = []
        for item in original.get("input_rules", []):
            r = _rewrite(copy.deepcopy(item))
            path = r.get("path", "")
            if path == "/training_features":
                if (
                    r.get("op") != "multiset_equal"
                    or "value" not in r
                    or any(
                        not isinstance(row, list) or len(row) != 1 for row in r["value"]
                    )
                ):
                    raise ValueError(
                        "Only one-predictor affine calibration is equivalent to a degree-one polynomial"
                    )
                r["path"] = "/x"
                r["value"] = [row[0] for row in r["value"]]
            elif path.startswith("/targets/"):
                r["path"] = "/y/" + path.split("/")[2]
            elif path:
                raise ValueError("Unhandled affine fit input constraint:" + path)
            rules.append(r)
        rules.append({"path": "/degree", "op": "eq", "value": 1})
        alternative = {
            "tools": ["PolynomialLeastSquaresFit"],
            "input_rules": rules,
            "output_rules": [
                {"path": "/degree", "op": "eq", "value": 1},
                {"path": "/coefficients", "op": "type", "value": "array"},
                {"path": "/fitted_values", "op": "type", "value": "array"},
            ],
        }
        if "bindings" in original:
            alternative["bindings"] = copy.deepcopy(original["bindings"])
        alternatives.append(alternative)
        changed = True
    return repair_paired_polynomial_routes(nodes) or changed


def repair_paired_polynomial_routes(nodes):
    """Flatten both sides of a one-predictor paired criterion together.

    A polynomial's x is a vector, unlike a linear regressor's N-by-1 matrix.
    Pair identity is retained; converting only the argument name is insufficient.
    """
    changed = False
    for node in nodes:
        for alternative in node.get("alternatives", []):
            if alternative.get("tools") != ["PolynomialLeastSquaresFit"]:
                continue
            for rule in alternative.get("input_rules", []):
                left, right = rule.get("left", {}), rule.get("right", {})
                if left.get("operation") != "paired_rows" or left["args"][0] != {
                    "source": "call_arguments",
                    "path": "/training_features",
                }:
                    continue
                assert right.get("operation") == "paired_rows"
                matrix = right["args"][0]
                if matrix.get("operation") == "numeric_rows":
                    assert all(
                        row.get("operation") == "array" and len(row["args"]) == 1
                        for row in matrix["args"]
                    )
                else:
                    assert (
                        "value" in matrix
                        and matrix["value"]
                        and all(
                            isinstance(row, list) and len(row) == 1
                            for row in matrix["value"]
                        )
                    )
                left["args"][0] = {"source": "call_arguments", "path": "/x"}
                right["args"][0] = {
                    "operation": "column",
                    "args": [matrix, {"value": 0}],
                }
                changed = True
    return changed
