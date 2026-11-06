"""Small deterministic certificates for reviewing real numerical observations."""
import math


def numerical_certificate(tool, arguments, output):
    """Check equations, not task intent; a passing check is never auto-approval."""
    if tool != "SymmetricEigenDecomposition":
        return None
    try:
        import numpy as np
    except ImportError:
        return _eigensystem_without_numpy(arguments, output)

    try:
        source = np.asarray(arguments["values"], dtype=float)
        values = np.asarray(output["eigenvalues"], dtype=float)
        vectors = np.asarray(output["eigenvectors"], dtype=float)
        n = len(values)
        if source.shape != (n, n) or vectors.shape != (n, n) or n == 0:
            return {"kind": "symmetric_eigensystem", "passed": False,
                    "reason": "Inconsistent matrix/eigensystem dimensions"}
        if not all(np.isfinite(a).all() for a in [source, values, vectors]):
            return {"kind": "symmetric_eigensystem", "passed": False,
                    "reason": "Nonfinite eigensystem"}
        # The public tool contract defines the source through its lower triangle.
        matrix = np.tril(source) + np.tril(source, -1).T
        residual = float(np.max(np.abs(matrix @ vectors - vectors * values)))
        orthogonality = float(np.max(np.abs(vectors.T @ vectors - np.eye(n))))
        tolerance = 1e-10 * max(1.0, float(np.max(np.abs(matrix)))) * n
        return {"kind": "symmetric_eigensystem", "eigenvectors": "columns",
                "max_abs_equation_residual": residual,
                "equation_tolerance": tolerance,
                "max_abs_orthogonality_residual": orthogonality,
                "orthogonality_tolerance": 1e-10 * n,
                "passed": bool(residual <= tolerance
                               and orthogonality <= 1e-10 * n
                               and np.all(np.diff(values) >= -tolerance))}
    except (ValueError, KeyError, TypeError, OverflowError):
        return {"kind": "symmetric_eigensystem", "passed": False,
                "reason": "Cannot read a finite eigensystem from the observation"}


def _eigensystem_without_numpy(arguments, output):
    """Keep the core harness install usable without scientific worker packages."""
    try:
        values, vectors = output["eigenvalues"], output["eigenvectors"]
        source, n = arguments["values"], len(values)
        if not 1 <= n <= 200 or len(source) != n or len(vectors) != n:
            raise ValueError("Invalid dimensions")
        if any(len(row) != n for row in [*source, *vectors]):
            raise ValueError("Invalid dimensions")
        if not all(type(v) in (int, float) and math.isfinite(v)
                   for v in [*values, *(v for row in [*source, *vectors] for v in row)]):
            raise ValueError("Nonfinite eigensystem")
        matrix = [[source[max(i, j)][min(i, j)] for j in range(n)] for i in range(n)]
        residual = max(abs(math.fsum(matrix[i][k] * vectors[k][j] for k in range(n))
                           - vectors[i][j] * values[j]) for i in range(n) for j in range(n))
        orthogonality = max(abs(math.fsum(vectors[k][i] * vectors[k][j] for k in range(n))
                                - int(i == j)) for i in range(n) for j in range(n))
        tolerance = 1e-10 * max(1.0, max(abs(v) for row in matrix for v in row)) * n
        return {"kind": "symmetric_eigensystem", "eigenvectors": "columns",
                "max_abs_equation_residual": residual, "equation_tolerance": tolerance,
                "max_abs_orthogonality_residual": orthogonality,
                "orthogonality_tolerance": 1e-10 * n,
                "passed": residual <= tolerance and orthogonality <= 1e-10 * n
                          and all(b - a >= -tolerance for a, b in zip(values, values[1:]))}
    except (ValueError, KeyError, TypeError, OverflowError):
        return {"kind": "symmetric_eigensystem", "passed": False,
                "reason": "Cannot read a finite eigensystem from the observation"}
