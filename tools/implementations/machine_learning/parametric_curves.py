"""Small public parametric curve families fitted by bounded local SciPy least squares.

No model selection, scientific acceptance decision, arbitrary formula evaluation,
code execution, network access or experimental action is performed.
"""

import math
import numpy as np
from scipy.optimize import least_squares
from scipy.special import expit
from threadpoolctl import threadpool_limits

REGISTRY = {
    "exponential_approach": {
        "parameters": ["asymptote", "rate"],
        "formula": "a*(1-exp(-b*x))",
        "x_domain": "x>=0",
        "lower": [0, 0],
        "upper": [None, None],
    },
    "power_law": {
        "parameters": ["scale", "exponent"],
        "formula": "a*x**b",
        "x_domain": "x>0",
        "lower": [0, None],
        "upper": [None, None],
    },
    "logistic": {
        "parameters": ["asymptote", "rate", "midpoint"],
        "formula": "a/(1+exp(-b*(x-c)))",
        "x_domain": "all finite x",
        "lower": [0, 0, None],
        "upper": [None, None, None],
    },
    "gaussian_peak": {
        "parameters": ["height", "center", "width"],
        "formula": "a*exp(-0.5*((x-b)/c)**2)",
        "x_domain": "all finite x; width>0",
        "lower": [0, None, 1e-12],
        "upper": [None, None, None],
    },
    "attenuation_ratio": {
        "parameters": ["decay_rate", "denominator_intercept", "denominator_slope"],
        "formula": "exp(-a*x)/(b+c*x)",
        "x_domain": "x>=0; denominator>0",
        "lower": [0, 1e-12, 0],
        "upper": [None, None, None],
    },
}


def _vector(value, name, minimum=1, maximum=1000):
    if (
        not isinstance(value, list)
        or not minimum <= len(value) <= maximum
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)
    ):
        raise ValueError(
            name
            + " must be a bounded nonempty finite numeric vector, excluding bool/null"
        )
    return np.asarray(value, dtype=float)


def _family(model_type):
    if not isinstance(model_type, str) or model_type not in REGISTRY:
        raise ValueError("Unknown fixed public curve family")
    return REGISTRY[model_type]


def _evaluate(model_type, x, p):
    family = _family(model_type)
    if model_type in {"exponential_approach", "attenuation_ratio"} and np.any(x < 0):
        raise ValueError("This family requires x>=0")
    if model_type == "power_law" and np.any(x <= 0):
        raise ValueError("power_law requires strictly positive x")
    for v, lo, hi in zip(p, family["lower"], family["upper"]):
        if lo is not None and v < lo or hi is not None and v > hi:
            raise ValueError("Model parameter violates the public family domain")
    with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
        try:
            if model_type == "exponential_approach":
                v = -p[0] * np.expm1(-p[1] * x)
            elif model_type == "power_law":
                v = p[0] * np.power(x, p[1])
            elif model_type == "logistic":
                v = p[0] * expit(p[1] * (x - p[2]))
            elif model_type == "gaussian_peak":
                v = p[0] * np.exp(-0.5 * ((x - p[1]) / p[2]) ** 2)
            else:
                v = np.exp(-p[0] * x) / (p[1] + p[2] * x)
        except FloatingPointError as exc:
            raise ValueError(
                "Curve evaluation exceeds its finite numeric domain"
            ) from exc
    if not np.all(np.isfinite(v)):
        raise ValueError("Curve evaluation is nonfinite")
    return v


