"""Temporal block training, feature selection, SVM search and evaluation."""

from __future__ import annotations

import logging
import warnings
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from feature_engine.selection import DropCorrelatedFeatures
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.dummy import DummyClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, ParameterGrid, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from tcc_crypto.dataset import target_name
from tcc_crypto.preparation import validate_calendar


def _binary_metrics(y_true: Sequence[int], y_pred: Sequence[int]) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def calculate_classification_metrics(
    y_true: Sequence[int], y_pred: Sequence[int], decision_scores: Sequence[float]
) -> dict[str, object]:
    """Calculate approved fold metrics and mark undefined ranking metrics."""
    true = pd.Series(y_true, dtype="int64")
    predicted = pd.Series(y_pred, dtype="int64")
    scores = pd.Series(decision_scores, dtype="float64")
    if true.empty or len(true) != len(predicted) or len(true) != len(scores):
        raise ValueError("Metric inputs must be non-empty and equally sized.")
    diagnostics: list[str] = []
    if true.nunique() < 2:
        roc_auc = float("nan")
        average_precision = float("nan")
        diagnostics.append("single_class_validation")
    else:
        roc_auc = float(roc_auc_score(true, scores))
        average_precision = float(average_precision_score(true, scores))
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="A single label was found", category=UserWarning
        )
        balanced_accuracy = float(balanced_accuracy_score(true, predicted))
    return {
        **_binary_metrics(true, predicted),
        "balanced_accuracy": balanced_accuracy,
        "roc_auc": roc_auc,
        "average_precision": average_precision,
        "metric_diagnostic": "|".join(diagnostics),
    }


PARAMETER_COLUMNS = ("kernel", "C", "gamma", "degree", "coef0", "class_weight")
LOGGER = logging.getLogger(__name__)


class SearchFailure(ValueError):
    """Keep computed CV evidence when no candidate qualifies for refitting."""

    def __init__(self, message, cv_results):
        super().__init__(message)
        self.cv_results = cv_results


def _parameter_values(parameters: Mapping[str, object]) -> dict[str, object]:
    return {column: parameters.get(column, pd.NA) for column in PARAMETER_COLUMNS}


def select_best_candidate(candidates: pd.DataFrame, *, tolerance: float) -> pd.Series:
    """Select one candidate using the approved deterministic tie-break rule."""
    ranked = rank_candidates(candidates, tolerance=tolerance)
    return ranked.loc[ranked["selection_rank"] == 1].iloc[0]


def rank_candidates(candidates: pd.DataFrame, *, tolerance: float) -> pd.DataFrame:
    """Rank candidates with F1 tolerance and the approved secondary ordering."""
    required = {
        "mean_f1",
        "mean_precision",
        "f1_standard_deviation",
        "mean_roc_auc",
        "kernel",
        "C",
        "candidate_order",
        "failed_fold_count",
    }
    missing = required.difference(candidates.columns)
    if missing:
        raise ValueError(f"Candidate table is missing columns: {sorted(missing)}.")
    valid = candidates.loc[
        (candidates["failed_fold_count"] == 0) & candidates["mean_f1"].notna()
    ].copy()
    if valid.empty:
        raise ValueError("No candidate completed every temporal fold.")
    kernel_order = {"linear": 0, "rbf": 1, "poly": 2}
    ranked_indexes: list[object] = []
    remaining = valid.copy()
    while not remaining.empty:
        best_f1 = float(remaining["mean_f1"].max())
        tied = remaining.loc[remaining["mean_f1"] >= best_f1 - tolerance].copy()
        tied["_precision"] = tied["mean_precision"].fillna(float("-inf"))
        tied["_f1_std"] = tied["f1_standard_deviation"].fillna(float("inf"))
        tied["_roc_auc"] = tied["mean_roc_auc"].fillna(float("-inf"))
        tied["_kernel"] = tied["kernel"].map(kernel_order).fillna(len(kernel_order))
        tied = tied.sort_values(
            [
                "_precision",
                "_f1_std",
                "_roc_auc",
                "_kernel",
                "C",
                "candidate_order",
            ],
            ascending=[False, True, False, True, True, True],
            kind="stable",
        )
        ranked_indexes.extend(tied.index)
        remaining = remaining.drop(index=tied.index)

    invalid = candidates.drop(index=valid.index).sort_values(
        "candidate_order", kind="stable"
    )
    ranked_indexes.extend(invalid.index)
    ranked = candidates.loc[ranked_indexes].copy()
    ranked.insert(4, "selection_rank", range(1, len(ranked) + 1))
    return ranked


