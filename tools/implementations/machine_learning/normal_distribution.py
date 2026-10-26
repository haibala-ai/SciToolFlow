"""Bounded standard-normal probabilities and quantiles, without model inference."""

import math


def standard_normal_distribution(operation: str, values: list) -> dict:
    """Evaluate CDF, survival or inverse tails for caller-standardized quantities.

    CDF/SF arguments are finite dimensionless z values with abs(z)<=1e6.
    PPF/ISF arguments are finite probabilities strictly between zero and one.
    Return aligned float64 results; probability operations also retain stable
    log probabilities and log complements. A finite-z probability reported as
    zero or one is rounded, never a mathematical endpoint probability.
    This numerical primitive does not estimate a location, scale, noise model,
    null hypothesis, scientific decision, power, uncertainty or coverage.
    """
    if not isinstance(operation, str) or operation not in {"cdf", "sf", "ppf", "isf"}:
        raise ValueError("operation must be cdf, sf, ppf or isf")
    if not isinstance(values, list) or not 1 <= len(values) <= 10000:
        raise ValueError(
            "values must be a list containing 1..10000 finite JSON numbers"
        )
    for value in values:
        if type(value) not in (int, float):
            raise ValueError(
                "values must contain real JSON numbers, not boolean, null, string or nested cells"
            )
        if operation in {"cdf", "sf"}:
            # Magnitude comparison precedes float conversion for arbitrary-size ints.
            if abs(value) > 1e6 or not math.isfinite(value):
                raise ValueError(
                    "cdf/sf require finite standardized values with abs(z)<=1e6"
                )
        elif not 0 < value < 1:
            raise ValueError("ppf/isf require probabilities strictly between 0 and 1")
    import numpy as np
    import scipy
    from scipy.special import ndtr, ndtri, log_ndtr

    x = np.asarray(values, dtype=np.float64)
    log_result = log_complement = None
    if operation in {"cdf", "sf"}:
        z = x if operation == "cdf" else -x
        result = ndtr(z)
        log_result = log_ndtr(z).tolist()
        log_complement = log_ndtr(-z).tolist()
        rounded_zero = np.flatnonzero(result == 0).tolist()
        rounded_one = np.flatnonzero(result == 1).tolist()
    else:
        result = ndtri(x) if operation == "ppf" else -ndtri(x)
        rounded_zero = rounded_one = []
    if not np.all(np.isfinite(result)) or any(
        not math.isfinite(v)
        for arr in (log_result, log_complement)
        if arr is not None
        for v in arr
    ):
        raise ValueError(
            "Standard-normal computation exceeded finite float64 output range"
        )
    return dict(
        operation=operation,
        input_values=x.tolist(),
        results=result.tolist(),
        log_results=log_result,
        log_complements=log_complement,
        rounded_zero_indices=rounded_zero,
        rounded_one_indices=rounded_one,
        distribution="standard_normal",
        scipy_version=scipy.__version__,
        numeric_protocol="Ordered float64 SciPy special-function evaluation; SF uses Phi(-z), not 1-Phi(z); ISF uses -Phi_inverse(p), not Phi_inverse(1-p). Probability logs use log_ndtr directly. Every finite-z probability is mathematically strictly between zero and one; endpoint float results are explicitly indexed as rounding. A tiny negative log probability can itself round to -0.0 while its log complement remains available.",
        scope="A standard-normal numerical primitive only. Caller establishes standardization, units, sampling/error distribution, dependence, hypotheses, decision thresholds and interpretation. No fitted Gaussian model, empirical validity, scientific power, confidence or coverage guarantee is inferred.",
    )