def fit_parametric_curve(
    x: list,
    y: list,
    model_type: str,
    initial_parameters: list,
    lower_bounds: list | None = None,
    upper_bounds: list | None = None,
    sigma: list | None = None,
    absolute_sigma: bool = False,
    loss: str = "linear",
    max_evaluations: int = 2000,
) -> dict:
    """Fit one declared fixed curve family using bounded local least squares.

    Families/formula/parameter order are public REGISTRY. There are2 or3 fitted
    parameters, at most1000 observations, and observations must exceed parameter
    count. Duplicate x observations are allowed; at least2 distinct x are needed.
    Optional sigma are positive observation standard deviations, not weights;
    residuals are divided by sigma. No weights are estimated. Absolute_sigma
    affects approximate covariance scaling only. Bounds may narrow but never
    widen family domains; per-entry null means the family's default bound.
    Linear, soft_l1 or huber loss uses fixed f_scale1 in sigma-scaled units.
    Return local optimizer diagnostics even when not converged; success only
    means numeric termination, never global optimum or scientific applicability.
    Approximate local covariance is supplied only for converged, full-column-rank,
    interior linear-loss fits with residual df>0. It assumes independent errors,
    a locally adequate model and supplied sigma conventions. Active bounds,
    robust losses, nonconvergence or deficient rank return null covariance/SE.
    No confidence interval, extrapolation validity or model-selection claim.
    """
    fam = _family(model_type)
    xx = _vector(x, "x")
    yy = _vector(y, "y")
    p0 = _vector(initial_parameters, "initial_parameters", maximum=3)
    k = len(fam["parameters"])
    n = len(xx)
    if len(yy) != n or len(p0) != k or n <= k or len(np.unique(xx)) < 2:
        raise ValueError(
            "Aligned observations must exceed exact parameter count and include2 distinct x"
        )
    if (
        type(absolute_sigma) is not bool
        or loss not in {"linear", "soft_l1", "huber"}
        or type(max_evaluations) is not int
        or not 10 <= max_evaluations <= 10000
    ):
        raise ValueError("Invalid sigma convention,loss or bounded evaluation budget")
    if absolute_sigma and sigma is None:
        raise ValueError("absolute_sigma requires explicit positive observation sigma")
    sd = np.ones(n) if sigma is None else _vector(sigma, "sigma")
    if len(sd) != n or np.any(sd <= 0):
        raise ValueError("sigma must be aligned and strictly positive")
    bounds = []
    for side, provided in [("lower", lower_bounds), ("upper", upper_bounds)]:
        if provided is not None and (
            not isinstance(provided, list) or len(provided) != k
        ):
            raise ValueError("Bound vector must have exact parameter count")
        values = []
        for i, domain in enumerate(fam[side]):
            v = None if provided is None else provided[i]
            if v is not None and (type(v) not in (int, float) or not math.isfinite(v)):
                raise ValueError("Bounds must contain finite numbers or null")
            if v is None:
                v = domain
            if domain is not None and (v < domain if side == "lower" else v > domain):
                raise ValueError("Bounds cannot widen public family domains")
            values.append(
                (-np.inf if side == "lower" else np.inf) if v is None else float(v)
            )
        bounds.append(np.asarray(values))
    lo, hi = bounds
    if np.any(lo >= hi) or np.any(p0 < lo) or np.any(p0 > hi):
        raise ValueError("Bounds must be ordered and initial parameters feasible")
    _evaluate(model_type, xx, p0)

    def residual(p):
        return (_evaluate(model_type, xx, p) - yy) / sd

    with threadpool_limits(limits=1):
        fit = least_squares(
            residual,
            p0,
            bounds=(lo, hi),
            method="trf",
            jac="3-point",
            x_scale="jac",
            loss=loss,
            f_scale=1.0,
            max_nfev=max_evaluations,
            ftol=1e-12,
            xtol=1e-12,
            gtol=1e-12,
        )
        predictions = _evaluate(model_type, xx, fit.x)
        raw = predictions - yy
        weighted = raw / sd
        singular = np.linalg.svd(fit.jac, compute_uv=False)
        tol = (
            np.finfo(float).eps
            * max(fit.jac.shape)
            * (singular[0] if len(singular) else 0)
        )
        rank = int(np.count_nonzero(singular > tol))
        condition = float(singular[0] / singular[-1]) if rank == k else None
        cov = None
        se = None
        status = "available_local_approximation"
        if not fit.success:
            status = "optimizer_not_converged"
        elif loss != "linear":
            status = "robust_loss_not_supported"
        elif rank < k:
            status = "jacobian_rank_deficient"
        elif np.any(fit.active_mask):
            status = "active_parameter_bounds"
        else:
            _, sv, vt = np.linalg.svd(fit.jac, full_matrices=False)
            cov = (vt.T / (sv**2)) @ vt
            if not absolute_sigma:
                cov *= float(weighted @ weighted) / (n - k)
            if np.all(np.isfinite(cov)) and np.all(np.diag(cov) >= 0):
                se = np.sqrt(np.diag(cov)).tolist()
                cov = cov.tolist()
            else:
                cov = None
                status = "nonfinite_local_covariance"
    output = {
        "model": {
            "model_type": model_type,
            "parameter_names": fam["parameters"],
            "parameters": fit.x.tolist(),
            "formula": fam["formula"],
            "training_x_range": [float(xx.min()), float(xx.max())],
        },
        "sample_count": n,
        "parameter_count": k,
        "residual_degrees_of_freedom": n - k,
        "predictions": predictions.tolist(),
        "residuals": raw.tolist(),
        "residual_convention": "prediction minus observed response,original y units",
        "residual_sum_squares": float(raw @ raw),
        "scaled_residual_sum_squares": float(weighted @ weighted),
        "rmse": float(np.sqrt(np.mean(raw**2))),
        "optimizer": {
            "converged": bool(fit.success),
            "status": int(fit.status),
            "message": str(fit.message),
            "function_evaluations": int(fit.nfev),
            "optimality": float(fit.optimality),
            "active_bounds": fit.active_mask.astype(int).tolist(),
            "loss": loss,
        },
        "jacobian_rank": rank,
        "jacobian_singular_values": singular.tolist(),
        "jacobian_condition_number": condition,
        "parameter_covariance": cov,
        "parameter_standard_errors": se,
        "covariance_status": status,
        "sigma_mode": (
            "unit_relative"
            if sigma is None
            else "absolute" if absolute_sigma else "relative"
        ),
        "scope": "Bounded local numerical fit only; no global-optimum,mechanism,causal,confidence-coverage or extrapolation guarantee.",
    }
    import json

    try:
        json.dumps(output, allow_nan=False)
    except ValueError as exc:
        raise ValueError(
            "Fitted diagnostics exceed finite representable range"
        ) from exc
    return output


