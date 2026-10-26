"""Bounded mathematical checks of actual, potentially nonunique linear witnesses.

These predicates neither solve a new scientific model nor choose a golden basis.
They check the original supplied numerical equations, preserving basis rotations
and alternative optimal primal/dual witnesses. No submitted code is evaluated.
"""

import json
from functools import lru_cache
import numpy as np

TOOLS = frozenset({"SymmetricEigenDecomposition", "MatrixSVD", "SolveLinearProgram"})


def _numeric(value, ndim=None):
    def valid(v):
        if isinstance(v, list):
            return all(valid(x) for x in v)
        return type(v) in (int, float) and np.isfinite(v)

    if not valid(value):
        raise ValueError("Finite real numerical arrays required")
    a = np.asarray(value, dtype=float)
    if ndim is not None and a.ndim != ndim:
        raise ValueError("Unexpected witness dimension")
    if a.size > 100000:
        raise ValueError("Witness exceeds bounded public tool size")
    return a


def _close(a, b, tol=1e-7):
    a = np.asarray(a)
    b = np.asarray(b)
    return a.shape == b.shape and bool(np.all(np.abs(a - b) <= tol * (1 + np.abs(b))))


def witness_certificate(tool, arguments, output):
    """Return a boolean, failing closed on malformed or inconsistent evidence."""
    if (
        tool not in TOOLS
        or not isinstance(arguments, dict)
        or not isinstance(output, dict)
    ):
        return False
    try:
        payload = json.dumps(
            [tool, arguments, output],
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        if len(payload) > 8000000:
            return False
        return bool(_check(payload))
    except (
        TypeError,
        ValueError,
        OverflowError,
        KeyError,
        IndexError,
        np.linalg.LinAlgError,
    ):
        return False


@lru_cache(maxsize=1024)
def _check(payload):
    tool, a, o = json.loads(payload)
    try:
        if tool == "SymmetricEigenDecomposition":
            A = _numeric(a["values"], 2)
            e = _numeric(o["eigenvalues"], 1)
            V = _numeric(o["eigenvectors"], 2)
            n = len(e)
            if not 1 <= n <= 200 or A.shape != (n, n) or V.shape != (n, n):
                return False
            # np.linalg.eigh reads the lower triangle; accepted nearly symmetric
            # inputs retain that documented source convention.
            S = np.tril(A) + np.tril(A, -1).T
            scale = 1 + np.linalg.norm(S, ord=np.inf)
            return bool(
                np.all(np.diff(e) >= -1e-10 * scale)
                and _close(V.T @ V, np.eye(n), 1e-7)
                and np.max(np.abs(S @ V - V * e)) <= 1e-7 * scale
            )
        if tool == "MatrixSVD":
            A = _numeric(a["values"], 2)
            U = _numeric(o["u"], 2)
            s = _numeric(o["singular_values"], 1)
            Vt = _numeric(o["vt"], 2)
            m, n = A.shape
            r = min(m, n)
            if (
                U.shape != (m, r)
                or Vt.shape != (r, n)
                or s.shape != (r,)
                or np.any(s < 0)
                or np.any(np.diff(s) > 1e-8 * (1 + max(s)))
            ):
                return False
            residual = float(np.linalg.norm((U * s) @ Vt - A))
            reported = o["reconstruction_error"]
            return (
                type(reported) in (int, float)
                and np.isfinite(reported)
                and reported >= 0
                and _close(U.T @ U, np.eye(r))
                and _close(Vt @ Vt.T, np.eye(r))
                and residual <= 1e-7 * (1 + np.linalg.norm(A))
                and abs(reported - residual) <= 1e-7 * (1 + np.linalg.norm(A))
            )
        c = _numeric(a["objective"], 1)
        n = len(c)
        bounds = a["bounds"]
        direction = a.get("direction", "min")
        if (
            not 1 <= n <= 500
            or len(bounds) != n
            or direction not in ("min", "max")
            or o["direction"] != direction
        ):
            return False
        mats = []
        rhs = []
        for label in ["inequality", "equality"]:
            raw = a.get(label + "_matrix")
            b = a.get(label + "_rhs")
            if raw is None and b is None:
                raw = []
                b = []
            B = _numeric(raw).reshape((-1, n))
            v = _numeric(b, 1)
            if len(B) != len(v):
                return False
            mats.append(B)
            rhs.append(v)
        Au, Ae = mats
        bu, be = rhs
        if (
            o["variable_count"] != n
            or o["inequality_count"] != len(bu)
            or o["equality_count"] != len(be)
        ):
            return False
        if o["status"] != "optimal":
            return (
                o["status"]
                in [
                    "infeasible",
                    "unbounded",
                    "limit",
                    "solver_failure",
                    "numerical_failure",
                ]
                and o["solution"] is None
                and o["objective_value"] is None
                and o["diagnostics"] is None
            )
        x = _numeric(o["solution"], 1)
        diag = o["diagnostics"]
        if x.shape != (n,) or not isinstance(diag, dict):
            return False
        yu = _numeric(diag["inequality_marginals"], 1)
        ye = _numeric(diag["equality_marginals"], 1)
        yl = _numeric(diag["lower_bound_marginals"], 1)
        yh = _numeric(diag["upper_bound_marginals"], 1)
        if (
            yu.shape != bu.shape
            or ye.shape != be.shape
            or yl.shape != x.shape
            or yh.shape != x.shape
        ):
            return False
        slack = bu - Au @ x
        residual = be - Ae @ x
        obj = float(c @ x)
        reported = o["objective_value"]
        if (
            type(reported) not in (int, float)
            or not np.isfinite(reported)
            or abs(obj - reported) > 1e-7 * (1 + abs(obj))
        ):
            return False
        if np.any(slack < -1e-7 * (1 + np.abs(bu) + np.abs(Au) @ np.abs(x))) or np.any(
            np.abs(residual) > 1e-7 * (1 + np.abs(be) + np.abs(Ae) @ np.abs(x))
        ):
            return False
        if not _close(_numeric(diag["inequality_slack"], 1), slack) or not _close(
            _numeric(diag["equality_residual"], 1), residual
        ):
            return False
        sign = 1 if direction == "min" else -1
        dual = float(bu @ yu + be @ ye)
        comp = [0.0]
        if (
            np.any(yu * sign > 1e-7)
            or np.any(-yl * sign > 1e-7)
            or np.any(yh * sign > 1e-7)
        ):
            return False
        for i, pair in enumerate(bounds):
            if not isinstance(pair, list) or len(pair) != 2:
                return False
            for endpoint, margin, field, sense in [
                (pair[0], yl[i], "lower_bound_slack", 1),
                (pair[1], yh[i], "upper_bound_slack", -1),
            ]:
                actual = diag[field][i]
                if endpoint is None:
                    if actual is not None or abs(margin) > 1e-7:
                        return False
                else:
                    if type(endpoint) not in (int, float) or not np.isfinite(endpoint):
                        return False
                    gap = sense * (x[i] - endpoint)
                    if (
                        gap < -1e-7 * (1 + abs(x[i]) + abs(endpoint))
                        or type(actual) not in (int, float)
                        or not np.isfinite(actual)
                        or abs(actual - gap) > 1e-7 * (1 + abs(gap))
                    ):
                        return False
                    dual += endpoint * margin
                    comp.append(abs(gap * margin) / (1 + abs(obj)))
        station = c - Au.T @ yu - Ae.T @ ye - yl - yh
        scale = (
            1 + abs(c) + abs(Au).T @ abs(yu) + abs(Ae).T @ abs(ye) + abs(yl) + abs(yh)
        )
        comp.extend((abs(slack * yu) / (1 + abs(obj))).tolist())
        return bool(
            np.max(abs(station) / scale) <= 1e-7
            and max(comp) <= 1e-7
            and abs(obj - dual) <= 1e-7 * (1 + abs(obj) + abs(dual))
            and abs(diag["dual_objective"] - dual) <= 1e-7 * (1 + abs(dual))
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
        KeyError,
        IndexError,
        np.linalg.LinAlgError,
    ):
        return False


def certificate_rule(tool):
    return {
        "left": {
            "operation": "linear_algebra_witness",
            "args": [
                {"value": tool},
                {"source": "call_arguments", "path": ""},
                {"source": "call_output", "path": ""},
            ],
        },
        "op": "eq",
        "right": {"value": True},
    }


def add_witness_rules(spec):
    """Idempotently strengthen relevant alternatives, retaining their own checks."""
    for node in spec.get("nodes", []):
        for alt in node["alternatives"]:
            relevant = set(alt["tools"]) & TOOLS
            if not relevant:
                continue
            # Alternatives in this authoring library name exactly one tool.
            if len(alt["tools"]) != 1:
                raise ValueError(
                    "Separate mathematical tool alternatives before adding witness checks"
                )
            rule = certificate_rule(next(iter(relevant)))
            if rule not in alt["output_rules"]:
                alt["output_rules"].append(rule)
    return spec
