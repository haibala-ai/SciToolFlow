"""Bounded numerical/statistical primitives for evidence-based research tasks."""

import math
import numpy as np


def _vector(values, name="values", nonnegative=False):
    if (
        not isinstance(values, list)
        or not 1 <= len(values) <= 10000
        or any(
            type(v) not in (int, float)
            or not math.isfinite(v)
            or (nonnegative and v < 0)
            for v in values
        )
    ):
        raise ValueError(name + " must contain1..10000 finite numeric values")
    return np.asarray(values, float)


def _matrix(values, name="values"):
    if (
        not isinstance(values, list)
        or not values
        or len(values) > 10000
        or not all(isinstance(r, list) and r for r in values)
        or len({len(r) for r in values}) != 1
        or len(values[0]) > 1000
    ):
        raise ValueError(name + " requires a bounded nonempty rectangular matrix")
    for row in values:
        _vector(row, name)
    return np.asarray(values, float)


def adjust_p_values(p_values: list, method: str = "bh") -> dict:
    """Adjust complete-family p-values by BH/BY/Bonferroni; retain input order.

    Inputs must include every eligible hypothesis specified by the study; this
    primitive cannot infer omitted tests. BH needs independence/positive dependence;
    BY is conservative under arbitrary dependence. No null p-value imputation.
    """
    from .statistical_kernels import adjust_complete_family
    if not isinstance(p_values, list) or not 1 <= len(p_values) <= 10000:
        raise ValueError("p_values needs 1..10000 values")
    return {
        "adjusted_p_values": adjust_complete_family(p_values, method),
        "method": method, "family_size": len(p_values),
        "scope": "Provided complete eligible family; input order retained; no omitted tests inferred",
    }


