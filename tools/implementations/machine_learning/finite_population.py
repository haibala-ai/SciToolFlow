"""Finite-population coverage expectations, with no inferred sampling design."""

import math


def finite_population_coverage(
    population_size: int, feature_success_counts: list, sample_sizes: list
) -> dict:
    """Expected distinct features encountered in a uniform sample without replacement.

    population_size is an integer number of exchangeable sampling units,0..1e9.
    Each integer feature_success_counts[k] is the number of those units carrying
    feature k,0..population_size. Features may overlap: the expectation uses
    linearity and does not assume mutual independence or mutually exclusive
    categories. Caller must establish the actual scientific sampling unit.

    sample_sizes contains integer draws,each0..population_size;its order and
    duplicates are retained. Both lists have1..1000entries and their product is
    at most10000. At most2000000log-product terms are evaluated per call.
    Mathematically integral finite JSON numbers such as448.0 are accepted and
    converted without loss to integers;fractions,booleans and strings reject.

    For a feature present in K of N units and draw m,the probability of no hit is
    C(N-K,m)/C(N,m). Zero and certain-hit boundaries are evaluated exactly. Other
    cases use a finite log1p product with min(K,m) terms and -expm1(logP) for
    stable tiny hit probabilities. No simulation,normal approximation or silent
    probability clipping is used. This is the hypergeometric zero-hit formula.

    Returns population/feature counts and ordered analyses. Every analysis has
    sample_size,sample_fraction(null if N=0),feature_absence_probabilities in the
    original feature order,expected_detected_features,and
    expected_fraction_of_observed_features(null if every feature count is0).
    Expected values are finite real numbers,not rounded observed counts.

    This computes an expectation conditional on the supplied finite population
    and uniform sampling model. It provides no confidence interval,p-value,
    unseen-feature estimate,detection correction,spatial independence proof,
    extrapolation beyond N,or guarantee of population representativeness.
    """

    def count(value, limit, name):
        if (
            type(value) not in (int, float)
            or not 0 <= value <= limit
            or value != int(value)
        ):
            raise ValueError(
                name + " must be a finite mathematical integer in0.." + str(limit)
            )
        return int(value)

    population_size = count(population_size, 10**9, "population_size")
    for name, values in [
        ("feature_success_counts", feature_success_counts),
        ("sample_sizes", sample_sizes),
    ]:
        if not isinstance(values, list) or not 1 <= len(values) <= 1000:
            raise ValueError(name + " must contain1..1000integers")
        for value in values:
            count(value, population_size, name)
    if len(feature_success_counts) * len(sample_sizes) > 10000:
        raise ValueError("At most10000 feature-by-sample-size probabilities")
    n = population_size
    feature_success_counts = [int(v) for v in feature_success_counts]
    sample_sizes = [int(v) for v in sample_sizes]
    work = sum(
        min(k, m)
        for m in sample_sizes
        for k in feature_success_counts
        if k and m and k + m <= n
    )
    if work > 2000000:
        raise ValueError("Requested exact stable products exceed2000000terms")
    observed = sum(k > 0 for k in feature_success_counts)
    analyses = []
    for m in sample_sizes:
        absence, hits = [], []
        for k in feature_success_counts:
            if m == 0 or k == 0:
                miss, hit = 1.0, 0.0
            elif k + m > n:
                miss, hit = 0.0, 1.0
            else:
                small, large = sorted([k, m])
                # Symmetry in k,m keeps both the work and cancellation bounded.
                log_miss = math.fsum(math.log1p(-large / (n - j)) for j in range(small))
                miss, hit = math.exp(log_miss), -math.expm1(log_miss)
            absence.append(miss)
            hits.append(hit)
        expected = math.fsum(hits)
        analyses.append(
            {
                "sample_size": m,
                "sample_fraction": m / n if n else None,
                "feature_absence_probabilities": absence,
                "expected_detected_features": expected,
                "expected_fraction_of_observed_features": (
                    expected / observed if observed else None
                ),
            }
        )
    return {
        "population_size": n,
        "feature_count": len(feature_success_counts),
        "nonzero_feature_count": observed,
        "analyses": analyses,
        "scope": "Uniform without-replacement finite-population expectation;overlapping features permitted;sampling unit and applicability supplied by caller;no unseen-feature or inferential claims",
    }
