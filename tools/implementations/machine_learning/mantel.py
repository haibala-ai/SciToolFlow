"""Bounded Pearson distance association with transparent label randomization."""

import math
import numpy as np


def _integer(value, name, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite mathematical integer")
    try:
        valid = math.isfinite(value) and int(value) == value
    except (OverflowError, ValueError):
        valid = False
    if not valid or not lower <= value <= upper:
        raise ValueError(f"{name} must be in [{lower},{upper}]")
    return int(value)


def _distance_matrix(value, name):
    if not isinstance(value, list) or not 3 <= len(value) <= 100:
        raise ValueError(f"{name} must be a 3..100 by 3..100 square list")
    n = len(value)
    if any(not isinstance(row, list) or len(row) != n for row in value):
        raise ValueError(f"{name} must be square,not ragged")
    for i, row in enumerate(value):
        for j, item in enumerate(row):
            if isinstance(item, bool) or not isinstance(item, (int, float)):
                raise ValueError(f"{name}[{i}][{j}] must be a finite number,not bool")
            try:
                finite = math.isfinite(item)
            except OverflowError:
                finite = False
            if not finite or item < 0:
                raise ValueError(f"{name} must contain finite nonnegative numbers")
            if i == j and item != 0:
                raise ValueError(f"{name} diagonal must be exactly zero")
            if j < i and item != value[j][i]:
                raise ValueError(
                    f"{name} must be exactly symmetric;no averaging is done"
                )
    return np.asarray(value, dtype=float)


def mantel_correlation(
    distance_a: list,
    distance_b: list,
    permutations: int = 999,
    seed: int = 42,
    alternative: str = "two-sided",
):
    """Correlate matched symmetric distance matrices and optionally permute labels.

    Both matrices must be square lists of equal size 3..100 with finite numeric
    entries,exact symmetry,nonnegative distances and exact zero diagonals. Bool,
    missing values and strings fail. The caller must match object identities and
    order beforehand;there is no ID inference,imputation or symmetrization.
    Triangle inequalities and Euclidean geometry are not required or certified.

    The statistic is Pearson r on row-major upper-triangle distances. Constant
    upper triangles fail clearly;near-constant input emits an explicit warning.
    Positive scaling precedes centering to avoid overflow and does not change r.
    This primitive does not compute an IID Pearson significance test on pairs.

    permutations is 0..9999,seed is 0..2**32-1,and permutations*n*(n-1)/2 cannot
    exceed 5000000. Each draw uses numpy.default_rng(seed).permutation(n) and
    simultaneously reorders rows and columns of distance_a. Draws are independent
    uniform label permutations with replacement,so identity and duplicate draws
    may occur. greater counts r_perm>=r,less counts r_perm<=r,and two-sided counts
    abs(r_perm)>=abs(r). Numerical ties use tolerance 100*float64_epsilon*max(1,abs(r)),
    so algebraically equal statistics are not separated by rounding noise.
    The same numerical correlation routine handles observed and permuted values.
    Reported p_value=(extreme_count+1)/(permutations+1). With zero permutations,
    p_value and extreme_count are null;the statistic remains available.

    The caller chooses geometry,object matching,alternative and a scientifically
    defensible permutation scheme. This tool only implements unrestricted labels;
    it cannot establish exchangeability,handle spatial/paired/blocked designs,
    remove confounding or justify ecological,causal or population inference. A
    numerical randomization fraction is inferential only under valid assumptions.
    """
    a = _distance_matrix(distance_a, "distance_a")
    b = _distance_matrix(distance_b, "distance_b")
    if a.shape != b.shape:
        raise ValueError("distance matrices must have identical shape and object order")
    permutations = _integer(permutations, "permutations", 0, 9999)
    seed = _integer(seed, "seed", 0, 2**32 - 1)
    if alternative not in ("two-sided", "greater", "less"):
        raise ValueError("alternative must be two-sided,greater or less")
    n = len(a)
    pairs = n * (n - 1) // 2
    if permutations * pairs > 5_000_000:
        raise ValueError("permutations*pair_count exceeds the 5000000 work limit")
    ii, jj = np.triu_indices(n, 1)
    warnings = []

    def center(matrix, name):
        vector = matrix[ii, jj]
        scale = float(np.max(vector))
        if scale == 0 or np.all(vector == vector[0]):
            raise ValueError(
                f"{name} upper-triangle distances are constant;Pearson r undefined"
            )
        scaled = matrix / scale
        values = scaled[ii, jj]
        mean = float(np.mean(values))
        deviation = values - mean
        norm = float(np.linalg.norm(deviation))
        if not math.isfinite(norm) or norm == 0:
            raise ValueError(
                f"{name} numerical centering has no usable finite variation"
            )
        if norm < 1e-13 * abs(mean):
            warnings.append(
                f"{name}:near-constant distances may reduce floating precision"
            )
        return scaled, mean, norm

    scaled_a, mean_a, norm_a = center(a, "distance_a")
    scaled_b, mean_b, norm_b = center(b, "distance_b")
    normalized_b = (scaled_b[ii, jj] - mean_b) / norm_b

    def statistic(order):
        values = scaled_a[order[ii], order[jj]]
        result = float(np.dot((values - mean_a) / norm_a, normalized_b))
        if not math.isfinite(result):
            raise ValueError("nonfinite correlation encountered")
        return max(-1.0, min(1.0, result))

    r = statistic(np.arange(n))
    tie_tolerance = 100 * np.finfo(float).eps * max(1.0, abs(r))
    extreme = None
    p_value = None
    if permutations:
        rng = np.random.default_rng(seed)
        extreme = 0
        for _ in range(permutations):
            sample = statistic(rng.permutation(n))
            if alternative == "two-sided":
                is_extreme = abs(sample) >= abs(r) - tie_tolerance
            elif alternative == "greater":
                is_extreme = sample >= r - tie_tolerance
            else:
                is_extreme = sample <= r + tie_tolerance
            extreme += int(is_extreme)
        p_value = (extreme + 1) / (permutations + 1)
    return {
        "correlation": r,
        "p_value": p_value,
        "object_count": n,
        "pair_count": pairs,
        "permutations": permutations,
        "extreme_count": extreme,
        "seed": seed,
        "alternative": alternative,
        "tie_tolerance": float(tie_tolerance),
        "method": "Pearson upper-triangle correlation;unrestricted first-matrix label permutations",
        "rng": "numpy.default_rng(PCG64)",
        "warnings": warnings,
        "scope": "Objects,not pairwise distances,are the randomization units. Unrestricted exchangeability is not verified;no blocked,paired,spatial,causal or population inference is established by this numerical result.",
    }
