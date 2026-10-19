"""Small numerical tools using the installed NumPy/SciPy/scikit-learn stack.

All returned model artifacts are explicit JSON parameters, never pickle files.
Preprocessing fits training data only. No network or domain-specific experiments.
"""

import math
import warnings

import numpy as np
from scipy import stats
from scipy.special import expit, softmax
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.exceptions import ConvergenceWarning
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, MinMaxScaler, PolynomialFeatures

from tools.implementations.shared.common import InputValidationError
from tools.implementations.shared.data_validation import (
    require,
    number,
    integer,
    vector,
    matrix,
    labels,
    result,
    MAX_CELLS,
)


def _paired(x, y, minimum=2):
    a, b = vector(x, "x", minimum), vector(y, "y", minimum)
    require(len(a) == len(b), "x and y must have equal lengths")
    return a, b


def _curve(x, y):
    a, b = _paired(x, y)
    require(np.all(np.diff(a) > 0), "x must be strictly increasing")
    return a, b


def _training(features, targets):
    x, y = matrix(features, minimum_rows=2), vector(targets, "targets", 2)
    require(len(x) == len(y), "Feature rows and targets must have equal lengths")
    return x, y


def _transform(training_features, features):
    train, data = matrix(training_features, "training_features", 2), matrix(features)
    require(
        train.shape[1] == data.shape[1], "Training and transform feature widths differ"
    )
    return train, data


def _linear_artifact(estimator, kind, x, y):
    return result(
        model={
            "type": kind,
            "n_features": x.shape[1],
            "coefficients": estimator.coef_,
            "intercept": estimator.intercept_,
        },
        training_mse=mean_squared_error(y, estimator.predict(x)),
        n_training_rows=len(x),
        metric_basis="Training fit only; not held-out performance",
    )


def describe_numeric_data(values: list) -> dict:
    """Summarize finite numeric values with count, mean, median, sample standard deviation, quartiles and range."""
    a = vector(values, minimum=2)
    return result(
        count=len(a),
        mean=np.mean(a),
        median=np.median(a),
        sample_std=np.std(a, ddof=1),
        minimum=np.min(a),
        maximum=np.max(a),
        q25=np.quantile(a, 0.25),
        q75=np.quantile(a, 0.75),
    )


def pearson_correlation(x: list, y: list) -> dict:
    """Calculate Pearson linear correlation and its two-sided p-value for paired nonconstant numeric vectors."""
    a, b = _paired(x, y)
    require(
        np.ptp(a) > 0 and np.ptp(b) > 0, "Correlation is undefined for constant vectors"
    )
    r, p = stats.pearsonr(a, b)
    return result(
        correlation=r,
        p_value=p,
        count=len(a),
        method="Pearson",
        alternative="two-sided",
    )


def spearman_correlation(x: list, y: list) -> dict:
    """Calculate Spearman rank correlation and its asymptotic two-sided p-value for paired nonconstant vectors."""
    a, b = _paired(x, y, 3)
    require(
        np.ptp(a) > 0 and np.ptp(b) > 0, "Correlation is undefined for constant vectors"
    )
    r, p = stats.spearmanr(a, b)
    return result(
        correlation=r, p_value=p, count=len(a), method="Spearman; asymptotic p-value"
    )


def welch_t_test(sample_a: list, sample_b: list) -> dict:
    """Compare independent numeric sample means with a two-sided Welch t-test, without assuming equal variances."""
    a, b = vector(sample_a, "sample_a", 2), vector(sample_b, "sample_b", 2)
    require(
        np.var(a, ddof=1) + np.var(b, ddof=1) > 0,
        "Both sample variances are zero; finite t-test undefined",
    )
    test = stats.ttest_ind(a, b, equal_var=False)
    return result(
        statistic=test.statistic,
        p_value=test.pvalue,
        degrees_of_freedom=test.df,
        mean_difference=np.mean(a) - np.mean(b),
        method="Welch t-test; two-sided",
    )


