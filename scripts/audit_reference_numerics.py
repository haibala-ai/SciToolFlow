"""Check archived numerical observations using formulas, without dispatch/model APIs.

No sklearn estimator, scipy.stats test or registered implementation is called.
NumPy linear algebra and scipy.special are numerical primitives, not an independent
floating-point implementation. These checks do not validate external source data.
"""

import json
import math
from pathlib import Path
import sys
import numpy as np
from scipy.special import betainc, gammaincc

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.audit_tasks import decoded, load_rows


def ranks(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(order)
    begin = 0
    while begin < len(order):
        end = begin + 1
        while end < len(order) and values[order[end]] == values[order[begin]]:
            end += 1
        for index in order[begin:end]:
            result[index] = (begin + end + 1) / 2
        begin = end
    return result


def verify(event):
    tool, a, out = event["tool"], event["arguments"], decoded(event.get("output"))
    checks = []
    if not isinstance(out, dict) or event.get("status") != "success":
        return checks

    def compare(name, expected, actual, *, atol=1e-8, rtol=1e-6):
        if expected is None:
            passed = actual is None
            error = None
        else:
            x, y = np.asarray(expected, dtype=float), np.asarray(actual, dtype=float)
            passed = x.shape == y.shape and bool(
                np.allclose(x, y, atol=atol, rtol=rtol)
            )
            error = (
                float(np.max(np.abs(x - y))) if x.shape == y.shape and x.size else None
            )
        checks.append(
            {
                "quantity": name,
                "passed": passed,
                "maximum_absolute_error": error,
                "atol": atol,
                "rtol": rtol,
            }
        )

    if tool == "DescribeNumericData":
        x = np.asarray(a["values"], dtype=float)
        expected = dict(
            count=len(x),
            mean=np.mean(x),
            median=np.median(x),
            sample_std=np.std(x, ddof=1) if len(x) > 1 else 0,
            minimum=np.min(x),
            maximum=np.max(x),
            q25=np.quantile(x, 0.25),
            q75=np.quantile(x, 0.75),
        )
        for key, value in expected.items():
            compare(key, value, out[key])
    elif tool in {"FitLinearRegression", "FitRidgeRegression"}:
        x, y = np.asarray(a["training_features"], float), np.asarray(
            a["targets"], float
        )
        mx, my = x.mean(0), y.mean()
        xc, yc = x - mx, y - my
        penalty = float(a.get("alpha", 0))
        beta = (
            np.linalg.solve(xc.T @ xc + penalty * np.eye(x.shape[1]), xc.T @ yc)
            if penalty
            else np.linalg.lstsq(xc, yc, rcond=None)[0]
        )
        intercept = my - mx @ beta
        compare("coefficients", beta, out["model"]["coefficients"])
        compare("intercept", intercept, out["model"]["intercept"])
        compare(
            "training_mse",
            np.mean((x @ beta + intercept - y) ** 2),
            out["training_mse"],
        )
    elif tool == "PredictLinearModel":
        model = a["model"]
        compare(
            "predictions",
            np.asarray(a["features"]) @ np.asarray(model["coefficients"])
            + model["intercept"],
            out["predictions"],
        )
    elif tool == "RegressionMetrics":
        y, p = np.asarray(a["truth"], float), np.asarray(a["predicted"], float)
        error = p - y
        mse = np.mean(error**2)
        ss = np.sum((y - y.mean()) ** 2)
        expected = dict(
            mae=np.mean(abs(error)),
            mse=mse,
            rmse=math.sqrt(mse),
            r_squared=1 - np.sum(error**2) / ss if ss else None,
            count=len(y),
        )
        for key, value in expected.items():
            compare(key, value, out[key])
    elif tool == "StandardizeNumericFeatures":
        x = np.asarray(a["features"], float)
        train = np.asarray(a.get("training_features") or a["features"], float)
        mean = train.mean(0)
        scale = train.std(0)
        scale[scale == 0] = 1
        compare("mean", mean, out["mean"])
        compare("scale", scale, out["scale"])
        compare("features", (x - mean) / scale, out["features"])
    elif tool in {"PearsonCorrelation", "SpearmanCorrelation"}:
        x, y = a["x"], a["y"]
        if tool == "SpearmanCorrelation":
            x, y = ranks(x), ranks(y)
        x, y = np.asarray(x, float), np.asarray(y, float)
        xc, yc = x - x.mean(), y - y.mean()
        n = len(x)
        r = float(xc @ yc / math.sqrt(float(xc @ xc) * float(yc @ yc)))
        compare("correlation", r, out["correlation"])
        if abs(r) < 1 and n > 2:
            if tool == "PearsonCorrelation":
                p = 2 * betainc(n / 2 - 1, n / 2 - 1, (1 - abs(r)) / 2)
            else:
                p = betainc((n - 2) / 2, 0.5, max(0, 1 - r * r))
            compare("p_value", p, out["p_value"], atol=0, rtol=1e-5)
    elif tool == "ChiSquareIndependence":
        x = np.asarray(a["contingency_table"], float)
        expected = np.outer(x.sum(1), x.sum(0)) / x.sum()
        df = (x.shape[0] - 1) * (x.shape[1] - 1)
        stat = np.sum((x - expected) ** 2 / expected)
        compare("expected_counts", expected, out["expected_counts"])
        compare("statistic", stat, out["statistic"])
        compare("degrees_of_freedom", df, out["degrees_of_freedom"])
        compare("p_value", gammaincc(df / 2, stat / 2), out["p_value"], atol=0)
    elif tool == "OneWayANOVA":
        groups = [np.asarray(v, float) for v in a["groups"]]
        allx = np.concatenate(groups)
        between = sum(len(v) * (v.mean() - allx.mean()) ** 2 for v in groups)
        within = sum(np.sum((v - v.mean()) ** 2) for v in groups)
        d1 = len(groups) - 1
        d2 = len(allx) - len(groups)
        stat = (between / d1) / (within / d2)
        compare("statistic", stat, out["statistic"])
        compare(
            "p_value",
            betainc(d2 / 2, d1 / 2, d2 / (d2 + d1 * stat)),
            out["p_value"],
            atol=0,
        )
    elif tool in {"SolveLinearSystem", "LinearLeastSquares"}:
        A, b = np.asarray(a["matrix_a"], float), np.asarray(a["vector_b"], float)
        solution = np.asarray(out["solution"], float)
        compare("residual_norm", np.linalg.norm(A @ solution - b), out["residual_norm"])
        independent = np.linalg.lstsq(A, b, rcond=None)[0]
        compare("least_squares_predictions", A @ independent, A @ solution)
        if "rank" in out:
            compare("rank", np.linalg.matrix_rank(A), out["rank"])
    elif tool == "MatrixInverse":
        x = np.asarray(a["values"], float)
        inverse = np.asarray(out["inverse"], float)
        compare("identity_reconstruction", np.eye(len(x)), x @ inverse)
        compare("condition_number", np.linalg.cond(x), out["condition_number"])
    elif tool == "MatrixSVD":
        x = np.asarray(a["values"], float)
        u, s, vt = [np.asarray(out[k], float) for k in ["u", "singular_values", "vt"]]
        compare("matrix_reconstruction", x, (u * s) @ vt)
        compare("left_orthogonality", np.eye(len(s)), u.T @ u)
        compare("right_orthogonality", np.eye(len(s)), vt @ vt.T)
    elif tool == "SymmetricEigenDecomposition":
        x = np.asarray(a["values"], float)
        s, v = np.asarray(out["eigenvalues"]), np.asarray(out["eigenvectors"])
        compare("eigen_equation", x @ v, v * s)
        compare("orthogonality", np.eye(len(s)), v.T @ v)
    elif tool == "KMeansClustering":
        x = np.asarray(a["features"], float)
        centers = np.asarray(out["centroids"], float)
        labels = np.asarray(out["labels"], int)
        compare("inertia", np.sum((x - centers[labels]) ** 2), out["inertia"])
        for label in set(labels):
            compare(
                "centroid_" + str(label), x[labels == label].mean(0), centers[label]
            )
        compare(
            "nearest_centroid_distance",
            np.sum((x - centers[labels]) ** 2, 1),
            np.min(np.sum((x[:, None, :] - centers[None, :, :]) ** 2, 2), 1),
        )
    elif tool == "PrincipalComponentProjection":
        x = np.asarray(a["features"], float)
        train = np.asarray(a.get("training_features") or a["features"], float)
        components = np.asarray(out["components"], float)
        mean = train.mean(0)
        compare("mean", mean, out["mean"])
        compare("scores", (x - mean) @ components.T, out["features"])
        compare("orthogonality", np.eye(len(components)), components @ components.T)
        score = (train - mean) @ components.T
        compare(
            "explained_variance", np.var(score, 0, ddof=1), out["explained_variance"]
        )
        compare(
            "explained_variance_ratio",
            np.var(score, 0, ddof=1) / np.var(train, 0, ddof=1).sum(),
            out["explained_variance_ratio"],
        )
    elif tool == "InterpolateLinear":
        x, y, query = np.asarray(a["x"]), np.asarray(a["y"]), a["query_x"]
        compare("values", np.interp(query, x, y), out["values"])
    elif tool == "NumericalTrapezoidIntegration":
        x, y = np.asarray(a["x"]), np.asarray(a["y"])
        compare("integral", np.sum(np.diff(x) * (y[1:] + y[:-1]) / 2), out["integral"])
    elif tool == "FiniteDifferenceGradient":
        x, y = np.asarray(a["x"]), np.asarray(a["y"])
        gradient = []
        for i in range(len(x)):
            if i == 0:
                v = (y[1] - y[0]) / (x[1] - x[0])
            elif i == len(x) - 1:
                v = (y[-1] - y[-2]) / (x[-1] - x[-2])
            else:
                h0, h1 = x[i] - x[i - 1], x[i + 1] - x[i]
                v = (
                    -h1 * y[i - 1] / (h0 * (h0 + h1))
                    + (h1 - h0) * y[i] / (h0 * h1)
                    + h0 * y[i + 1] / (h1 * (h0 + h1))
                )
            gradient.append(v)
        compare("gradient", gradient, out["gradient"])
    return checks


def main():
    results = []
    for reference in load_rows(ROOT / "evaluation/references.jsonl"):
        entries = []
        for event in load_rows(ROOT / reference["reference_trace"]):
            if event.get("event") != "tool_result":
                continue
            try:
                checks = verify(event)
            except Exception as error:
                entries.append(
                    {
                        "observation_id": event["observation_id"],
                        "tool": event["tool"],
                        "checker_error": type(error).__name__ + ": " + str(error),
                    }
                )
                continue
            if checks:
                entries.append(
                    {
                        "observation_id": event["observation_id"],
                        "tool": event["tool"],
                        "checks": checks,
                    }
                )
        results.append(
            {
                "id": reference["id"],
                "observations": entries,
                "independently_recomputed_quantity_count": sum(
                    len(e.get("checks", [])) for e in entries
                ),
            }
        )
    all_entries = [e for r in results for e in r["observations"]]
    all_checks = [c for e in all_entries for c in e.get("checks", [])]
    report = {
        "scope": "archived numerical observations; no live tool or LLM calls",
        "tasks_enumerated": len(results),
        "tasks_with_recomputations": sum(bool(r["observations"]) for r in results),
        "observations_checked": len(all_entries),
        "quantities_checked": len(all_checks),
        "quantity_failures": sum(not c["passed"] for c in all_checks),
        "checker_errors": sum("checker_error" in e for e in all_entries),
        "limits": "Formula and dataflow consistency only. Does not validate source databases, physical assumptions, optimal clustering, or every scientific gold claim. Shared NumPy/scipy.special numerical primitives.",
        "tasks": results,
    }
    path = ROOT / "results/reports/full_run_audit_20261018/numerical_audit.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "tasks"}, indent=2))


if __name__ == "__main__":
    main()
