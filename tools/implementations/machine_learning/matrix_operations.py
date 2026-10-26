"""Bounded dense matrix composition for scientific tool outputs."""

import math

import numpy as np
from threadpoolctl import threadpool_limits


def matrix_multiply(left: list, right: list) -> dict:
    """Multiply a matrix by an aligned matrix or column vector, without broadcasting.

    Args:
        left: Nonempty rectangular numeric matrix with at most 10000 entries.
        right: Numeric vector of length equal to left's column count, or a
            rectangular matrix whose row count equals that column count.
            Each operand has at most 10000 entries. Bool/null/strings,
            mixed dimensions, empty rows, ragged rows and nonfinite values fail.

    Returns:
        dict with product, left_shape, right_shape, product_shape and operation.
        A vector right operand returns a vector product; a matrix returns a
        matrix. Both use ordinary float64 and preserve supplied axis order.
        Result size is at most 10000 entries and at most 10 million scalar
        multiply-add terms are allowed. One numerical thread; no unit inference,
        transposition, broadcasting, identity matching or fitting is performed.

    Raises:
        ValueError: Invalid shape/type/alignment, excessive size/work, or
            nonfinite input/output. Inputs must represent compatible units and
            scientifically matched axes; this tool cannot establish those facts.
    """

    def scalar(value):
        if type(value) not in (int, float):
            raise ValueError("Matrix entries must be real numbers, excluding bool/null")
        try:
            number = float(value)
        except (OverflowError, ValueError) as error:
            raise ValueError("Matrix entry exceeds float64 range") from error
        if not math.isfinite(number):
            raise ValueError("Matrix entries must be finite")
        return number

    def matrix(value, label):
        if (
            not isinstance(value, list)
            or not value
            or not isinstance(value[0], list)
            or not value[0]
        ):
            raise ValueError(label + " must be a nonempty rectangular matrix")
        width = len(value[0])
        if len(value) * width > 10000 or any(
            not isinstance(row, list) or len(row) != width for row in value
        ):
            raise ValueError(label + " must be rectangular with at most 10000 entries")
        return np.asarray([[scalar(v) for v in row] for row in value], dtype=float)

    a = matrix(left, "left")
    if not isinstance(right, list) or not right:
        raise ValueError("right must be a nonempty matrix or vector")
    if isinstance(right[0], list):
        b = matrix(right, "right")
        columns = b.shape[1]
        operation = "matrix_matrix"
    else:
        if len(right) > 10000:
            raise ValueError("right must have at most 10000 entries")
        b = np.asarray([scalar(v) for v in right], dtype=float)
        columns = 1
        operation = "matrix_vector"
    if a.shape[1] != b.shape[0]:
        raise ValueError("left columns must equal right rows/vector length")
    if a.shape[0] * columns > 10000 or a.shape[0] * a.shape[1] * columns > 10000000:
        raise ValueError("Product exceeds the declared output/work bound")
    try:
        with threadpool_limits(limits=1), np.errstate(over="raise", invalid="raise"):
            product = a @ b
    except FloatingPointError as error:
        raise ValueError(
            "Matrix product is outside finite float64 range; rescale inputs"
        ) from error
    if not np.all(np.isfinite(product)):
        raise ValueError("Matrix product must be finite; rescale inputs")
    return {
        "product": product.tolist(),
        "left_shape": list(a.shape),
        "right_shape": list(b.shape),
        "product_shape": list(product.shape),
        "operation": operation,
    }
