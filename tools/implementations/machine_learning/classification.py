"""Explicit bounded numeric classification, without filename or feature inference."""

import warnings

import numpy as np
from sklearn.ensemble import AdaBoostClassifier, RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPClassifier

from tools.implementations.shared.data_validation import (
    integer, labels, matrix, require, result,
)


def train_and_predict_classifier(
    training_features: list,
    training_targets: list,
    features: list,
    algorithm: str = "random_forest",
    seed: int = 42,
    iterations: int = 100,
) -> dict:
    """Fit the declared classifier and predict explicit numeric rows in their source order.

    No scaling, splitting, feature generation or accuracy computation is implicit.
    ``iterations`` is tree/boosting count, or MLP's maximum optimization epochs.
    MLP uses one 64-unit ReLU layer, Adam, alpha=0.0001 and no early stopping;
    AdaBoost uses default depth-one weak learners and learning_rate=1;
    random forest uses sqrt feature sampling and unrestricted tree depth.
    A fitted estimator is kept only for this call; no pickle is read or exported.
    """
    train = matrix(training_features, "training_features", 2)
    predict = matrix(features, "features")
    targets = labels(training_targets, "training_targets", 2)
    require(len(train) == len(targets), "Training rows and targets must align")
    require(train.shape[1] == predict.shape[1], "Training and prediction widths differ")
    require(len(np.unique(targets)) >= 2, "Training targets need at least two classes")
    require(len(np.unique(targets)) <= 100, "At most100 distinct classes")
    require(algorithm in {"random_forest", "adaboost", "mlp"}, "Unknown classifier algorithm")
    integer(seed, "seed", 0, 2**32 - 1)
    integer(iterations, "iterations", 1, 500)
    if algorithm == "random_forest":
        model = RandomForestClassifier(n_estimators=iterations, random_state=seed, n_jobs=1)
    elif algorithm == "adaboost":
        model = AdaBoostClassifier(n_estimators=iterations, random_state=seed)
    else:
        model = MLPClassifier(hidden_layer_sizes=(64,), max_iter=iterations, random_state=seed)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        model.fit(train, targets)
        predictions = model.predict(predict)
        probabilities = model.predict_proba(predict)
    require(np.all(np.isfinite(probabilities)), "Classifier produced nonfinite probabilities")
    return result(
        algorithm=algorithm, seed=seed, iterations=iterations,
        classes=model.classes_, predictions=predictions, probabilities=probabilities,
        n_training_rows=len(train), n_prediction_rows=len(predict), n_features=train.shape[1],
        convergence_warning=any(issubclass(w.category, ConvergenceWarning) for w in caught),
        warnings=list(dict.fromkeys(str(w.message) for w in caught)),
        fitted_iterations=int(model.n_iter_) if algorithm == "mlp" else len(model.estimators_),
        scope="Fit and predict only. Inputs retain caller-supplied scaling and order; no implicit CSV, split, features, metrics or persisted estimator.",
    )
