"""Finite-support binomial probabilities with explicit floating tail semantics."""

import math


def binomial_probability_table(n: int, p: float) -> dict:
    """Return ordered k=0..n mass/CDF/survival and log-mass probabilities.

    n is an integer-valued number0..200; boolean and fractions are rejected.
    p is a finite real JSON number in[0,1], excluding boolean and strings.
    The caller establishes independent identical-probability Bernoulli trials.
    CDF[k]=P(X<=k), SF[k]=P(X>k); SF is computed directly, not1-CDF.
    No shift, estimated parameter, sampling, decision boundary or normal
    approximation is inserted. This is not a binomial-fit or independence test.
    Finite log mass is retained even if its float64 PMF underflows to zero.
    Null log mass denotes an exact zero mass at p=0 or1 (except n=0).
    Raw SciPy float64 probabilities are not renormalized; their total/error
    and numerical endpoint rounding are reported explicitly.
    """
    if type(n) not in (int, float) or not 0 <= n <= 200 or not float(n).is_integer():
        raise ValueError(
            "n must be an integer-valued number from0 through200, excluding boolean and fractions"
        )
    n = int(n)
    if type(p) not in (int, float):
        raise ValueError(
            "p must be a finite real JSON number in[0,1], excluding boolean and string"
        )
    if not 0 <= p <= 1:
        raise ValueError("p must be finite and lie in[0,1]")
    p = float(p)
    if not math.isfinite(p):
        raise ValueError("p must be finite and lie in[0,1]")
    import numpy as np
    import scipy
    from scipy.stats import binom

    k = np.arange(n + 1, dtype=int)
    mass = binom.pmf(k, n, p)
    cdf = binom.cdf(k, n, p)
    sf = binom.sf(k, n, p)
    logs = binom.logpmf(k, n, p)
    if any(
        not math.isfinite(float(v)) or v < 0 or v > 1 + 1e-12
        for arr in (mass, cdf, sf)
        for v in arr
    ):
        raise ValueError(
            "Binomial probability computation exceeded its finite numeric range"
        )
    exact_zero = [int(i) for i, v in enumerate(logs) if math.isinf(float(v)) and v < 0]
    if any(
        not math.isfinite(float(v)) and i not in exact_zero for i, v in enumerate(logs)
    ):
        raise ValueError(
            "Binomial log-mass computation exceeded its finite numeric range"
        )
    total = math.fsum(map(float, mass))
    if abs(total - 1) > 1e-10:
        raise ValueError(
            "Binomial mass total failed1e-10 numerical normalization check"
        )
    return dict(
        n=n,
        p=p,
        k=k.tolist(),
        pmf=mass.tolist(),
        cdf=cdf.tolist(),
        sf=sf.tolist(),
        log_pmf=[None if i in exact_zero else float(v) for i, v in enumerate(logs)],
        exact_zero_mass_k=exact_zero,
        rounded_zero_mass_k=[
            int(i) for i, v in enumerate(mass) if v == 0 and i not in exact_zero
        ],
        mass_sum=total,
        mass_sum_error=total - 1,
        mean=n * p,
        variance=n * p * (1 - p),
        scipy_version=scipy.__version__,
        numeric_protocol="SciPy binom float64 PMF,CDF,direct SF and log-PMF; ordered support0..n. Raw values are not renormalized. Tiny tails may underflow; finite log-PMF distinguishes rounded mass zero from mathematical endpoint zeros. SF[k] is P(X>k),not P(X>=k).",
        scope="Caller establishes fixed n and independent identically distributed Bernoulli trials with a common success probability. No parameter fit, dependence check, optional-stopping correction, scientific decision or coverage guarantee is inferred.",
    )
