"""Bounded unnormalized graph Laplacian; no network inference or task decision."""

import math
import numpy as np


def graph_laplacian(adjacency: list) -> dict:
    """Construct L=diag(sum(A,axis=1))-A for an undirected weighted graph.

    Supply a 1..100-node square numeric adjacency with exactly symmetric weights,
    exactly zero diagonal and finite nonnegative entries, excluding booleans.
    Floating conversion and arithmetic use float64. Values outside its finite
    range, or overflowing degree sums, fail explicitly. No clipping, tolerance,
    self-loop removal, symmetrization, normalization or missing-edge inference.
    Isolated nodes and a one-node zero graph are valid. This primitive does not
    compute connected components, modes, cutoffs or a scientific interpretation.
    """
    if (
        not isinstance(adjacency, list)
        or not 1 <= len(adjacency) <= 100
        or any(
            not isinstance(row, list) or len(row) != len(adjacency) for row in adjacency
        )
    ):
        raise ValueError(
            "adjacency must be a square list matrix with 1..100 nodes and at most 10000 cells"
        )
    for i, row in enumerate(adjacency):
        for j, value in enumerate(row):
            if type(value) not in (int, float):
                raise ValueError(
                    "adjacency weights must be finite numeric scalars,not booleans or containers"
                )
            try:
                converted = float(value)
            except (OverflowError, ValueError) as error:
                raise ValueError(
                    "adjacency weight exceeds finite float64 range"
                ) from error
            if not math.isfinite(converted) or value < 0:
                raise ValueError(
                    "adjacency weights must be nonnegative and finite within float64 range"
                )
            if i == j and value != 0:
                raise ValueError(
                    "adjacency diagonal must be exactly zero;self-loops are not removed"
                )
            if value != adjacency[j][i]:
                raise ValueError(
                    "adjacency must be exactly symmetric;no implicit symmetrization"
                )
    a = np.asarray(adjacency, dtype=np.float64)
    try:
        with np.errstate(over="raise", invalid="raise"):
            degrees = np.sum(a, axis=1, dtype=np.float64)
            laplacian = np.diag(degrees) - a
    except FloatingPointError as error:
        raise ValueError(
            "float64 degree sum or Laplacian arithmetic overflows"
        ) from error
    if not np.isfinite(degrees).all() or not np.isfinite(laplacian).all():
        raise ValueError("degree and Laplacian outputs must be finite")
    return {
        "laplacian": laplacian.tolist(),
        "degrees": degrees.tolist(),
        "node_count": len(a),
        "method": "Unnormalized undirected weighted graph Laplacian:L=diag(row sums)-A",
        "numeric_protocol": "Input symmetry and zero diagonal are checked exactly before float64 conversion;outputs use finite float64 arithmetic",
        "scope": "Only supplied graph weights;isolated nodes retained;no connected-component,cutoff,normal-mode or physical-dynamics inference",
    }