def hypergeometric_enrichment(
    universe_ids: list, selected_ids: list, term_members: dict
) -> dict:
    """One-sided gene-set overrepresentation with distinct-ID sets.

    universe/selected lists must contain distinct nonempty string IDs; selected
    outside universe is an error. Term members outside universe are ignored but
    reported. Returns unadjusted survival-function p-values; apply declared FDR
    separately to the entire tested family. Not causal functional confirmation.
    """
    from scipy.stats import hypergeom

    for values in [universe_ids, selected_ids]:
        if (
            not isinstance(values, list)
            or not values
            or len(values) > 10000
            or any(not isinstance(x, str) or not x for x in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError("IDs require1..10000 distinct nonempty strings")
    u = set(universe_ids)
    s = set(selected_ids)
    if not s <= u:
        raise ValueError("selected IDs outside universe")
    if (
        not isinstance(term_members, dict)
        or not term_members
        or len(term_members) > 1000
    ):
        raise ValueError("term_members must have1..1000 named terms")
    rows = []
    for term, ids in term_members.items():
        if (
            not isinstance(term, str)
            or not term
            or not isinstance(ids, list)
            or any(not isinstance(i, str) or not i for i in ids)
        ):
            raise ValueError("term IDs/members must be strings")
        members = set(ids) & u
        k = len(s & members)
        rows.append(
            {
                "term_id": term,
                "term_size": len(members),
                "overlap_size": k,
                "overlap_ids": sorted(s & members),
                "outside_universe_ids": sorted(set(ids) - u),
                "p_value": float(hypergeom.sf(k - 1, len(u), len(members), len(s))),
            }
        )
    return {
        "universe_size": len(u),
        "selected_size": len(s),
        "results": rows,
        "p_values": [r["p_value"] for r in rows],
        "test": "one-sided hypergeometric overrepresentation; unadjusted p-values",
    }


def superpose_coordinate_sets(
    reference_coordinates: list, mobile_coordinates: list
) -> dict:
    """Fit a proper rigid rotation to already matched3D point pairs (Kabsch).

    At least3 noncollinear points required; reflection forbidden. Input rows must
    be corresponding atoms in the same physical length units. No residue matching
    is inferred. Returns fitted mobile points and per-pair Euclidean residuals.
    """
    from .matched_coordinate_distances import rigid_superposition
    output = rigid_superposition([reference_coordinates, mobile_coordinates], ["reference", "mobile"], True, True)
    fit = output["pair_fits"][0]
    return dict(matched_count=output["point_count"], rmsd=fit["rmsd"], rotation=fit["rotation"], translation=fit["translation"], fitted_mobile_coordinates=fit["aligned_mobile_coordinates"], distances=fit["residual_distances"], proper_rotation_determinant=fit["determinant"], convention=output["transform_convention"])


def adjusted_rand_agreement(labels_a: list, labels_b: list) -> dict:
    """Permutation-invariant adjusted Rand index for same ordered observations."""
    from sklearn.metrics import adjusted_rand_score

    if (
        not isinstance(labels_a, list)
        or not isinstance(labels_b, list)
        or not 2 <= len(labels_a) <= 10000
        or len(labels_a) != len(labels_b)
    ):
        raise ValueError("Require equal label lists length2..10000")
    for labels in [labels_a, labels_b]:
        if any(type(v) not in (str, int) for v in labels):
            raise ValueError("Labels must be strings/integers")
    return {
        "adjusted_rand_index": float(adjusted_rand_score(labels_a, labels_b)),
        "sample_count": len(labels_a),
        "scope": "same record ordering required; permutation-invariant cluster labels; noise treated as an ordinary label",
    }


def clustering_quality_metrics(features: list, labels: list) -> dict:
    """Euclidean silhouette on nonnoise labels, with explicit undefined result.

    Label-1 is noise and excluded. One cluster or one cluster per retained point
    yields null silhouette. This internal criterion does not establish real classes.
    """
    from sklearn.metrics import silhouette_score

    x = _matrix(features)
    if (
        not isinstance(labels, list)
        or len(labels) != len(x)
        or any(type(v) not in (int, str) for v in labels)
    ):
        raise ValueError("labels must align with rows")
    keep = np.asarray([v != -1 for v in labels])
    ret = x[keep]
    ys = [v for v, k in zip(labels, keep) if k]
    k = len(set(ys))
    n = len(ret)
    val = float(silhouette_score(ret, ys)) if 2 <= k < n else None
    return {
        "silhouette": val,
        "cluster_count": k,
        "retained_count": n,
        "noise_count": len(x) - n,
        "metric": "Euclidean silhouette excluding numeric noise label-1; undefined outside2..N-1 clusters",
    }


def _binary_label(value, name):
    """Normalize JSON mathematical integers without coercing strings or booleans."""
    if type(value) in (str, int):
        return value
    if type(value) is float and math.isfinite(value) and value.is_integer():
        return int(value)
    raise ValueError(
        name + " must be a string or finite mathematical integer; "
        "booleans, fractional numbers and containers are not labels"
    )


def binary_classification_metrics(truth: list, predicted: list, positive_label) -> dict:
    """Binary confusion metrics; integral floats normalize to integers, 0/0 is null.

    Strings remain distinct from numeric labels. Boolean, fractional and nonfinite
    labels are errors. A positive label absent from a single observed class is
    allowed; it cannot introduce a third class to two observed classes.
    """
    if (
        not isinstance(truth, list)
        or not truth
        or len(truth) > 10000
        or not isinstance(predicted, list)
        or len(truth) != len(predicted)
    ):
        raise ValueError("Require aligned nonempty label lists")
    truth = [_binary_label(v, "truth label") for v in truth]
    predicted = [_binary_label(v, "predicted label") for v in predicted]
    positive_label = _binary_label(positive_label, "positive_label")
    if len(set(truth + predicted + [positive_label])) > 2:
        raise ValueError(
            "Only binary labels accepted; positive_label cannot be unrelated to two observed classes"
        )
    tp = sum(
        a == positive_label and b == positive_label for a, b in zip(truth, predicted)
    )
    fn = sum(
        a == positive_label and b != positive_label for a, b in zip(truth, predicted)
    )
    fp = sum(
        a != positive_label and b == positive_label for a, b in zip(truth, predicted)
    )
    tn = len(truth) - tp - fn - fp
    return {
        "true_positive": tp,
        "false_negative": fn,
        "false_positive": fp,
        "true_negative": tn,
        "positive_label": positive_label,
        "recall": tp / (tp + fn) if tp + fn else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "accuracy": (tp + tn) / len(truth),
        "sample_count": len(truth),
    }


def threshold_class_probabilities(
    probabilities: list,
    threshold: float = 0.5,
    positive_label: str | int = "positive",
    negative_label: str | int = "negative",
) -> dict:
    """Map positive-class probabilities to labels using p>=threshold.

    Integral float labels normalize to integers; strings are not numeric-coerced.
    Boolean, fractional, nonfinite and container labels are rejected.
    """
    p = _vector(probabilities, "probabilities", True)
    if (
        np.any(p > 1)
        or type(threshold) not in (int, float)
        or not math.isfinite(threshold)
        or not 0 <= threshold <= 1
    ):
        raise ValueError("Probabilities/threshold must be in[0,1]")
    positive_label = _binary_label(positive_label, "positive_label")
    negative_label = _binary_label(negative_label, "negative_label")
    if positive_label == negative_label:
        raise ValueError("Distinct string/integer labels required")
    return {
        "predicted": [positive_label if v >= threshold else negative_label for v in p],
        "threshold": threshold,
        "positive_label": positive_label,
        "negative_label": negative_label,
        "rule": "positive if probability>=threshold",
    }


def decision_cost_summary(
    truth: list,
    predicted: list,
    positive_label,
    false_positive_cost: float = 1.0,
    false_negative_cost: float = 1.0,
) -> dict:
    """Sum declared nonnegative binary FP/FN costs; no threshold optimization.

    Label semantics match BinaryClassificationMetrics: integral floats become
    integers, strings remain distinct, and boolean/fractional/nonfinite labels fail.
    """
    for v in [false_positive_cost, false_negative_cost]:
        if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
            raise ValueError("Costs must be finite nonnegative numbers")
    r = binary_classification_metrics(truth, predicted, positive_label)
    total = (
        r["false_positive"] * false_positive_cost
        + r["false_negative"] * false_negative_cost
    )
    return {
        "total_cost": total,
        "mean_cost": total / len(truth),
        "false_positive": r["false_positive"],
        "false_negative": r["false_negative"],
        "sample_count": len(truth),
        "cost_scope": "provided rows and declared FP/FN costs only",
    }


def probability_calibration_summary(
    truth: list, probabilities: list, positive_label, bins: int = 5
) -> dict:
    """Binary Brier/log-loss and fixed equal-width reliability bins.

    Empty bins retain null observed/predicted means. Log loss clips only at1e-15
    for numerical evaluation and reports this; no model/calibration is fitted.
    Integral float labels normalize to integers. Strings remain distinct from
    numbers; boolean, fractional, nonfinite and container labels are rejected.
    """
    p = _vector(probabilities, "probabilities", True)
    if np.any(p > 1) or not isinstance(truth, list) or len(truth) != len(p):
        raise ValueError("Require aligned binary labels and probabilities[0,1]")
    truth = [_binary_label(v, "truth label") for v in truth]
    positive_label = _binary_label(positive_label, "positive_label")
    if len(set(truth + [positive_label])) > 2:
        raise ValueError(
            "Only binary labels accepted; positive_label cannot be unrelated to two observed classes"
        )
    if type(bins) is not int or not 2 <= bins <= 20:
        raise ValueError("bins must be2..20")
    y = np.asarray([v == positive_label for v in truth], float)
    pp = np.clip(p, 1e-15, 1 - 1e-15)
    rows = []
    for i in range(bins):
        m = (p >= i / bins) & ((p < (i + 1) / bins) if i < bins - 1 else (p <= 1))
        n = int(m.sum())
        rows.append(
            {
                "lower": i / bins,
                "upper": (i + 1) / bins,
                "count": n,
                "mean_probability": float(p[m].mean()) if n else None,
                "observed_fraction": float(y[m].mean()) if n else None,
            }
        )
    return {
        "brier_score": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(pp) + (1 - y) * np.log(1 - pp))),
        "sample_count": len(y),
        "bins": rows,
        "log_loss_clip_epsilon": 1e-15,
        "scope": "descriptive fixed-bin reliability; no fit; absent classes limit generalization",
    }