def paired_t_test(sample_a: list, sample_b: list) -> dict:
    """Compare paired numeric measurements using a two-sided paired t-test on nonconstant differences."""
    a, b = _paired(sample_a, sample_b)
    require(
        np.var(a - b, ddof=1) > 0,
        "Paired differences have zero variance; finite t-test undefined",
    )
    test = stats.ttest_rel(a, b)
    return result(
        statistic=test.statistic,
        p_value=test.pvalue,
        degrees_of_freedom=test.df,
        mean_difference=np.mean(a - b),
        method="Paired t-test; two-sided",
    )


def mann_whitney_u_test(sample_a: list, sample_b: list) -> dict:
    """Compare two independent numeric distributions with a two-sided Mann-Whitney U test and automatic tie-aware method selection."""
    a, b = vector(sample_a, "sample_a", 2), vector(sample_b, "sample_b", 2)
    test = stats.mannwhitneyu(a, b, alternative="two-sided", method="auto")
    return result(
        statistic=test.statistic,
        p_value=test.pvalue,
        method="Mann-Whitney U; scipy auto; two-sided",
    )


def one_way_anova(groups: list) -> dict:
    """Compare means of at least two independent numeric groups with classical one-way ANOVA, assuming equal variances."""
    require(isinstance(groups, list) and 2 <= len(groups) <= 20, "Require 2..20 groups")
    arrays = [vector(g, f"groups[{i}]", 2) for i, g in enumerate(groups)]
    require(sum(len(a) for a in arrays) <= 5000, "Too many observations")
    require(
        sum(np.var(a, ddof=1) for a in arrays) > 0,
        "Within-group variance is zero; finite F statistic undefined",
    )
    test = stats.f_oneway(*arrays)
    return result(
        statistic=test.statistic,
        p_value=test.pvalue,
        group_count=len(arrays),
        method="Classical one-way ANOVA",
    )


def chi_square_independence(contingency_table: list) -> dict:
    """Test independence in a nonnegative integer contingency table with Pearson chi-square and no Yates correction."""
    a = matrix(contingency_table, "contingency_table", 2)
    require(
        a.shape[1] >= 2 and np.all(a >= 0) and np.all(a == np.floor(a)),
        "Require at least 2x2 nonnegative integer counts",
    )
    require(
        np.all(a.sum(axis=0) > 0) and np.all(a.sum(axis=1) > 0),
        "Every row and column must have positive total",
    )
    chi, p, df, expected = stats.chi2_contingency(a, correction=False)
    return result(
        statistic=chi,
        p_value=p,
        degrees_of_freedom=df,
        expected_counts=expected,
        expected_counts_below_five=int(np.sum(expected < 5)),
        method="Pearson chi-square; no continuity correction",
    )


def bootstrap_mean_interval(
    values: list, confidence: float = 0.95, resamples: int = 1000, seed: int = 42
) -> dict:
    """Estimate an IID sample mean confidence interval with a reproducible percentile bootstrap; this is an approximate interval."""
    a = vector(values, minimum=2)
    require(
        0 < number(confidence, "confidence") < 1, "confidence must be between 0 and 1"
    )
    integer(resamples, "resamples", 100, 10000)
    integer(seed, "seed", 0, 2**32 - 1)
    rng = np.random.default_rng(seed)
    means = np.concatenate(
        [
            rng.choice(
                a, size=(min(128, resamples - start), len(a)), replace=True
            ).mean(axis=1)
            for start in range(0, resamples, 128)
        ]
    )
    low, high = np.quantile(means, [(1 - confidence) / 2, (1 + confidence) / 2])
    return result(
        mean=np.mean(a),
        lower=low,
        upper=high,
        confidence=confidence,
        resamples=resamples,
        seed=seed,
        method="IID percentile bootstrap; approximate",
    )


def linear_least_squares(matrix_a: list, vector_b: list) -> dict:
    """Solve a finite linear least-squares problem and report solution, rank, singular values and residual norm."""
    a, b = matrix(matrix_a, "matrix_a"), vector(vector_b, "vector_b")
    require(len(a) == len(b), "Matrix rows must match vector length")
    x, _, rank, singular = np.linalg.lstsq(a, b, rcond=None)
    return result(
        solution=x,
        rank=rank,
        singular_values=singular,
        residual_norm=np.linalg.norm(a @ x - b),
    )


