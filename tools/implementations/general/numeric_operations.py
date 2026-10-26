"""Finite, ordered elementwise numerical operations without generated code."""

import math


def elementwise_numeric_operations(
    operation: str,
    values: list,
    other: list | float | None = None,
) -> dict:
    """Apply one declared arithmetic operation to a numeric vector or matrix.

    Args:
        operation: add/subtract/multiply/divide use values as the left operand.
            sqrt/log/exp/reciprocal/abs are unary. log is the natural logarithm.
        values: A nonempty 1D vector or nonempty rectangular 2D matrix, with at
            most 10000 total finite real entries in scientific row/column order.
            Ragged, mixed vector/matrix, empty rows and deeper nesting fail.
            Booleans/null/strings are rejected. Arithmetic is ordinary float64,
            not arbitrary-precision integer or symbolic arithmetic.
        other: For binary operations, either one finite numeric scalar broadcast
            to every row, or a finite vector of EXACTLY the same length. A
            one-element list is not broadcast. For a 2D matrix, other may be
            a scalar or an exactly matching rectangular 2D matrix; 1D vectors,
            single-row/column broadcasting and all implicit axis expansion fail. Unary operations require null.

    Returns:
        dict with operation, values (same ordered shape, all finite floats),
        length (outer length), shape, element_count, operand_mode
        (unary/scalar_broadcast/aligned_vector/aligned_matrix), and scope.
        No file, network, code generation, expression evaluation, model fitting
        or unit inference occurs. Callers must establish compatible quantities,
        record alignment and meaningful transformations from scientific context.

    Raises:
        ValueError: Invalid length/type/operation, zero division, negative square
            root, nonpositive logarithm, overflow/nonfinite result, or a nonzero
            multiply/divide/exp result that underflows to zero. Failing element
            indices are zero-based row-major indices.
            Entire calls fail; invalid rows are not dropped, clipped or imputed.
    """
    binary = {"add", "subtract", "multiply", "divide"}
    unary = {"sqrt", "log", "exp", "reciprocal", "abs"}
    if not isinstance(operation, str) or operation not in binary | unary:
        raise ValueError(
            "operation must be add/subtract/multiply/divide/sqrt/log/exp/reciprocal/abs"
        )

    def finite(value, label):
        if type(value) not in (int, float):
            raise ValueError(
                label + " must be a finite real number, excluding booleans"
            )
        try:
            result = float(value)
        except (OverflowError, ValueError) as error:
            raise ValueError(label + " cannot be represented in float64") from error
        if not math.isfinite(result):
            raise ValueError(label + " must be finite")
        return result

    if not isinstance(values, list) or not 1 <= len(values) <= 10000:
        raise ValueError("values must be a numeric list of length 1..10000")
    is_matrix = any(isinstance(row, list) for row in values)
    if is_matrix:
        if (
            not all(isinstance(row, list) and row for row in values)
            or any(len(row) != len(values[0]) for row in values)
            or len(values) * len(values[0]) > 10000
        ):
            raise ValueError(
                "Matrix must be nonempty rectangular 2D with <=10000 entries; no mixed shapes"
            )
        shape = [len(values), len(values[0])]
        flattened = [value for row in values for value in row]
    else:
        shape = [len(values)]
        flattened = values
    left = [
        finite(value, "values flat index " + str(i))
        for i, value in enumerate(flattened)
    ]
    if operation in unary:
        if other is not None:
            raise ValueError("Unary operations require other=null or omitted")
        right = [None] * len(left)
        mode = "unary"
    elif isinstance(other, list):
        if is_matrix:
            if len(other) != shape[0] or not all(
                isinstance(row, list) and len(row) == shape[1] for row in other
            ):
                raise ValueError(
                    "Matrix other must have exactly the same 2D shape; no axis broadcasting"
                )
            right = [
                finite(value, "other flat index " + str(i))
                for i, value in enumerate(value for row in other for value in row)
            ]
            mode = "aligned_matrix"
        elif len(other) != len(left):
            raise ValueError(
                "Vector other must have exactly the same length; no list broadcasting"
            )
        else:
            right = [
                finite(value, "other[" + str(i) + "]") for i, value in enumerate(other)
            ]
            mode = "aligned_vector"
    else:
        right = [finite(other, "other")] * len(left)
        mode = "scalar_broadcast"
    result = []
    for i, (a, b) in enumerate(zip(left, right)):
        if (
            operation in {"divide", "reciprocal"}
            and (b if operation == "divide" else a) == 0
        ):
            raise ValueError("Division by zero at row " + str(i))
        if operation == "sqrt" and a < 0:
            raise ValueError("Square root requires nonnegative input at row " + str(i))
        if operation == "log" and a <= 0:
            raise ValueError(
                "Natural logarithm requires positive input at row " + str(i)
            )
        try:
            if operation == "add":
                value = a + b
            elif operation == "subtract":
                value = a - b
            elif operation == "multiply":
                value = a * b
            elif operation == "divide":
                value = a / b
            elif operation == "sqrt":
                value = math.sqrt(a)
            elif operation == "log":
                value = math.log(a)
            elif operation == "exp":
                value = math.exp(a)
            elif operation == "reciprocal":
                value = 1.0 / a
            else:
                value = abs(a)
        except (OverflowError, ValueError) as error:
            raise ValueError("Unrepresentable result at row " + str(i)) from error
        if not math.isfinite(value):
            raise ValueError("Nonfinite result at row " + str(i))
        if (operation == "exp" and value == 0) or (
            operation in {"multiply", "divide"} and a != 0 and b != 0 and value == 0
        ):
            raise ValueError(
                "Result underflows float64 to zero at row "
                + str(i)
                + "; rescale the calculation"
            )
        result.append(value)
    shaped_result = (
        [result[start : start + shape[1]] for start in range(0, len(result), shape[1])]
        if is_matrix
        else result
    )
    return {
        "operation": operation,
        "values": shaped_result,
        "length": shape[0],
        "shape": shape,
        "element_count": len(result),
        "operand_mode": mode,
        "scope": "Ordered float64 arithmetic only; no unit inference, row alignment repair, clipping or imputation",
    }