def pca_reconstruction_error(
    training_features: list, features: list, n_components: int = 2
) -> dict:
    """Fit PCA only on training rows; reconstruct supplied heldout rows in input units."""
    from sklearn.decomposition import PCA

    a = _matrix(training_features)
    b = _matrix(features)
    if (
        a.shape[1] != b.shape[1]
        or type(n_components) is not int
        or not 1 <= n_components <= min(a.shape)
    ):
        raise ValueError("Matching widths and valid component count required")
    if len(a) < 2 or float(np.sum(np.var(a, axis=0))) <= 0:
        raise ValueError(
            "PCA variance ratio requires at least2 training rows and nonzero total variance"
        )
    p = PCA(n_components=n_components, svd_solver="full").fit(a)
    fit = p.inverse_transform(p.transform(b))
    mse = float(np.mean((b - fit) ** 2))
    return {
        "reconstruction_mse": mse,
        "reconstruction_rmse": math.sqrt(mse),
        "explained_variance_ratio": p.explained_variance_ratio_.tolist(),
        "n_components": n_components,
        "fit_row_count": len(a),
        "evaluation_row_count": len(b),
        "scope": "input feature units; train-only PCA; no automatic scaling",
    }


def group_train_test_split(
    features: list,
    targets: list,
    groups: list,
    test_fraction: float = 0.25,
    seed: int = 42,
) -> dict:
    """Reproducible group-disjoint split; fraction concerns groups, not row count."""
    from sklearn.model_selection import GroupShuffleSplit

    x = _matrix(features)
    if (
        not isinstance(targets, list)
        or not isinstance(groups, list)
        or len(targets) != len(x)
        or len(groups) != len(x)
        or any(type(v) not in (str, int) for v in groups)
        or len(set(groups)) < 2
    ):
        raise ValueError("Aligned targets/groups with at least2 groups required")
    if (
        type(seed) is not int
        or type(test_fraction) not in (int, float)
        or not 0 < test_fraction < 1
    ):
        raise ValueError("Valid seed and fraction required")
    a, b = next(
        GroupShuffleSplit(n_splits=1, test_size=test_fraction, random_state=seed).split(
            x, targets, groups
        )
    )
    return {
        "train_indices": a.tolist(),
        "test_indices": b.tolist(),
        "training_features": x[a].tolist(),
        "test_features": x[b].tolist(),
        "training_targets": [targets[i] for i in a],
        "test_targets": [targets[i] for i in b],
        "training_groups": sorted(set(groups[i] for i in a), key=str),
        "test_groups": sorted(set(groups[i] for i in b), key=str),
        "scope": "group-disjoint split; no class-stratification guarantee",
    }