def matrix_inverse(values: list) -> dict:
    """Invert a square nonsingular real numeric matrix and report its condition number and inverse residual."""
    a = matrix(values, "values")
    require(a.shape[0] == a.shape[1], "Require a square matrix")
    try:
        inverse = np.linalg.inv(a)
    except np.linalg.LinAlgError:
        raise InputValidationError("Matrix is singular")
    return result(
        inverse=inverse,
        condition_number=np.linalg.cond(a),
        residual_norm=np.linalg.norm(a @ inverse - np.eye(len(a))),
    )


def matrix_svd(values: list) -> dict:
    """Compute an economy singular-value decomposition of a real numeric matrix, returning U, singular values and V transpose."""
    a = matrix(values, "values")
    u, singular, vt = np.linalg.svd(a, full_matrices=False)
    return result(
        u=u,
        singular_values=singular,
        vt=vt,
        reconstruction_error=np.linalg.norm((u * singular) @ vt - a),
    )


def symmetric_eigen_decomposition(values: list) -> dict:
    """Compute real eigenvalues and orthonormal eigenvectors of a symmetric real matrix; reject nonsymmetric inputs."""
    a = matrix(values, "values")
    require(
        a.shape[0] == a.shape[1] and np.allclose(a, a.T, rtol=1e-10, atol=1e-12),
        "Require a symmetric square matrix",
    )
    eigenvalues, eigenvectors = np.linalg.eigh(a)
    return result(eigenvalues=eigenvalues, eigenvectors=eigenvectors)


def solve_linear_system(matrix_a: list, vector_b: list) -> dict:
    """Solve a square nonsingular real linear system A x = b and report the numeric residual."""
    a, b = matrix(matrix_a, "matrix_a"), vector(vector_b, "vector_b")
    require(
        a.shape[0] == a.shape[1] == len(b),
        "Require a square matrix matching vector length",
    )
    try:
        x = np.linalg.solve(a, b)
    except np.linalg.LinAlgError:
        raise InputValidationError("Matrix is singular")
    return result(solution=x, residual_norm=np.linalg.norm(a @ x - b))


