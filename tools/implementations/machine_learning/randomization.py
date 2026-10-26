"""Bounded exact paired-assignment inference, with no inferred study design."""

from collections import Counter
from fractions import Fraction
import math


def paired_randomization_test(
    sample_a: list,
    sample_b: list,
    alternative: str = "two-sided",
    return_distribution: bool = False,
) -> dict:
    """Enumerate independent within-pair swaps for an equal-pair mean contrast.

    Require 2..16 supplied pairs and finite numeric cells with absolute magnitude
    at most 1e100. Input pairs, their independence, equal assignment probability
    and applicability of a sharp no-effect null must be justified by the caller.
    This tool does not infer randomization, sampling units or technical-repeat
    independence from array shape. It does not test a weak mean-zero null under
    arbitrary individual effects and does not return a confidence interval.

    Fraction(str(number)) fixes the supplied decimal-value interpretation.
    Every sign assignment counts, including repeated null statistics. Tails are
    inclusive; two-sided means absolute statistic at least absolute observed.
    No Monte Carlo approximation, floating tie epsilon or +1 correction is used.
    Optional histogram is complete only when at most 4096 unique values occur;
    otherwise it is explicitly omitted, while the full enumeration is retained.
    """
    if (
        not isinstance(sample_a, list)
        or not isinstance(sample_b, list)
        or not 2 <= len(sample_a) == len(sample_b) <= 16
    ):
        raise ValueError("Require two aligned lists containing 2..16 pairs")
    for name, values in [("sample_a", sample_a), ("sample_b", sample_b)]:
        if any(
            type(value) not in (int, float)
            or abs(value) > 1e100
            or not math.isfinite(value)
            for value in values
        ):
            raise ValueError(
                name
                + ": require finite real JSON numbers with abs(value)<=1e100; no boolean, string or null cells"
            )
    if not isinstance(alternative, str) or alternative not in {
        "two-sided",
        "greater",
        "less",
    }:
        raise ValueError("alternative must be two-sided, greater or less")
    if type(return_distribution) is not bool:
        raise ValueError("return_distribution must be a boolean")
    differences = [
        Fraction(str(a)) - Fraction(str(b)) for a, b in zip(sample_a, sample_b)
    ]
    n = len(differences)
    observed_sum = sum(differences, Fraction(0))
    null_sums = Counter({Fraction(0): 1})
    for difference in differences:
        updated = Counter()
        for value, multiplicity in null_sums.items():
            updated[value + difference] += multiplicity
            updated[value - difference] += multiplicity
        null_sums = updated
    total = 2**n
    assert sum(null_sums.values()) == total
    if alternative == "two-sided":
        extreme = sum(
            multiplicity
            for value, multiplicity in null_sums.items()
            if abs(value) >= abs(observed_sum)
        )
    elif alternative == "greater":
        extreme = sum(
            multiplicity
            for value, multiplicity in null_sums.items()
            if value >= observed_sum
        )
    else:
        extreme = sum(
            multiplicity
            for value, multiplicity in null_sums.items()
            if value <= observed_sum
        )
    underflow = []

    def numeric(value, pointer):
        converted = float(value)
        if value and converted == 0:
            underflow.append(pointer)
        return converted

    histogram = None
    distribution_status = "not_requested"
    if return_distribution:
        if len(null_sums) <= 4096:
            distribution_status = "complete"
            histogram = [
                {
                    "mean_difference": numeric(
                        value / n, "/null_distribution/" + str(i) + "/mean_difference"
                    ),
                    "mean_difference_exact": str(value / n),
                    "multiplicity": multiplicity,
                }
                for i, (value, multiplicity) in enumerate(sorted(null_sums.items()))
            ]
        else:
            distribution_status = "omitted_above4096_unique_values"
    observed = observed_sum / n
    limits = [min(null_sums) / n, max(null_sums) / n]
    result = {
        "observed_mean_difference": numeric(observed, "/observed_mean_difference"),
        "observed_mean_difference_exact": str(observed),
        "pair_count": n,
        "assignment_count": total,
        "extreme_assignment_count": extreme,
        "p_value": extreme / total,
        "p_value_exact": str(Fraction(extreme, total)),
        "alternative": alternative,
        "unique_null_statistics": len(null_sums),
        "null_statistic_range": [
            numeric(value, "/null_statistic_range/" + str(i))
            for i, value in enumerate(limits)
        ],
        "null_statistic_range_exact": list(map(str, limits)),
        "null_distribution": histogram,
        "distribution_status": distribution_status,
        "numeric_underflow_fields": underflow,
        "input_orientation": "sample_a minus sample_b; equal weight per provided pair",
        "method": "Exact independent within-pair sign-flip randomization of the equal-pair mean difference",
        "numeric_protocol": "Fraction(str(number)); inclusive tails; every assignment multiplicity retained; no floating tie tolerance, Monte Carlo approximation or +1 correction",
        "scope": "Conditional on justified independent equal-probability within-pair assignments and a sharp no-effect null. No study design, sampling unit, repeat independence, weak-mean-null validity, confidence interval or population transport is inferred.",
    }
    return result
