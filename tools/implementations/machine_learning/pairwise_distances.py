"""Bounded deterministic pairwise distances on declared numeric feature rows."""

import math
import numpy as np
from scipy.spatial.distance import cdist
from threadpoolctl import threadpool_limits


def pairwise_numeric_distances(
    values: list, other: list | None = None, metric: str = "euclidean"
) -> dict:
    """Compute one explicitly selected pairwise distance,without preprocessing.

    Input rows are finite numeric vectors with equal nonzero feature width;
    bool/null,ragged/empty vectors rejected. At most10000 total input numeric
    cells and10000 output distances. With other=null compare values with itself;
    otherwise columns correspond to other rows. Shared feature order/units are
    caller responsibilities. No implicit scaling,imputation or row removal.
    Euclidean/cityblock distances inherit feature units only when those units
    are commensurate. Cosine returns 1-cos(theta), not the angle theta or Euclidean distance;
    it need not satisfy the triangle inequality.
    any all-zero row makes it undefined and rejects the whole call.
    Bray-Curtis requires nonnegative numeric values;zero-vs-positive is1,
    two zero rows have undefined denominator and reject the whole call.
    Jaccard requires numeric0/1presence indicators;no automatic binarization.
    Following SciPy,empty-versus-empty Jaccard dissimilarity is0 explicitly.
    Nonfinite computed distances (including numeric overflow) reject the call.
    Distances do not establish statistical independence,causality,cluster
    validity or suitability of the selected metric for a scientific question.
    """

    def matrix(rows, name):
        if (
            not isinstance(rows, list)
            or not rows
            or len(rows) > 10000
            or any(not isinstance(r, list) or not r for r in rows)
        ):
            raise ValueError(name + " requires bounded nonempty numeric rows")
        width = len(rows[0])
        if len(rows) * width > 10000 or any(len(r) != width for r in rows):
            raise ValueError(name + " is ragged or exceeds 10000 cells")
        if any(
            type(v) not in (int, float) or not math.isfinite(v) for r in rows for v in r
        ):
            raise ValueError(name + " accepts only finite numbers,not boolean or null")
        return np.asarray(rows, dtype=float)

    if not isinstance(metric, str) or metric not in {
        "euclidean",
        "cityblock",
        "cosine",
        "braycurtis",
        "jaccard",
    }:
        raise ValueError("Unknown declared metric")
    left = matrix(values, "values")
    self_comparison = other is None
    right = left if self_comparison else matrix(other, "other")
    if (
        left.shape[1] != right.shape[1]
        or len(left) * len(right) > 10000
        or left.size + (0 if self_comparison else right.size) > 10000
    ):
        raise ValueError("Feature width, input size or output cell bound mismatch")
    zero_left = np.all(left == 0, axis=1)
    zero_right = np.all(right == 0, axis=1)
    if metric == "cosine" and (np.any(zero_left) or np.any(zero_right)):
        raise ValueError("Cosine dissimilarity is undefined for zero vectors")
    if metric == "braycurtis":
        if np.any(left < 0) or np.any(right < 0):
            raise ValueError("Bray-Curtis requires nonnegative values")
        if np.any(zero_left) and np.any(zero_right):
            raise ValueError("Bray-Curtis zero-versus-zero denominator is undefined")
    if metric == "jaccard" and (
        not np.all((left == 0) | (left == 1)) or not np.all((right == 0) | (right == 1))
    ):
        raise ValueError(
            "Jaccard requires explicit numeric 0/1 presence indicators; counts are not implicitly binarized"
        )
    with threadpool_limits(limits=1):
        distances = cdist(left, right, metric=metric)
    if not np.all(np.isfinite(distances)):
        raise ValueError("Computed distances exceed finite representable range")
    return {
        "distances": distances.tolist(),
        "shape": [len(left), len(right)],
        "left_row_count": len(left),
        "right_row_count": len(right),
        "feature_count": left.shape[1],
        "metric": metric,
        "comparison": "self" if self_comparison else "cross",
        "zero_policy": {
            "euclidean": "zero vectors valid",
            "cityblock": "zero vectors valid",
            "cosine": "any zero vector rejected",
            "braycurtis": "zero/positive=1;zero/zero rejected",
            "jaccard": "numericbinary;empty/empty=0",
        }[metric],
        "scope": "Declared metric on unchanged ordered features;no automatic scaling,binarization,imputation,inferenceorclusterselection.",
    }
