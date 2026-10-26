"""Bounded continuous linear programs with explicit bounds and KKT diagnostics."""

import math
import warnings


def solve_linear_program(
    objective: list,
    bounds: list,
    inequality_matrix: list | None = None,
    inequality_rhs: list | None = None,
    equality_matrix: list | None = None,
    equality_rhs: list | None = None,
    direction: str = "min",
) -> dict:
    """Optimize a caller-defined continuous linear model, retaining axis order.

    objective has1..500 finite real coefficients. bounds explicitly provides
    one[lower,upper]pair per variable; null endpoints mean unbounded, never zero.
    inequality_matrix*x<=inequality_rhs and equality_matrix*x=equality_rhs.
    Each matrix/RHS pair is jointly null or jointly specified;[],[]means no rows.
    At most2000 constraint rows and100000 coefficients across both matrices.
    All numeric cells exclude boolean/string/null/nonfinite values. Zero rows,
    redundant equalities and fixed variables are allowed. No implicit variable
    nonnegativity, intercept, normalization, alignment or model repair is added.
    Internally divide a nonzero objective by its largest coefficient magnitude;
    divide each constraint row and RHS by that row's largest coefficient magnitude
    (or abs(RHS),or1 for zero rows). Reverse these positive scales in marginals.
    Nonzero normalized objective/row coefficients must be at least1e-8 in
    magnitude; nonzero normalized RHS must have magnitude1e-8..1e12, and finite
    bound endpoints have abs<=1e12. Unsupported dynamic ranges fail explicitly
    with a variable-rescaling hint rather than letting HiGHS drop coefficients.

    direction is min or max. Returns status, finite optimal solution/objective
    and numerical KKT diagnostics when validated; nonoptimal statuses have null
    solution, objective and diagnostics. Infeasible/unbounded are solver model
    outcomes, not numeric observations. HiGHS dual simplex uses one thread,
    presolve disabled, max10000 iterations and30solver seconds. Floating checks
    use1e-7 scaled tolerance; these are not exact rational certificates.

    Marginals refer to the REQUESTED objective, including max. They are partial
    derivatives with respect to RHS/bound endpoints. For min, inequality and
    upper marginals are nonpositive and lower marginals nonnegative; max reverses
    those signs. Stationarity is c-A_ub^T*y_ub-A_eq^T*y_eq-y_lower-y_upper=0.
    Unbounded endpoint slacks are null; their marginals must be numerically zero.
    Degenerate optima can have several valid primal/dual witnesses. No integer
    variables, strict inequalities, nonlinear goals, scientific assumptions,
    sampling uncertainty, sharp-identification or causal validity is inferred.
    """

    def number(value, label):
        if type(value) not in (int, float):
            raise ValueError(label + " must be a finite real JSON number")
        try:
            result = float(value)
        except (OverflowError, ValueError) as error:
            raise ValueError(label + " exceeds float64 range") from error
        if not math.isfinite(result):
            raise ValueError(label + " must be finite")
        return result

    if direction not in ("min", "max") or not isinstance(direction, str):
        raise ValueError("direction must be min or max")
    if not isinstance(objective, list) or not 1 <= len(objective) <= 500:
        raise ValueError("objective must contain1..500 real coefficients")
    c = [number(v, "objective[" + str(i) + "]") for i, v in enumerate(objective)]
    n = len(c)
    if not isinstance(bounds, list) or len(bounds) != n:
        raise ValueError("bounds needs one explicit[lower,upper]pair per variable")
    limits = []
    for i, pair in enumerate(bounds):
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Each bounds entry must be[lower,upper]")
        lower, upper = [
            None if v is None else number(v, "bounds[" + str(i) + "]") for v in pair
        ]
        if lower is not None and upper is not None and lower > upper:
            raise ValueError("Lower bound exceeds upper bound at variable " + str(i))
        if any(v is not None and abs(v) > 1e12 for v in (lower, upper)):
            raise ValueError(
                "Finite bounds require abs(endpoint)<=1e12; rescale variables"
            )
        limits.append((lower, upper))

    def constraints(matrix, rhs, label):
        if matrix is None and rhs is None:
            return [], []
        if (
            not isinstance(matrix, list)
            or not isinstance(rhs, list)
            or len(matrix) != len(rhs)
            or len(matrix) > 2000
        ):
            raise ValueError(
                label + " matrix and RHS must be paired aligned lists or both null"
            )
        if any(not isinstance(row, list) or len(row) != n for row in matrix):
            raise ValueError(label + " rows must match the complete objective width")
        return (
            [[number(v, label + " matrix cell") for v in row] for row in matrix],
            [number(v, label + " RHS cell") for v in rhs],
        )

    au, bu = constraints(inequality_matrix, inequality_rhs, "inequality")
    ae, be = constraints(equality_matrix, equality_rhs, "equality")
    if len(au) + len(ae) > 2000 or (len(au) + len(ae)) * n > 100000:
        raise ValueError(
            "Combined constraint rows<=2000 and coefficients<=100000 required"
        )

    objective_scale = max(map(abs, c)) or 1.0
    scaled_c = [v / objective_scale for v in c]
    if any(original != 0 and abs(v) < 1e-8 for original, v in zip(c, scaled_c)):
        raise ValueError(
            "Nonzero normalized objective coefficients require abs>=1e-8; rescale variables or objective terms"
        )

    def scaled_rows(matrix, rhs):
        rows, values, scales = [], [], []
        for row, value in zip(matrix, rhs):
            scale = max(map(abs, row)) or abs(value) or 1.0
            normalized = [v / scale for v in row]
            target = value / scale
            if any(
                original != 0 and abs(v) < 1e-8 for original, v in zip(row, normalized)
            ):
                raise ValueError(
                    "Nonzero normalized constraint coefficients require abs>=1e-8; rescale variables"
                )
            if not math.isfinite(target) or (
                value != 0 and not 1e-8 <= abs(target) <= 1e12
            ):
                raise ValueError(
                    "Nonzero normalized constraint RHS requires abs in1e-8..1e12; rescale variables/RHS"
                )
            rows.append(normalized)
            values.append(target)
            scales.append(scale)
        return rows, values, scales

    scaled_au, scaled_bu, scales_u = scaled_rows(au, bu)
    scaled_ae, scaled_be, scales_e = scaled_rows(ae, be)

    import numpy as np
    import scipy
    from scipy.optimize import OptimizeWarning, linprog
    from threadpoolctl import threadpool_limits

    sign = 1 if direction == "min" else -1
    with warnings.catch_warnings(), threadpool_limits(limits=1):
        # SciPy deliberately forwards unknown options to HiGHS. Its threads
        # option is needed in addition to BLAS thread limits.
        warnings.filterwarnings(
            "ignore",
            category=OptimizeWarning,
            message=r"Unrecognized options detected:.*threads.*",
        )
        result = linprog(
            np.asarray(scaled_c) * sign,
            A_ub=scaled_au or None,
            b_ub=scaled_bu or None,
            A_eq=scaled_ae or None,
            b_eq=scaled_be or None,
            bounds=limits,
            method="highs-ds",
            options=dict(
                presolve=False,
                threads=1,
                maxiter=10000,
                time_limit=30.0,
                primal_feasibility_tolerance=1e-9,
                dual_feasibility_tolerance=1e-9,
            ),
        )
    status = {0: "optimal", 1: "limit", 2: "infeasible", 3: "unbounded"}.get(
        int(result.status), "solver_failure"
    )
    answer = dict(
        status=status,
        solution=None,
        objective_value=None,
        diagnostics=None,
        validation_error=None,
        direction=direction,
        variable_count=n,
        inequality_count=len(au),
        equality_count=len(ae),
        solver_status_code=int(result.status),
        solver_message=str(result.message),
        solver_iterations=int(result.nit or 0),
        scipy_version=scipy.__version__,
        objective_scale=objective_scale,
        inequality_row_scales=scales_u,
        equality_row_scales=scales_e,
        numerical_protocol="Positive objective and constraint-row scaling, reversed in requested-direction marginals; unsupported normalized dynamic ranges rejected explicitly. SciPy HiGHS dual simplex; presolve disabled; one HiGHS/BLAS thread;10000iteration/30second solver limits;1e-9 solver feasibility tolerances. Optimal witnesses additionally require finite primal/dual fields and1e-7 scaled primal, stationarity, sign, complementary-slackness and dual-gap checks. This is floating numerical verification, not an exact certificate.",
        scope="Caller defines scientific variables, axes, units, objective, feasible set and interpretation. Continuous variables only. No implicit nonnegativity, normalization, model repair, sampling uncertainty, causal or sharp-identification claim. Degenerate optimal witnesses need not be unique; nonoptimal outcomes supply no numeric optimum.",
    )
    if status != "optimal":
        return answer
    x = np.asarray(result.x, dtype=float)
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        yu = (
            np.asarray(result.ineqlin.marginals, dtype=float)
            * sign
            * objective_scale
            / np.asarray(scales_u)
        )
        ye = (
            np.asarray(result.eqlin.marginals, dtype=float)
            * sign
            * objective_scale
            / np.asarray(scales_e)
        )
        yl = np.asarray(result.lower.marginals, dtype=float) * sign * objective_scale
        yh = np.asarray(result.upper.marginals, dtype=float) * sign * objective_scale
    arrays = (x, yu, ye, yl, yh)
    if any(not np.all(np.isfinite(v)) for v in arrays):
        answer["status"] = "numerical_failure"
        answer["validation_error"] = (
            "Solver reported optimal but primal/dual witness fields are nonfinite; numeric optimum discarded"
        )
        return answer
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            u = np.asarray(au, dtype=float).reshape((-1, n))
            e = np.asarray(ae, dtype=float).reshape((-1, n))
            slack = np.asarray(bu) - u @ x
            residual = np.asarray(be) - e @ x
            requested = float(np.asarray(c) @ x)
            dual = float(np.asarray(bu) @ yu + np.asarray(be) @ ye)
            lower_slack, upper_slack = [], []
            primal = [0.0]
            complement = [0.0]
            for i, (lower, upper) in enumerate(limits):
                lower_slack.append(None if lower is None else float(x[i] - lower))
                upper_slack.append(None if upper is None else float(upper - x[i]))
                for endpoint, margin, gap, sense in (
                    (lower, yl[i], lower_slack[-1], 1),
                    (upper, yh[i], upper_slack[-1], -1),
                ):
                    if endpoint is None:
                        primal.append(abs(float(margin)))
                    else:
                        dual += endpoint * float(margin)
                        primal.append(max(0.0, -gap) / (1 + abs(endpoint) + abs(x[i])))
                        complement.append(abs(gap * margin) / (1 + abs(requested)))
            for row, rhs, gap in zip(au, bu, slack):
                primal.append(
                    max(0.0, -float(gap))
                    / (1 + abs(rhs) + float(np.abs(row) @ np.abs(x)))
                )
            for row, rhs, gap in zip(ae, be, residual):
                primal.append(
                    abs(float(gap)) / (1 + abs(rhs) + float(np.abs(row) @ np.abs(x)))
                )
            stationarity = np.asarray(c) - u.T @ yu - e.T @ ye - yl - yh
            stationarity_scale = (
                1
                + np.abs(c)
                + np.abs(u).T @ np.abs(yu)
                + np.abs(e).T @ np.abs(ye)
                + np.abs(yl)
                + np.abs(yh)
            )
            signs = [
                0.0,
                *np.maximum(yu * sign, 0).tolist(),
                *np.maximum(-yl * sign, 0).tolist(),
                *np.maximum(yh * sign, 0).tolist(),
            ]
            complement.extend((np.abs(slack * yu) / (1 + abs(requested))).tolist())
            # Bound residuals can be numpy scalars even when the value is
            # finite. The public contract requires ordinary JSON numbers.
            check_values = [float(value) for value in [
                max(primal),
                float(np.max(np.abs(stationarity) / stationarity_scale)),
                max(signs),
                max(complement),
                abs(requested - dual) / (1 + abs(requested) + abs(dual)),
            ]]
            diagnostics = dict(
                inequality_slack=slack.tolist(),
                equality_residual=residual.tolist(),
                lower_bound_slack=lower_slack,
                upper_bound_slack=upper_slack,
                inequality_marginals=yu.tolist(),
                equality_marginals=ye.tolist(),
                lower_bound_marginals=yl.tolist(),
                upper_bound_marginals=yh.tolist(),
                dual_objective=dual,
                scaled_primal_violation=check_values[0],
                scaled_stationarity_violation=check_values[1],
                dual_sign_violation=check_values[2],
                scaled_complementarity_violation=check_values[3],
                scaled_duality_gap=check_values[4],
                validation_tolerance=1e-7,
            )
            finite = [
                requested,
                dual,
                *check_values,
                *slack.tolist(),
                *residual.tolist(),
                *[v for v in lower_slack + upper_slack if v is not None],
            ]
            if not all(math.isfinite(v) for v in finite) or max(check_values) > 1e-7:
                answer["status"] = "numerical_failure"
                answer["validation_error"] = (
                    "Solver reported optimal but finite-value or scaled KKT verification failed; numeric optimum discarded"
                )
                return answer
    except (FloatingPointError, OverflowError, ValueError):
        answer["status"] = "numerical_failure"
        answer["validation_error"] = (
            "Numerical witness verification exceeded finite float64 range; numeric optimum discarded"
        )
        return answer
    answer.update(
        solution=x.tolist(), objective_value=requested, diagnostics=diagnostics
    )
    return answer