def evaluate_parametric_curve(model: dict, x: list) -> dict:
    """Evaluate one public fixed-family model without fitting or extrapolation claims.

    Accept the model object returned by FitParametricCurve, or an explicit object
    containing model_type and exact ordered finite parameters. Training range is
    optional metadata; when present its finite ordered endpoints classify each
    query as inside/outside observed support, not whether extrapolation is valid.
    At most1000 finite query x; no uncertainty propagation or scientific decision.
    """
    if not isinstance(model, dict):
        raise ValueError("model must be a public fixed-family object")
    kind = model.get("model_type")
    fam = _family(kind)
    p = _vector(model.get("parameters"), "parameters", maximum=3)
    if len(p) != len(fam["parameters"]):
        raise ValueError("Exact parameter count required")
    xx = _vector(x, "x")
    v = _evaluate(kind, xx, p)
    support = model.get("training_x_range")
    outside = None
    if support is not None:
        interval = _vector(support, "training_x_range", minimum=2, maximum=2)
        if interval[0] > interval[1]:
            raise ValueError("training_x_range must be ordered")
        outside = ((xx < interval[0]) | (xx > interval[1])).tolist()
    return {
        "model_type": kind,
        "parameter_names": fam["parameters"],
        "parameters": p.tolist(),
        "x": xx.tolist(),
        "predictions": v.tolist(),
        "outside_training_range": outside,
        "scope": "Deterministic declared model evaluation; an inside-range flag does not establish model adequacy,and outside-range predictions are unsupported extrapolations unless independently justified.",
    }
