"""Shared complete-family P-value correction and hypergeometric tail kernels."""

import math


def adjust_complete_family(p_values, method):
    if method not in {"bh", "by", "bonferroni"}:
        raise ValueError("method must be bh, by, or bonferroni")
    if not isinstance(p_values, list) or len(p_values) > 60000 or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in p_values):
        raise ValueError("A complete family needs at most 60000 finite P values in [0,1]")
    size = len(p_values)
    if method == "bonferroni":
        return [min(1.0, p * size) for p in p_values]
    factor = math.fsum(1 / i for i in range(1, size + 1)) if method == "by" else 1.0
    ranked = sorted(range(size), key=lambda i: p_values[i])
    output = [0.0] * size
    running = 1.0
    for rank_index in range(size - 1, -1, -1):
        i = ranked[rank_index]
        running = min(running, p_values[i] * size * factor / (rank_index + 1))
        output[i] = running
    return output


def enrichment_tail(N, K, n, k):
    from scipy.stats import hypergeom
    if any(type(v) is not int for v in [N, K, n, k]) or not 0 <= K <= N or not 0 <= n <= N or not max(0, n + K - N) <= k <= min(n, K):
        raise ValueError("Invalid hypergeometric counts")
    if not N:
        raise ValueError("Universe must be nonempty")
    p = float(hypergeom.sf(k - 1, N, K, n))
    logp = float(hypergeom.logsf(k - 1, N, K, n))
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("Hypergeometric tail is not a finite probability")
    expected = n * K / N
    return dict(p_value=p, log_p_value=logp if math.isfinite(logp) else None, p_value_underflow=p == 0.0, expected_overlap=expected, fold_enrichment=k / expected if expected else None)
