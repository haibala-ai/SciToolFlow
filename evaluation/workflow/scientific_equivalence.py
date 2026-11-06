"""Lossless distance representations and bounded scientific partition checks."""
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from itertools import product
import math
from .values import MissingEvidence, _number


def distance_matrix(value, reference):
    """Expand standard upper-triangle order only for a true distance matrix."""
    n = len(reference) if isinstance(reference, list) else 0
    if (not 2 <= n <= 256 or any(not isinstance(row, list) or len(row) != n
                               or any(not _number(x) for x in row) for row in reference)
            or any(abs(reference[i][i]) > 1e-8 for i in range(n))
            or any(reference[i][j] < -1e-8 or not math.isclose(reference[i][j], reference[j][i],
                    rel_tol=1e-8, abs_tol=1e-8) for i in range(n) for j in range(n))):
        raise MissingEvidence('Require a complete finite symmetric distance reference')
    if not isinstance(value, list):
        raise MissingEvidence('Distance answer must be a matrix or condensed upper triangle')
    if len(value) == n and all(isinstance(row, list) and len(row) == n
                             and all(_number(x) for x in row) for row in value):
        return value
    if len(value) != n*(n-1)//2 or not all(_number(x) for x in value):
        raise MissingEvidence('Incomplete or ambiguous distance representation')
    matrix = [[0.0]*n for _ in range(n)]
    cursor = 0
    for i in range(n):
        for j in range(i+1, n):
            matrix[i][j] = matrix[j][i] = value[cursor]
            cursor += 1
    return matrix


def memberships(labels):
    if (not isinstance(labels, list) or not 2 <= len(labels) <= 256
            or any(type(x) not in (str, int) or isinstance(x, str) and not 1 <= len(x) <= 128 for x in labels)):
        raise MissingEvidence('Require bounded unambiguous cluster labels')
    names = {}
    return [names.setdefault((type(x), x), len(names)) for x in labels]


def features(value, maximum=256):
    if (not isinstance(value, list) or not 2 <= len(value) <= maximum
            or not isinstance(value[0], list) or not 1 <= len(value[0]) <= 16
            or any(not isinstance(row, list) or len(row) != len(value[0])
                   or any(not _number(x) or abs(x) > 1e12 for x in row) for row in value)):
        raise MissingEvidence('Require a bounded finite feature matrix')
    return tuple(tuple(row) for row in value)


@lru_cache(maxsize=128)
def _optimal_bipartitions(matrix):
    # Scientific ties are computed independently of the submitted answer.
    # Fraction(str(...)) preserves the explicitly provided finite decimal data.
    points = tuple(tuple(Fraction(str(x)) for x in row) for row in matrix)
    n, width = len(points), len(points[0])
    best, profiles = None, []
    for tail in product((0, 1), repeat=n-1):
        if 1 not in tail:
            continue
        labels = (0, *tail)
        cost = Fraction(0)
        for label in (0, 1):
            group = [row for row, k in zip(points, labels) if k == label]
            center = [sum(row[j] for row in group)/len(group) for j in range(width)]
            cost += sum((row[j]-center[j])**2 for row in group for j in range(width))
        if best is None or cost < best:
            best, profiles = cost, [labels]
        elif cost == best:
            profiles.append(labels)
    return tuple(profiles)


def optimal_bipartition_profiles(value):
    matrix = features(value, maximum=12)
    return [{'memberships': list(row), 'noise_mask': None} for row in _optimal_bipartitions(matrix)]


def partition_silhouette(value, labels):
    matrix, group = features(value), memberships(labels)
    n = len(matrix)
    if len(group) != n or not 2 <= len(set(group)) < n:
        raise MissingEvidence('Silhouette requires aligned rows and 2..n-1 clusters')
    sizes = Counter(group)
    distances = [[math.dist(a, b) for b in matrix] for a in matrix]
    scores = []
    for i in range(n):
        if sizes[group[i]] == 1:
            scores.append(0.0)
            continue
        within = sum(distances[i][j] for j in range(n) if i != j and group[j] == group[i])/(sizes[group[i]]-1)
        other = min(sum(distances[i][j] for j in range(n) if group[j] == k)/sizes[k]
                    for k in sizes if k != group[i])
        scores.append((other-within)/max(other, within) if max(other, within) else 0.0)
    return sum(scores)/n


def partition_adjusted_rand(first, second):
    a, b = memberships(first), memberships(second)
    if len(a) != len(b):
        raise MissingEvidence('ARI requires the same ordered objects')
    choose = lambda n: n*(n-1)//2
    cells = sum(choose(n) for n in Counter(zip(a, b)).values())
    rows = sum(choose(n) for n in Counter(a).values())
    columns = sum(choose(n) for n in Counter(b).values())
    expected = Fraction(rows*columns, choose(len(a)))
    maximum = Fraction(rows+columns, 2)
    return float((cells-expected)/(maximum-expected)) if maximum != expected else 1.0
