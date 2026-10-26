"""Bounded fixed-stratum, independent-cluster mean bootstrap.

This is a statistical primitive, not a validator of a sampling design. Source
units, independent units, strata, target weights and working exchangeability
assumptions must be justified by the caller.
"""

import math
import numpy as np


def stratified_cluster_mean_interval(
    values: list,
    groups: list,
    strata: list,
    stratum_weights: list,
    confidence: float = 0.95,
    resamples: int = 2000,
    seed: int = 42,
) -> dict:
    """Fixed-weight percentile interval by resampling cluster means within strata.

    Reduce repeated rows to each independent cluster's arithmetic mean. A cluster
    ID is global and must belong to exactly one stratum. Retain the observed
    cluster count separately in each stratum; draw those cluster means with
    replacement, combine stratum means with the caller's fixed positive weights.
    At least two clusters per stratum are required. No finite-population
    correction, uncertainty in weights, exchangeability test or interval-coverage
    guarantee is inferred. Output remains in the units of values.

    RNG protocol: NumPy PCG64(seed), canonical strata and cluster order by
    (type name,string value), chunks of128 bootstrap replicates; within each
    chunk visit strata in canonical order and draw a (chunk,cluster_count)
    integer-index array. Percentiles use NumPy's linear quantile convention.
    This protocol differs from R's RNG and from a pooled cluster bootstrap.
    """
    if (
        not isinstance(values, list)
        or not 1 <= len(values) <= 10000
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)
    ):
        raise ValueError("values must contain1..10000 finite numeric observations")
    for name, labels in [("groups", groups), ("strata", strata)]:
        if (
            not isinstance(labels, list)
            or len(labels) != len(values)
            or any(
                type(v) not in (str, int) or (type(v) is str and not v) for v in labels
            )
        ):
            raise ValueError(
                name
                + " must contain aligned nonempty string or integer IDs; boolean/null/container IDs are invalid"
            )
    if (
        type(confidence) not in (int, float)
        or not math.isfinite(confidence)
        or not 0 < confidence < 1
        or type(resamples) is not int
        or not 100 <= resamples <= 10000
        or type(seed) is not int
        or not 0 <= seed < 2**64
    ):
        raise ValueError(
            "confidence must be in(0,1),resamples100..10000,and seed an unsigned64-bit integer"
        )
    order = lambda value: (type(value).__name__, str(value))
    cluster_values = {}
    cluster_stratum = {}
    for v, g, s in zip(values, groups, strata):
        if g in cluster_stratum and cluster_stratum[g] != s:
            raise ValueError(
                "Each global cluster ID must belong to exactly one stratum"
            )
        cluster_stratum[g] = s
        cluster_values.setdefault(g, []).append(float(v))
    observed_strata = sorted(set(strata), key=order)
    if len(observed_strata) > 100:
        raise ValueError("At most100 observed strata are supported")
    if not isinstance(stratum_weights, list) or len(stratum_weights) != len(
        observed_strata
    ):
        raise ValueError(
            "stratum_weights must list every observed stratum exactly once"
        )
    weights = {}
    for row in stratum_weights:
        if (
            not isinstance(row, dict)
            or set(row) != {"stratum", "weight"}
            or type(row["stratum"]) not in (str, int)
            or row["stratum"] not in observed_strata
            or row["stratum"] in weights
            or type(row["weight"]) not in (int, float)
            or not math.isfinite(row["weight"])
            or row["weight"] <= 0
        ):
            raise ValueError(
                "Each weight record requires one distinct observed stratum and one finite strictly positive weight"
            )
        weights[row["stratum"]] = float(row["weight"])
    if not math.isclose(math.fsum(weights.values()), 1.0, rel_tol=0, abs_tol=1e-12):
        raise ValueError(
            "Fixed stratum weights must sum to1; weights are not silently normalized"
        )
    panels = []
    summaries = []
    for s in observed_strata:
        ids = sorted([g for g in cluster_values if cluster_stratum[g] == s], key=order)
        if len(ids) < 2:
            raise ValueError(
                "Every stratum requires at least2 independent clusters for the requested bootstrap"
            )
        means = np.array(
            [math.fsum(cluster_values[g]) / len(cluster_values[g]) for g in ids]
        )
        if not np.isfinite(means).all():
            raise ValueError("Cluster means exceed finite float64 range")
        panels.append(means)
        summaries.append(
            {
                "stratum": s,
                "weight": weights[s],
                "cluster_ids": ids,
                "cluster_count": len(ids),
                "observation_count": sum(len(cluster_values[g]) for g in ids),
                "mean": float(np.mean(means)),
            }
        )
    rng = np.random.Generator(np.random.PCG64(seed))
    bootstrap = np.empty(resamples)
    for start in range(0, resamples, 128):
        count = min(128, resamples - start)
        sample = np.zeros(count)
        for s, means in zip(observed_strata, panels):
            indices = rng.integers(0, len(means), size=(count, len(means)))
            sample += weights[s] * means[indices].mean(axis=1)
        bootstrap[start : start + count] = sample
    if not np.isfinite(bootstrap).all():
        raise ValueError("Bootstrap means exceed finite float64 range")
    tail = (1 - confidence) / 2
    interval = np.quantile(bootstrap, [tail, 1 - tail], method="linear").tolist()
    mean = math.fsum(row["weight"] * row["mean"] for row in summaries)
    if not math.isfinite(mean):
        raise ValueError("Weighted mean exceeds finite float64 range")
    return {
        "mean": mean,
        "interval": interval,
        "group_count": len(cluster_values),
        "stratum_count": len(observed_strata),
        "stratum_summaries": summaries,
        "confidence": confidence,
        "resamples": resamples,
        "seed": seed,
        "estimand": "Fixed-weight sum of stratum means of equally weighted independent cluster means; repeated rows remain within clusters.",
        "scope": "Within-stratum cluster exchangeability and cross-cluster independence are working assumptions, not tested. Fixed stratum composition and weights; percentile approximation without guaranteed coverage or finite-population correction.",
        "random_protocol": "PCG64; canonical(type name,string value) strata/clusters;128replicate chunks,then strata; integer-index draws;linear percentile.",
    }