def polynomial_least_squares_fit(x: list, y: list, degree: int = 2) -> dict:
    """Fit a polynomial to paired numeric data, returning descending-power coefficients and training residuals; reject rank-deficient fits."""
    a, b = _paired(x, y)
    integer(degree, "degree", 0, 5)
    require(
        len(np.unique(a)) > degree, "Need more distinct x values than polynomial degree"
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error", np.RankWarning)
        try:
            coefficients = np.polyfit(a, b, degree)
        except np.RankWarning:
            raise InputValidationError("Polynomial fit is numerically rank deficient")
    return result(
        coefficients=coefficients,
        degree=degree,
        fitted_values=np.polyval(coefficients, a),
        residual_sum_squares=np.sum((np.polyval(coefficients, a) - b) ** 2),
        coefficient_order="descending powers",
    )


def interpolate_linear(x: list, y: list, query_x: list) -> dict:
    """Linearly interpolate a real numeric curve at query points inside its measured x range; do not extrapolate."""
    a, b = _curve(x, y)
    q = vector(query_x, "query_x")
    require(
        np.all((q >= a[0]) & (q <= a[-1])), "Query points must be inside the x range"
    )
    return result(x=q, values=np.interp(q, a, b), method="linear interpolation")


def numerical_trapezoid_integration(x: list, y: list) -> dict:
    """Integrate a numeric curve on a strictly increasing grid using the composite trapezoidal rule."""
    a, b = _curve(x, y)
    return result(
        integral=np.trapz(b, a), point_count=len(a), method="composite trapezoidal rule"
    )


def finite_difference_gradient(x: list, y: list) -> dict:
    """Approximate dy/dx on a strictly increasing grid using central interior and first-order boundary finite differences."""
    a, b = _curve(x, y)
    return result(
        x=a,
        gradient=np.gradient(b, a, edge_order=1),
        method="numpy gradient; first-order boundaries",
    )


def split_train_test(
    features: list,
    targets: list,
    test_fraction: float = 0.25,
    seed: int = 42,
    stratify: bool = False,
) -> dict:
    """Split numeric feature rows and numeric or categorical targets into disjoint train/test sets with reproducible indices."""
    x = matrix(features, minimum_rows=4)
    require(
        isinstance(targets, list) and len(targets) == len(x),
        "Targets must match feature rows",
    )
    y = (
        labels(targets, "targets")
        if all(isinstance(v, str) for v in targets)
        else vector(targets, "targets")
    )
    require(
        0 < number(test_fraction, "test_fraction") < 1,
        "test_fraction must be between 0 and 1",
    )
    integer(seed, "seed", 0, 2**32 - 1)
    require(isinstance(stratify, bool), "stratify must be boolean")
    try:
        train, test = train_test_split(
            np.arange(len(x)),
            test_size=test_fraction,
            random_state=seed,
            stratify=y if stratify else None,
        )
    except ValueError as error:
        raise InputValidationError(str(error))
    return result(
        training_features=x[train],
        training_targets=y[train],
        test_features=x[test],
        test_targets=y[test],
        train_indices=train,
        test_indices=test,
        seed=seed,
    )


def standardize_numeric_features(training_features: list, features: list) -> dict:
    """Fit feature means and population scales on training data only, then standardize another matrix using those parameters."""
    train, data = _transform(training_features, features)
    scaler = StandardScaler().fit(train)
    return result(
        features=scaler.transform(data),
        mean=scaler.mean_,
        scale=scaler.scale_,
        fit_basis="training_features only",
    )


def minmax_scale_features(training_features: list, features: list) -> dict:
    """Fit feature minima/maxima on training rows and apply their zero-to-one scaling; out-of-training-range values are not clipped."""
    train, data = _transform(training_features, features)
    scaler = MinMaxScaler().fit(train)
    return result(
        features=scaler.transform(data),
        data_min=scaler.data_min_,
        data_max=scaler.data_max_,
        scale=scaler.scale_,
        offset=scaler.min_,
        fit_basis="training_features only",
    )


def median_impute_features(training_features: list, features: list) -> dict:
    """Fit per-feature medians on training data and replace explicit null cells in another numeric matrix; reject all-null training columns."""
    train, data = matrix(training_features, "training_features", 2, True), matrix(
        features, allow_null=True
    )
    require(train.shape[1] == data.shape[1], "Feature widths differ")
    require(
        not np.any(np.all(np.isnan(train), axis=0)),
        "Every training column needs an observed value",
    )
    imputer = SimpleImputer(strategy="median").fit(train)
    return result(
        features=imputer.transform(data),
        medians=imputer.statistics_,
        fit_basis="training_features only",
    )


def polynomial_features_transform(
    features: list, degree: int = 2, include_bias: bool = False
) -> dict:
    """Expand a numeric feature matrix into bounded polynomial interaction features and return the exponent table."""
    x = matrix(features)
    integer(degree, "degree", 1, 5)
    require(isinstance(include_bias, bool), "include_bias must be boolean")
    width = math.comb(x.shape[1] + degree, degree) - int(not include_bias)
    require(
        width <= 200 and len(x) * width <= MAX_CELLS,
        "Polynomial expansion exceeds bounded output size",
    )
    transformer = PolynomialFeatures(degree=degree, include_bias=include_bias)
    transformed = transformer.fit_transform(x)
    return result(features=transformed, powers=transformer.powers_, degree=degree)


def principal_component_projection(
    training_features: list, features: list, n_components: int = 2
) -> dict:
    """Fit PCA on training data only and project another matrix; return means, components and explained variance without automatic scaling."""
    train, data = _transform(training_features, features)
    integer(n_components, "n_components", 1, min(train.shape))
    require(
        np.sum(np.var(train, axis=0)) > 0,
        "PCA explained variance is undefined for constant training data",
    )
    pca = PCA(n_components=n_components, svd_solver="full").fit(train)
    return result(
        features=pca.transform(data),
        components=pca.components_,
        mean=pca.mean_,
        explained_variance=pca.explained_variance_,
        explained_variance_ratio=pca.explained_variance_ratio_,
        fit_basis="training_features only",
    )


def fit_linear_regression(training_features: list, targets: list) -> dict:
    """Fit ordinary least-squares regression with an intercept and export a portable JSON linear-model artifact."""
    x, y = _training(training_features, targets)
    return _linear_artifact(LinearRegression().fit(x, y), "linear_regression", x, y)


def fit_ridge_regression(
    training_features: list, targets: list, alpha: float = 1.0
) -> dict:
    """Fit L2-regularized ridge regression with an unpenalized intercept and export its JSON coefficients; features are not automatically scaled."""
    x, y = _training(training_features, targets)
    require(number(alpha, "alpha") > 0, "alpha must be positive")
    return _linear_artifact(Ridge(alpha=alpha).fit(x, y), "ridge_regression", x, y)


def fit_logistic_regression(
    training_features: list,
    targets: list,
    regularization_c: float = 1.0,
    max_iterations: int = 200,
) -> dict:
    """Fit standardized L2 logistic classification on training data, exporting classes, coefficients and scaling parameters as JSON."""
    x, y = matrix(training_features, minimum_rows=4), labels(targets, "targets", 4)
    require(
        len(x) == len(y) and 2 <= len(np.unique(y)) <= 20,
        "Require matching targets and 2..20 classes",
    )
    require(
        number(regularization_c, "regularization_c") > 0,
        "regularization_c must be positive",
    )
    integer(max_iterations, "max_iterations", 10, 1000)
    scaler = StandardScaler().fit(x)
    clf = LogisticRegression(
        C=regularization_c, max_iter=max_iterations, solver="lbfgs"
    )
    with warnings.catch_warnings():
        warnings.simplefilter("error", ConvergenceWarning)
        try:
            clf.fit(scaler.transform(x), y)
        except ConvergenceWarning:
            raise InputValidationError(
                "Logistic fit did not converge; increase the iteration budget or inspect features"
            )
    return result(
        model={
            "type": "logistic_regression",
            "n_features": x.shape[1],
            "classes": clf.classes_,
            "coefficients": clf.coef_,
            "intercepts": clf.intercept_,
            "mean": scaler.mean_,
            "scale": scaler.scale_,
        },
        n_training_rows=len(x),
        iterations=clf.n_iter_,
        training_accuracy=clf.score(scaler.transform(x), y),
        metric_basis="Training fit only; not held-out performance",
    )


def predict_linear_model(model: dict, features: list) -> dict:
    """Apply an exported linear or ridge JSON model to a numeric matrix; reject incompatible feature widths or invalid coefficients."""
    require(
        isinstance(model, dict)
        and model.get("type") in {"linear_regression", "ridge_regression"},
        "Require an exported linear/ridge model",
    )
    x = matrix(features)
    coeff = vector(model.get("coefficients"), "coefficients")
    require(
        model.get("n_features") == x.shape[1] == len(coeff),
        "Model and feature widths differ",
    )
    intercept = number(model.get("intercept"), "intercept")
    return result(predictions=x @ coeff + intercept, model_type=model["type"])


def predict_logistic_model(model: dict, features: list) -> dict:
    """Apply an exported standardized logistic JSON model, returning class predictions and probabilities in its declared class order."""
    require(
        isinstance(model, dict) and model.get("type") == "logistic_regression",
        "Require an exported logistic model",
    )
    x = matrix(features)
    classes = labels(model.get("classes"), "classes", 2)
    require(
        len(classes) <= 20 and len(np.unique(classes)) == len(classes),
        "Model classes must be unique",
    )
    coeff = matrix(model.get("coefficients"), "coefficients")
    intercepts = vector(model.get("intercepts"), "intercepts")
    mean, scale = vector(model.get("mean"), "mean"), vector(model.get("scale"), "scale")
    require(
        model.get("n_features")
        == x.shape[1]
        == len(mean)
        == len(scale)
        == coeff.shape[1],
        "Model and feature widths differ",
    )
    require(
        np.all(scale > 0) and coeff.shape[0] == len(intercepts),
        "Invalid scaling or intercept count",
    )
    require(
        coeff.shape[0] == (1 if len(classes) == 2 else len(classes)),
        "Coefficient rows do not match class count",
    )
    scores = ((x - mean) / scale) @ coeff.T + intercepts
    probability = (
        np.column_stack([1 - expit(scores[:, 0]), expit(scores[:, 0])])
        if len(classes) == 2
        else softmax(scores, axis=1)
    )
    return result(
        predictions=classes[np.argmax(probability, axis=1)],
        probabilities=probability,
        classes=classes,
    )


def regression_metrics(truth: list, predicted: list) -> dict:
    """Measure held-out regression predictions with MAE, MSE, RMSE and R squared; report null R squared for constant truth."""
    a, b = _paired(truth, predicted)
    mse = mean_squared_error(a, b)
    return result(
        mae=mean_absolute_error(a, b),
        mse=mse,
        rmse=np.sqrt(mse),
        r_squared=r2_score(a, b) if np.ptp(a) > 0 else None,
        count=len(a),
        r_squared_defined=bool(np.ptp(a) > 0),
    )


def classification_metrics(truth: list, predicted: list) -> dict:
    """Score categorical predictions with accuracy, macro precision/recall/F1 and a confusion matrix using an explicit label order."""
    a, b = labels(truth, "truth"), labels(predicted, "predicted")
    require(
        len(a) == len(b) and a.dtype.kind == b.dtype.kind,
        "Truth and predicted labels must match in length and label type",
    )
    order = np.unique(np.concatenate([a, b]))
    precision, recall, f1, _ = precision_recall_fscore_support(
        a, b, labels=order, average="macro", zero_division=0
    )
    return result(
        accuracy=accuracy_score(a, b),
        macro_precision=precision,
        macro_recall=recall,
        macro_f1=f1,
        labels=order,
        confusion_matrix=confusion_matrix(a, b, labels=order),
        undefined_class_divisions="set to zero",
    )


def kmeans_clustering(features: list, clusters: int = 2, seed: int = 42) -> dict:
    """Cluster finite numeric rows using reproducible Euclidean k-means with ten initializations; return labels, centroids and inertia."""
    x = matrix(features, minimum_rows=2)
    integer(clusters, "clusters", 1, min(len(x), 100))
    integer(seed, "seed", 0, 2**32 - 1)
    require(
        len(np.unique(x, axis=0)) >= clusters,
        "Need at least as many distinct points as clusters",
    )
    model = KMeans(n_clusters=clusters, n_init=10, random_state=seed).fit(x)
    return result(
        labels=model.labels_,
        centroids=model.cluster_centers_,
        inertia=model.inertia_,
        seed=seed,
    )


def dbscan_clustering(features: list, eps: float = 0.5, min_samples: int = 5) -> dict:
    """Cluster a bounded numeric point cloud using Euclidean DBSCAN; labels minus one denote noise, not execution failure."""
    x = matrix(features, minimum_rows=2)
    require(len(x) <= 2000, "DBSCAN is bounded to 2000 rows")
    require(number(eps, "eps") > 0, "eps must be positive")
    integer(min_samples, "min_samples", 1, len(x))
    model = DBSCAN(eps=eps, min_samples=min_samples, n_jobs=1).fit(x)
    return result(
        labels=model.labels_,
        cluster_count=len(set(model.labels_) - {-1}),
        noise_count=int(np.sum(model.labels_ == -1)),
    )


def cross_validate_regressor(
    features: list, targets: list, folds: int = 5, alpha: float = 1.0, seed: int = 42
) -> dict:
    """Evaluate ridge regression with shuffled K-fold splits and train-only standardization inside every fold; return held-out metrics and indices."""
    x, y = _training(features, targets)
    integer(folds, "folds", 2, 10)
    integer(seed, "seed", 0, 2**32 - 1)
    require(
        len(x) >= 2 * folds and number(alpha, "alpha") > 0,
        "Need at least two validation rows per fold and positive alpha",
    )
    scores = []
    for train, test in KFold(n_splits=folds, shuffle=True, random_state=seed).split(x):
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha)).fit(
            x[train], y[train]
        )
        pred = model.predict(x[test])
        scores.append(
            {
                "train_indices": train.tolist(),
                "test_indices": test.tolist(),
                "rmse": float(np.sqrt(mean_squared_error(y[test], pred))),
                "mae": float(mean_absolute_error(y[test], pred)),
                "r_squared": (
                    float(r2_score(y[test], pred)) if np.ptp(y[test]) > 0 else None
                ),
            }
        )
    return result(
        fold_results=scores,
        mean_rmse=np.mean([s["rmse"] for s in scores]),
        mean_mae=np.mean([s["mae"] for s in scores]),
        folds=folds,
        seed=seed,
        preprocessing_fit_basis="each training fold only",
    )
