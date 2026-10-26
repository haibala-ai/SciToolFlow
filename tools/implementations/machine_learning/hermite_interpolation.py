"""Bounded derivative-constrained one-dimensional interpolation."""

import math
import numpy as np
from scipy.interpolate import CubicHermiteSpline
from threadpoolctl import threadpool_limits


def cubic_hermite_interpolate(
    x: list, y: list, derivatives: list, query_x: list
) -> dict:
    """Evaluate a piecewise cubic Hermite interpolant and its first derivative.

    x, y and derivatives are finite real 1D lists of equal length 2..1000;
    x is strictly increasing. derivatives are dy/dx at each knot, not forces
    unless the caller supplies the correct sign and units. query_x is a finite
    list of 1..10000 points inside the closed source range; its order is kept.
    No extrapolation, smoothing, monotonicity or stationary-point search occurs.
    Overshoots are valid interpolation behavior. Invalid/nonfinite numerical
    results reject the whole call. Units and scientific model validity remain
    the caller's responsibility.
    """

    def vector(value, name, lower, upper):
        if not isinstance(value, list) or not lower <= len(value) <= upper:
            raise ValueError(f"{name} must be a 1D list of length {lower}..{upper}")
        out = []
        for entry in value:
            if type(entry) not in (int, float):
                raise ValueError(
                    f"{name} entries must be finite real numbers, excluding booleans"
                )
            try:
                number = float(entry)
            except (OverflowError, ValueError) as error:
                raise ValueError(
                    f"{name} cannot be represented as finite float64"
                ) from error
            if not math.isfinite(number):
                raise ValueError(f"{name} entries must be finite")
            out.append(number)
        return np.asarray(out, dtype=float)

    xx = vector(x, "x", 2, 1000)
    yy = vector(y, "y", 2, 1000)
    dd = vector(derivatives, "derivatives", 2, 1000)
    qq = vector(query_x, "query_x", 1, 10000)
    if len(xx) != len(yy) or len(xx) != len(dd):
        raise ValueError("x, y and derivatives must have equal lengths")
    if any(b <= a for a, b in zip(xx[:-1], xx[1:])):
        raise ValueError("x must be strictly increasing with distinct knots")
    if np.any(qq < xx[0]) or np.any(qq > xx[-1]):
        raise ValueError("query_x cannot extrapolate outside the closed source range")
    try:
        with (
            threadpool_limits(limits=1),
            np.errstate(over="raise", invalid="raise", divide="raise"),
        ):
            interpolant = CubicHermiteSpline(xx, yy, dd, extrapolate=False)
            values = interpolant(qq)
            slopes = interpolant(qq, 1)
    except (FloatingPointError, OverflowError, ValueError) as error:
        raise ValueError("Cubic Hermite calculation failed or overflowed") from error
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(slopes)):
        raise ValueError("Cubic Hermite calculation produced nonfinite output")
    return {
        "query_x": qq.tolist(),
        "values": values.tolist(),
        "derivatives": slopes.tolist(),
        "knot_count": len(xx),
        "query_count": len(qq),
        "source_range": [float(xx[0]), float(xx[-1])],
        "method": "scipy.interpolate.CubicHermiteSpline, no extrapolation",
        "scope": "Numerical derivative-constrained interpolation only; no smoothing, peak search, convergence or scientific interpretation",
    }
