"""Bounded real matrix exponential as a composable numerical primitive."""
import math
import numpy as np
from scipy.linalg import expm
from threadpoolctl import threadpool_limits


def matrix_exponential(values: list) -> dict:
    """Compute exp(A) of a real square matrix, not elementwise exponentials.

    Args:
        values: Nonempty square 2D list, dimension1..32, finite real entries.
            Booleans, strings, complex numbers, ragged shapes and NaN/Inf fail.
            Infinity norm (maximum absolute row sum) must be<=700. The caller
            must supply a dimensionless matrix, e.g. a rate generator times an
            elapsed time; this tool neither infers units nor checks any kinetic
            or stochastic interpretation. No clipping or renormalization occurs.

    Returns:
        dict with exponential (real finite matrix exp(A), same shape), shape,
        dimension, input_infinity_norm, method and scope. This is the full
        matrix exponential computed by SciPy's scaling/squaring Pade method;
        it is not exp applied separately to entries. Matrix products and
        physical boundary/initial conditions are separate caller choices.

    Raises:
        ValueError: Invalid input or bounded norm violation; overflow or any
            nonfinite numerical result fails the complete call. Results can
            contain negative entries for a general real input matrix.
    """
    if (not isinstance(values, list) or not 1 <= len(values) <= 32
        or any(not isinstance(row, list) or len(row) != len(values) for row in values)):
        raise ValueError('values must be a square 2D numeric list of dimension1..32')
    checked=[]
    for row in values:
        converted=[]
        for value in row:
            if type(value) not in (int, float):
                raise ValueError('Matrix entries must be finite real numbers, excluding booleans')
            try:
                number=float(value)
            except (OverflowError, ValueError) as error:
                raise ValueError('Matrix entry cannot be represented as finite float64') from error
            if not math.isfinite(number):
                raise ValueError('Matrix entries must be finite real numbers')
            converted.append(number)
        checked.append(converted)
    try:
        row_sums=[math.fsum(abs(v) for v in row) for row in checked]
    except OverflowError as error:
        raise ValueError('Matrix absolute row sum overflowed') from error
    norm=max(row_sums)
    if not math.isfinite(norm) or norm > 700:
        raise ValueError('Maximum absolute row sum must be<=700')
    a=np.asarray(checked,dtype=float)
    try:
        with threadpool_limits(limits=1), np.errstate(over='raise',invalid='raise'):
            result=expm(a)
    except (FloatingPointError, OverflowError, ValueError) as error:
        raise ValueError('Matrix exponential numerical calculation failed') from error
    if not np.all(np.isfinite(result)):
        raise ValueError('Matrix exponential produced nonfinite entries')
    return {'exponential':result.tolist(),'shape':[len(values),len(values)],
            'dimension':len(values),'input_infinity_norm':norm,
            'method':'scipy.linalg.expm scaling/squaring Pade matrix exponential',
            'scope':'Dimensionless supplied real matrix only; no unit, generator, state, positivity or conservation inference'}