class FeatureSelector(TransformerMixin, BaseEstimator):
    """The supplied recorte selection, with fitted state and explanatory evidence."""

    def __init__(self, variance_threshold=0.01, correlation_threshold=0.8):
        self.variance_threshold = variance_threshold
        self.correlation_threshold = correlation_threshold

    def fit(self, X, y=None):
        self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.n_features_in_ = X.shape[1]
        self.fallback_error_ = ""
        self.variance_ = VarianceThreshold(self.variance_threshold)
        try:
            self.variance_.fit(X)
            remaining = list(X.columns[self.variance_.get_support()])
        except ValueError as error:
            self.fallback_error_ = str(error)
            LOGGER.warning("Feature selection fallback: %s", error)
            sample = X.var(numeric_only=True)
            if sample.isna().all():
                raise ValueError("No feature has a valid fallback variance.") from error
            remaining = [sample.idxmax()]
        self.variance_features_ = remaining
        self.correlation_ = None
        if len(remaining) > 1 and not self.fallback_error_:
            self.correlation_ = DropCorrelatedFeatures(
                threshold=self.correlation_threshold,
                method="pearson",
                missing_values="ignore",
            )
            self.correlation_.fit(X[remaining])
            self.selected_features_ = [
                c for c in remaining if c not in self.correlation_.features_to_drop_
            ]
        else:
            self.selected_features_ = remaining
        self.correlations_ = X[remaining].corr()
        self.variances_ = X.var(ddof=0)
        self.sample_variances_ = X.var(ddof=1)
        return self

    def transform(self, X):
        return X.loc[:, self.selected_features_].copy()

    def audit(self) -> pd.DataFrame:
        rows = []
        mapping = getattr(self.correlation_, "correlated_feature_dict_", {})
        for position, feature in enumerate(self.feature_names_in_):
            kept = feature in self.selected_features_
            related = next(
                (key for key, values in mapping.items() if feature in values), ""
            )
            reason = (
                ("fallback_retained" if kept else "fallback_discarded")
                if self.fallback_error_
                else (
                    "retained"
                    if kept
                    else (
                        "low_variance"
                        if feature not in self.variance_features_
                        else "high_correlation"
                    )
                )
            )
            rows.append(
                {
                    "feature": feature,
                    "position": position,
                    "variance": self.variances_[feature],
                    "fallback_sample_variance": self.sample_variances_[feature],
                    "selected": kept,
                    "reason": reason,
                    "related_feature": related,
                    "correlation": self.correlations_.loc[feature, related]
                    if related
                    else np.nan,
                    "fallback_error": self.fallback_error_,
                }
            )
        return pd.DataFrame(rows)


def outer_blocks(size: int, window: int):
    """Disjoint adjacent blocks; only the last validation block may be partial."""
    for start in range(0, size - window, window):
        yield (
            np.arange(start, start + window),
            np.arange(start + window, min(start + 2 * window, size)),
        )