def grouped_bootstrap_mean_interval(
    values: list,
    groups: list,
    confidence: float = 0.95,
    resamples: int = 1000,
    seed: int = 42,
) -> dict:
    """Percentile interval for equal-weight group-mean estimand via group resampling."""
    v = _vector(values)
    if (
        not isinstance(groups, list)
        or len(groups) != len(v)
        or any(type(g) not in (str, int) for g in groups)
        or len(set(groups)) < 2
    ):
        raise ValueError("At least2 aligned independent groups required")
    if (
        type(confidence) not in (int, float)
        or not 0 < confidence < 1
        or type(resamples) is not int
        or not 100 <= resamples <= 10000
        or type(seed) is not int
    ):
        raise ValueError(
            "confidence(0,1),resamples100..10000 and integer seed required"
        )
    ids = sorted(set(groups), key=str)
    means = np.asarray([np.mean([x for x, g in zip(v, groups) if g == k]) for k in ids])
    rng = np.random.default_rng(seed)
    boot = np.concatenate(
        [
            rng.choice(
                means, size=(min(128, resamples - start), len(means)), replace=True
            ).mean(axis=1)
            for start in range(0, resamples, 128)
        ]
    )
    lo, hi = np.quantile(boot, [(1 - confidence) / 2, 1 - (1 - confidence) / 2])
    return {
        "mean": float(means.mean()),
        "interval": [float(lo), float(hi)],
        "group_count": len(ids),
        "confidence": confidence,
        "resamples": resamples,
        "seed": seed,
        "estimand": "equal-weight mean of group means; groups assumed independent; percentile approximation",
    }


def time_series_split_records(times: list, cutoff: float, gap: float = 0.0) -> dict:
    """Partition time indices into past<=cutoff and future>cutoff+gap; no shuffling."""
    t = _vector(times, "times")
    if (
        type(cutoff) not in (int, float)
        or not math.isfinite(cutoff)
        or type(gap) not in (int, float)
        or not math.isfinite(gap)
        or gap < 0
    ):
        raise ValueError("Finite cutoff and nonnegative gap required")
    train = np.flatnonzero(t <= cutoff)
    test = np.flatnonzero(t > cutoff + gap)
    omit = np.flatnonzero((t > cutoff) & (t <= cutoff + gap))
    if not len(train) or not len(test):
        raise ValueError("Both past and future must be nonempty")
    return {
        "train_indices": train.tolist(),
        "test_indices": test.tolist(),
        "gap_indices": omit.tolist(),
        "train_max_time": float(t[train].max()),
        "test_min_time": float(t[test].min()),
        "cutoff": cutoff,
        "gap": gap,
        "scope": "indices preserve original row order; no model/preprocessor fitting",
    }