def describe_windows(dataset: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """Inspect boundaries before fitting, using the same block/split constructors."""
    data = dataset.loc[dataset.is_usable].reset_index(drop=True)
    rows = []
    for window in settings["windows"]:
        for block, (a, b) in enumerate(outer_blocks(len(data), window)):
            for scope, fold, train, test in [
                ("outer", -1, a, b),
                *[
                    ("inner", i, a[c], a[d])
                    for i, (c, d) in enumerate(
                        TimeSeriesSplit(**settings["temporal_cross_validation"]).split(
                            a
                        )
                    )
                ],
            ]:
                rows.append(
                    {
                        "window_size": window,
                        "block_id": block,
                        "scope": scope,
                        "fold": fold,
                        "training_start": data.iloc[train[0]].feature_time_utc,
                        "training_end": data.iloc[train[-1]].feature_time_utc,
                        "validation_start": data.iloc[test[0]].feature_time_utc,
                        "validation_end": data.iloc[test[-1]].feature_time_utc,
                        "training_count": len(train),
                        "validation_count": len(test),
                        "fit_time_utc": assert_label_availability(
                            data.iloc[train], data.iloc[test]
                        ),
                    }
                )
    return pd.DataFrame(rows)


def pipeline(settings: dict, estimator=None) -> Pipeline:
    return Pipeline(
        [
            (
                "scaling",
                StandardScaler(**settings["scaling"]).set_output(transform="pandas"),
            ),
            ("selection", FeatureSelector(**settings["selection"])),
            (
                "svc",
                SVC(random_state=settings["random_seed"])
                if estimator is None
                else estimator,
            ),
        ]
    )


def score_estimator(estimator, X, y):
    predicted = estimator.predict(X)
    if hasattr(estimator, "decision_function"):
        scores = estimator.decision_function(X)
    else:
        probabilities = estimator.predict_proba(X)
        classes = estimator.classes_
        scores = (
            probabilities[:, list(classes).index(1)]
            if 1 in classes
            else np.zeros(len(X))
        )
    values = calculate_classification_metrics(y, predicted, scores)
    return {
        name: value for name, value in values.items() if name != "metric_diagnostic"
    }


def candidate_table(cv_results: dict) -> pd.DataFrame:
    rows = []
    splits = sorted(
        k for k in cv_results if k.startswith("split") and k.endswith("_test_f1")
    )
    for i, parameters in enumerate(cv_results["params"]):
        row = {
            "candidate_order": i,
            **_parameter_values(
                {k.removeprefix("svc__"): v for k, v in parameters.items()}
            ),
            "failed_fold_count": sum(not np.isfinite(cv_results[k][i]) for k in splits),
        }
        for metric in (
            "accuracy",
            "precision",
            "recall",
            "f1",
            "balanced_accuracy",
            "roc_auc",
            "average_precision",
        ):
            values = [
                cv_results[f"split{j}_test_{metric}"][i] for j in range(len(splits))
            ]
            row[f"mean_{metric}"] = float(pd.Series(values).mean())
        row["f1_standard_deviation"] = cv_results["std_test_f1"][i]
        rows.append(row)
    return pd.DataFrame(rows)


def fit_search(X, y, settings: dict, grid: dict):
    """One integrated search/refit; preserve the approved ranking callable."""

    def refit(cv_results):
        try:
            best = select_best_candidate(
                candidate_table(cv_results),
                tolerance=grid["selection"]["floating_point_tolerance"],
            )
        except ValueError as error:
            raise SearchFailure(str(error), cv_results) from error
        return int(best.candidate_order)

    search = GridSearchCV(
        pipeline(settings),
        [
            {f"svc__{k}": v for k, v in branch.items()}
            for branch in grid["parameter_grid"]
        ],
        scoring=score_estimator,
        cv=TimeSeriesSplit(**settings["temporal_cross_validation"]),
        refit=refit,
        error_score=np.nan,
        return_train_score=False,
        n_jobs=1,
    )
    search.fit(X, y)
    return search


def assert_label_availability(
    training: pd.DataFrame, validation: pd.DataFrame
) -> pd.Timestamp:
    """Fit after first validation feature candle closes, before its outcome day."""
    fit_time = validation.iloc[0].feature_available_at_utc
    if (
        training.target_available_at_utc > fit_time
    ).any() or training.target_available_at_utc.isna().any():
        raise ValueError("Training uses an outcome not yet available at fit time.")
    if fit_time >= validation.iloc[0].target_time_utc:
        raise ValueError("Prediction occurs after its target day begins.")
    return fit_time


def train_symbol(
    dataset: pd.DataFrame, symbol: str, settings: dict, grid: dict
) -> dict[str, pd.DataFrame]:
    """Calculate one asset's results; the orchestrator owns persistence."""
    buckets = {
        name: []
        for name in (
            "predictions",
            "metrics",
            "selection",
            "correlations",
            "scaling",
            "blocks",
            "folds",
            "candidates",
            "fold_scores",
            "winners",
            "failures",
        )
    }

    def save(name, frame, identity):
        if len(frame):
            buckets[name].append(frame.assign(**identity))

    if symbol in settings["excluded_symbols"]:
        save(
            "failures",
            pd.DataFrame([{"status": "explicit_symbol_exclusion"}]),
            {"symbol": symbol},
        )
        return {
            k: pd.concat(v, ignore_index=True) if v else pd.DataFrame()
            for k, v in buckets.items()
        }
    data = dataset.loc[dataset.is_usable].reset_index(drop=True)
    validate_calendar(pd.DatetimeIndex(data.feature_time_utc))
    features = settings["features"]["active_features"]
    for window in settings["windows"]:
        for q in settings["targets"]:
            target = target_name(q)
            if len(data) <= window:
                save(
                    "failures",
                    pd.DataFrame([{"status": "insufficient_complete_window"}]),
                    {"symbol": symbol, "window_size": window, "target": target},
                )
            for block, (train_indices, test_indices) in enumerate(
                outer_blocks(len(data), window)
            ):
                identity = {
                    "symbol": symbol,
                    "window_size": window,
                    "target": target,
                    "block_id": block,
                }
                LOGGER.info("Training block: %s", identity)
                train = data.iloc[train_indices]
                test = data.iloc[test_indices]
                fit_time = assert_label_availability(train, test)
                save(
                    "blocks",
                    pd.DataFrame(
                        [
                            {
                                "training_start": train.feature_time_utc.iloc[0],
                                "training_end": train.feature_time_utc.iloc[-1],
                                "validation_start": test.feature_time_utc.iloc[0],
                                "validation_end": test.feature_time_utc.iloc[-1],
                                "training_count": len(train),
                                "validation_count": len(test),
                                "positive_count": int(train[target].sum()),
                                "negative_count": int(len(train) - train[target].sum()),
                                "fit_time_utc": fit_time,
                            }
                        ]
                    ),
                    identity,
                )
                X = train[features]
                y = train[target].astype(int)
                blocked = y.nunique() < 2
                inner_blocked = audit_inner_splits(
                    train, X, y, settings, identity, save
                )
                search, search_error = search_and_audit(
                    X, y, settings, grid, blocked, inner_blocked, identity, save
                )
                predictions = predict_models(
                    train,
                    test,
                    X,
                    y,
                    features,
                    settings,
                    identity,
                    fit_time,
                    blocked,
                    inner_blocked,
                    search,
                    search_error,
                    save,
                )
                save("predictions", predictions, identity)
                evaluate_predictions(predictions, settings, search, identity, save)
    return {
        k: pd.concat(v, ignore_index=True) if v else pd.DataFrame()
        for k, v in buckets.items()
    }


def _save_preprocessing(fitted, identity, save):
    selector = fitted.named_steps["selection"]
    scaler = fitted.named_steps["scaling"]
    selection = selector.audit()
    save("selection", selection, identity)
    if identity["fit_scope"] == "full_in_sample":
        LOGGER.info(
            "Feature selection %s\n%s", identity, selection.to_string(index=False)
        )
    correlations = (
        selector.correlations_.rename_axis("feature")
        .reset_index()
        .melt(id_vars="feature", var_name="related_feature", value_name="correlation")
    )
    save("correlations", correlations, identity)
    save(
        "scaling",
        pd.DataFrame(
            {
                "feature": scaler.feature_names_in_,
                "mean": scaler.mean_,
                "scale": scaler.scale_,
                "variance": scaler.var_,
            }
        ),
        identity,
    )


def audit_inner_splits(train, X, y, settings, identity, save) -> bool:
    """Record each inner calendar, class count and training-only preprocessing."""
    inner_blocked = False
    for fold, (a, b) in enumerate(
        TimeSeriesSplit(**settings["temporal_cross_validation"]).split(X)
    ):
        inner_time = assert_label_availability(train.iloc[a], train.iloc[b])
        inner_blocked |= y.iloc[a].nunique() < 2
        fold_id = {**identity, "fit_scope": "inner", "fold": fold}
        save(
            "folds",
            pd.DataFrame(
                [
                    {
                        "training_start": train.iloc[a].feature_time_utc.iloc[0],
                        "training_end": train.iloc[a].feature_time_utc.iloc[-1],
                        "validation_start": train.iloc[b].feature_time_utc.iloc[0],
                        "validation_end": train.iloc[b].feature_time_utc.iloc[-1],
                        "training_count": len(a),
                        "validation_count": len(b),
                        "positive_count": int(y.iloc[a].sum()),
                        "negative_count": int(len(a) - y.iloc[a].sum()),
                        "fit_time_utc": inner_time,
                        "status": "single_class_training"
                        if y.iloc[a].nunique() < 2
                        else "ok",
                    }
                ]
            ),
            fold_id,
        )
        try:
            fitted = pipeline(settings)[:-1].fit(X.iloc[a], y.iloc[a])
            _save_preprocessing(fitted, fold_id, save)
        except ValueError as error:
            save(
                "failures",
                pd.DataFrame(
                    [
                        {
                            "status": "preprocessing_failed",
                            "error": str(error),
                        }
                    ]
                ),
                fold_id,
            )
    return inner_blocked


def search_and_audit(X, y, settings, grid, blocked, inner_blocked, identity, save):
    """Run integrated search/refit and preserve candidate evidence, including failures."""
    search = None
    evidence_saved = False
    search_error = ""
    if not blocked:
        captured = []
        try:
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                search = fit_search(X, y, settings, grid)
            candidates = candidate_table(search.cv_results_)
            save(
                "candidates",
                rank_candidates(
                    candidates,
                    tolerance=grid["selection"]["floating_point_tolerance"],
                ),
                identity,
            )
            save("winners", candidates.iloc[[search.best_index_]], identity)
            for fold in range(5):
                scores = pd.DataFrame({"candidate_order": range(len(candidates))})
                for metric in settings["metrics"]:
                    scores[metric] = search.cv_results_[f"split{fold}_test_{metric}"]
                scores["status"] = np.where(scores.f1.notna(), "ok", "fit_failed")
                save("fold_scores", scores, {**identity, "fold": fold})
        except ValueError as error:
            search_error = str(error)
            if isinstance(error, SearchFailure):
                evidence_saved = True
                save(
                    "candidates",
                    candidate_table(error.cv_results),
                    identity,
                )
                for fold in range(5):
                    scores = pd.DataFrame(
                        {"candidate_order": range(len(error.cv_results["params"]))}
                    )
                    for metric in settings["metrics"]:
                        scores[metric] = error.cv_results[f"split{fold}_test_{metric}"]
                    scores["status"] = np.where(scores.f1.notna(), "ok", "fit_failed")
                    save("fold_scores", scores, {**identity, "fold": fold})
        finally:
            save(
                "failures",
                pd.DataFrame(
                    [
                        {
                            "status": "search_warning",
                            "warning_type": warning.category.__name__,
                            "error": str(warning.message),
                        }
                        for warning in captured
                    ]
                ),
                identity,
            )
    if search is None and not evidence_saved:
        failure = (
            "single_class_training" if blocked or inner_blocked else "search_failed"
        )
        candidates = pd.DataFrame(
            [
                {
                    "candidate_order": i,
                    **_parameter_values(params),
                    "status": failure,
                    "error": search_error,
                }
                for i, params in enumerate(ParameterGrid(grid["parameter_grid"]))
            ]
        )
        save("candidates", candidates, identity)
        for fold in range(5):
            save(
                "fold_scores",
                candidates[["candidate_order", "status", "error"]].copy(),
                {**identity, "fold": fold},
            )
    return search, search_error


def predict_models(
    train,
    test,
    X,
    y,
    features,
    settings,
    identity,
    fit_time,
    blocked,
    inner_blocked,
    search,
    search_error,
    save,
) -> pd.DataFrame:
    """Fit comparisons and predict both roles without using validation outcomes."""
    predicted_parts = []
    for name in settings["models"]:
        status = "ok"
        estimator = None
        if blocked:
            status = "single_class_training"
        elif name == "tuned_svc":
            if inner_blocked:
                status = "single_class_training_fold"
            elif search is None:
                status = "search_failed"
            else:
                estimator = search.best_estimator_
        else:
            model = {
                "default_svc": SVC(random_state=settings["random_seed"]),
                "always_negative": DummyClassifier(strategy="constant", constant=0),
                "training_class_frequency": DummyClassifier(strategy="prior"),
            }[name]
            try:
                estimator = pipeline(settings, model).fit(X, y)
            except ValueError as error:
                status = "fit_failed"
                search_error = str(error)
        if estimator is not None and name == "tuned_svc":
            _save_preprocessing(
                estimator,
                {**identity, "fit_scope": "full_in_sample", "fold": -1},
                save,
            )
        if status != "ok":
            save(
                "failures",
                pd.DataFrame(
                    [
                        {
                            "model": name,
                            "status": status,
                            "error": search_error,
                        }
                    ]
                ),
                identity,
            )
        for role, part in [("in_sample", train), ("out_of_sample", test)]:
            rows = part[["feature_time_utc", "target_time_utc"]].copy()
            rows["actual"] = part[identity["target"]].astype("Int64")
            rows["predicted"] = pd.Series(pd.NA, index=part.index, dtype="Int64")
            rows["score"] = np.nan
            if estimator is not None:
                rows["predicted"] = estimator.predict(part[features])
                if hasattr(estimator, "decision_function"):
                    rows["score"] = estimator.decision_function(part[features])
                else:
                    rows["score"] = estimator.predict_proba(part[features])[
                        :, list(estimator.classes_).index(1)
                    ]
            rows["role"] = role
            rows["model"] = name
            rows["status"] = status
            rows["fit_time_utc"] = fit_time
            rows["prediction_time_utc"] = part.feature_available_at_utc
            if role == "in_sample":
                rows["prediction_time_utc"] = fit_time
            predicted_parts.append(rows)
    predictions = pd.concat(predicted_parts, ignore_index=True)
    return predictions


def evaluate_predictions(predictions, settings, search, identity, save) -> None:
    """Evaluate each role on common successful dates across approved comparisons."""
    for role, group in predictions.groupby("role", sort=False):
        valid_dates = (
            group.loc[group.status == "ok"].groupby("feature_time_utc").model.nunique()
        )
        common = valid_dates.index[valid_dates == len(settings["models"])]
        for name, rows in group.groupby("model", sort=False):
            evaluated = rows.loc[rows.feature_time_utc.isin(common)]
            metric = {
                "role": role,
                "model": name,
                "attempted_count": len(rows),
                "evaluated_count": len(evaluated),
                "omitted_count": len(rows) - len(evaluated),
                "status": "ok" if len(evaluated) else "no_common_predictions",
            }
            if len(evaluated):
                metric.update(
                    calculate_classification_metrics(
                        evaluated.actual,
                        evaluated.predicted,
                        evaluated.score,
                    )
                )
                truth = evaluated.actual.astype(int)
                guess = evaluated.predicted.astype(int)
                for label, a, b in [
                    ("true_negative", 0, 0),
                    ("false_positive", 0, 1),
                    ("false_negative", 1, 0),
                    ("true_positive", 1, 1),
                ]:
                    metric[label] = int(((truth == a) & (guess == b)).sum())
            if search is not None and name == "tuned_svc":
                metric.update(
                    {k.removeprefix("svc__"): v for k, v in search.best_params_.items()}
                )
            save("metrics", pd.DataFrame([metric]), identity)
