"""Frozen-parameter daily walk-forward classification and matched baselines."""

from __future__ import annotations

import json
from dataclasses import dataclass
from time import perf_counter
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.metrics import confusion_matrix, precision_recall_curve, roc_curve
from sklearn.svm import SVC

from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.features.warmup import _validate_numeric_feature_frame
from tcc_crypto.modeling.config import (
    DailyFeatureSelectionConfig,
    DailySvmGridSearchConfig,
    expand_parameter_grid,
)
from tcc_crypto.modeling.final_config import FinalEvaluationConfig
from tcc_crypto.modeling.metrics import calculate_classification_metrics
from tcc_crypto.modeling.preprocessing import prepare_window
from tcc_crypto.modeling.ranking import PARAMETER_COLUMNS

MODELS = ("tuned_svc", "default_svc", "always_negative", "training_class_frequency")


@dataclass(frozen=True)
class FinalEvaluationResult:
    eligibility: pd.DataFrame
    predictions: pd.DataFrame
    metrics: pd.DataFrame
    roc: pd.DataFrame
    precision_recall: pd.DataFrame
    selected_configurations: pd.DataFrame


def freeze_configurations(
    selected: pd.DataFrame,
    eligibility: pd.DataFrame,
    symbol: str,
    config: DailySvmGridSearchConfig,
) -> pd.DataFrame:
    """Resolve selected candidate IDs against the original grid, never test scores."""
    candidates = expand_parameter_grid(config.parameter_grid)
    frozen = selected.copy()
    allowed = set(
        eligibility.loc[
            eligibility.status.eq("eligible"), ["target", "window_size"]
        ].itertuples(index=False, name=None)
    )
    if symbol in config.excluded_symbols:
        allowed = set()
    if selected.empty:
        if allowed:
            raise ValueError(
                "Eligible development searches have no selected configurations."
            )
        return frozen
    if selected.duplicated(["target", "window_size"]).any():
        raise ValueError("Frozen configurations must be unique per target and window.")
    actual = set(selected[["target", "window_size"]].itertuples(index=False, name=None))
    if actual != allowed or not selected.symbol.eq(symbol).all():
        raise ValueError(
            "Selected configurations do not match development eligibility."
        )
    parameters = []
    for row in selected.itertuples(index=False):
        order = int(row.candidate_order)
        if order != row.candidate_order or not 0 <= order < len(candidates):
            raise ValueError("Selected candidate order is outside the approved grid.")
        if (
            row.selection_rank != 1
            or row.failed_fold_count != 0
            or row.successful_fold_count != config.n_splits
        ):
            raise ValueError(
                "Selected candidate did not complete all development folds."
            )
        values = candidates[order]
        for name in PARAMETER_COLUMNS:
            actual_value = getattr(row, name)
            expected = values.get(name)
            if expected is None:
                same = actual_value is None or pd.isna(actual_value)
            else:
                same = pd.notna(actual_value) and actual_value == expected
            if not same:
                raise ValueError(
                    f"Selected {name} differs from the approved candidate."
                )
        parameters.append(json.dumps(values, sort_keys=True))
    frozen["frozen_parameters"] = parameters
    return frozen


def run_final_evaluation(
    dataset: pd.DataFrame,
    *,
    symbol: str,
    selected: pd.DataFrame,
    eligibility: pd.DataFrame,
    grid_config: DailySvmGridSearchConfig,
    config: FinalEvaluationConfig,
    selection_config: DailyFeatureSelectionConfig,
    feature_columns: Sequence[str] = ACTIVE_FEATURES,
) -> FinalEvaluationResult:
    """Use past windows only; share identical target-independent preprocessing.

    One selector/scaler is refitted for each date/window. The same fitted transform
    serves target-specific estimators using exactly that training feature matrix.
    The immediately preceding observation is excluded before each prediction.
    """
    if (
        config.gap != grid_config.gap
        or config.feature_start_utc
        <= grid_config.development_end_utc + pd.Timedelta(days=1)
    ):
        raise ValueError(
            "Final evaluation must follow development and its boundary gap."
        )
    if (
        config.single_class_training_policy != "record_no_prediction"
        or config.comparison_observations != "common_successful_dates"
    ):
        raise ValueError("Unsupported final omission/comparison policy.")
    feature_columns = tuple(feature_columns)
    if any(
        name.startswith(("target_", "next_day_")) or name == "feature_is_imputed"
        for name in feature_columns
    ):
        raise ValueError(
            "Future outcomes and imputation audit fields cannot enter features."
        )
    data = dataset.loc[: config.feature_end_utc].copy()
    _validate_numeric_feature_frame(data.loc[:, feature_columns])
    if not data.index.to_series().diff().dropna().eq(pd.Timedelta(days=1)).all():
        raise ValueError(
            "Final input must have a complete daily calendar after warm-up."
        )
    if not data.target_date_utc.eq(data.index + pd.Timedelta(days=1)).all():
        raise ValueError("Final input targets must refer to the next UTC day.")
    frozen = freeze_configurations(selected, eligibility, symbol, grid_config)
    final_eligibility = eligibility.copy()
    final_eligibility["final_test_eligibility_status"] = (
        "no_eligible_development_configuration"
    )
    final_eligibility["first_permitted_final_test_feature_utc"] = pd.Series(
        pd.NaT, index=final_eligibility.index, dtype="datetime64[ns, UTC]"
    )
    final_eligibility["last_permitted_final_test_feature_utc"] = pd.Series(
        pd.NaT, index=final_eligibility.index, dtype="datetime64[ns, UTC]"
    )
    rows = []
    for window_size, configurations in (
        frozen.groupby("window_size") if not frozen.empty else ()
    ):
        window_size = int(window_size)
        for position, date in enumerate(data.index):
            if not config.feature_start_utc <= date <= config.feature_end_utc:
                continue
            stop = position - config.gap
            start = stop - window_size
            training = data.iloc[max(start, 0) : max(stop, 0)]
            evaluation = data.iloc[[position]]
            prepared = None
            preprocessing_error = None
            for choice in configurations.itertuples(index=False):
                target = str(choice.target)
                labels = training[target]
                base = {
                    "symbol": symbol,
                    "target": target,
                    "window_size": window_size,
                    "feature_date_utc": date,
                    "target_date_utc": evaluation.target_date_utc.iloc[0],
                    "training_start_utc": training.index.min(),
                    "training_end_utc": training.index.max(),
                    "training_target_end_utc": training.target_date_utc.max(),
                    "gap_date_utc": data.index[position - 1] if position else pd.NaT,
                    "training_rows": len(training),
                    "training_negative": int(labels.eq(0).sum()),
                    "training_positive": int(labels.eq(1).sum()),
                    "actual": evaluation[target].iloc[0],
                    "candidate_order": int(choice.candidate_order),
                    "selected_features": "",
                    "selected_feature_count": 0,
                    "scaler_mean": "",
                    "scaler_scale": "",
                    "variance_fallback_feature": "",
                    "frozen_parameters": choice.frozen_parameters,
                    "feature_is_imputed": bool(evaluation.feature_is_imputed.iloc[0]),
                    "target_is_imputed": bool(evaluation.target_is_imputed.iloc[0]),
                }
                reason = ""
                if start < 0 or len(training) != window_size:
                    reason = "insufficient_trailing_history"
                elif labels.isna().any():
                    reason = "missing_training_labels"
                elif pd.isna(base["actual"]):
                    reason = "unlabeled_evaluation"
                elif labels.nunique() < 2:
                    reason = "single_class_training"
                if not reason and prepared is None and preprocessing_error is None:
                    try:
                        prepared = prepare_window(
                            training.loc[:, feature_columns],
                            evaluation.loc[:, feature_columns],
                            selection_config,
                        )
                    except (ValueError, RuntimeError) as error:
                        preprocessing_error = str(error)
                if not reason and preprocessing_error is not None:
                    reason = "preprocessing_failed"
                if prepared is not None:
                    base.update(
                        selected_features="|".join(
                            prepared.selector.selected_features_
                        ),
                        selected_feature_count=len(
                            prepared.selector.selected_features_
                        ),
                        scaler_mean=json.dumps(prepared.scaler.mean_.tolist()),
                        scaler_scale=json.dumps(prepared.scaler.scale_.tolist()),
                        variance_fallback_feature=prepared.selector.variance_fallback_feature_
                        or "",
                    )
                for model in MODELS:
                    row = {
                        **base,
                        "model": model,
                        "status": reason or "ok",
                        "error": preprocessing_error or "",
                        "prediction": pd.NA,
                        "decision_score": float("nan"),
                        "fit_seconds": 0.0,
                    }
                    if not reason:
                        started = perf_counter()
                        try:
                            estimator = {
                                "tuned_svc": lambda: SVC(
                                    **json.loads(choice.frozen_parameters)
                                ),
                                "default_svc": SVC,
                                "always_negative": lambda: DummyClassifier(
                                    strategy="constant", constant=0
                                ),
                                "training_class_frequency": lambda: DummyClassifier(
                                    strategy="prior"
                                ),
                            }[model]()
                            estimator.fit(prepared.training, labels.astype("int64"))
                            row["prediction"] = int(
                                estimator.predict(prepared.evaluation)[0]
                            )
                            if model.endswith("svc"):
                                row["decision_score"] = float(
                                    estimator.decision_function(prepared.evaluation)[0]
                                )
                            else:
                                positive = int(
                                    np.flatnonzero(estimator.classes_ == 1)[0]
                                )
                                row["decision_score"] = float(
                                    estimator.predict_proba(prepared.evaluation)[
                                        0, positive
                                    ]
                                )
                        except (ValueError, RuntimeError) as error:
                            row.update(
                                status="fit_failed",
                                error=str(error),
                                prediction=pd.NA,
                                decision_score=float("nan"),
                            )
                        row["fit_seconds"] = perf_counter() - started
                    rows.append(row)
    predictions = pd.DataFrame(rows)
    if not predictions.empty:
        predictions["prediction"] = predictions.prediction.astype("Int8")
        predictions["actual"] = predictions.actual.astype("Int8")
        keys = ["target", "window_size", "feature_date_utc"]
        common = predictions.groupby(keys).status.transform(
            lambda statuses: len(statuses) == len(MODELS) and statuses.eq("ok").all()
        )
        predictions["comparison_eligible"] = common.astype("boolean")
        for (target, window), group in predictions.groupby(["target", "window_size"]):
            good = group.loc[group.comparison_eligible, "feature_date_utc"]
            match = final_eligibility.target.eq(
                target
            ) & final_eligibility.window_size.eq(window)
            final_eligibility.loc[match, "final_test_eligibility_status"] = (
                "eligible" if not good.empty else "no_common_successful_dates"
            )
            final_eligibility.loc[match, "first_permitted_final_test_feature_utc"] = (
                good.min()
            )
            final_eligibility.loc[match, "last_permitted_final_test_feature_utc"] = (
                good.max()
            )
    else:
        predictions = pd.DataFrame(
            columns=[
                "symbol",
                "target",
                "window_size",
                "model",
                "feature_date_utc",
                "target_date_utc",
                "actual",
                "prediction",
                "decision_score",
                "status",
                "comparison_eligible",
            ]
        )
    metrics, roc, pr = summarize_final_predictions(predictions)
    return FinalEvaluationResult(
        final_eligibility, predictions, metrics, roc, pr, frozen
    )


def summarize_final_predictions(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compute metrics and curves on identical successful dates for all models."""
    metrics, roc_rows, pr_rows = [], [], []
    for keys, group in predictions.groupby(
        ["symbol", "target", "window_size", "model"], sort=False
    ):
        identifiers = dict(
            zip(("symbol", "target", "window_size", "model"), keys, strict=True)
        )
        valid = group.loc[group.comparison_eligible.fillna(False)]
        row = {
            **identifiers,
            "attempted_dates": len(group),
            "evaluated_dates": len(valid),
            "omitted_dates": len(group) - len(valid),
            "single_class_training_dates": int(
                group.status.eq("single_class_training").sum()
            ),
            "fit_failure_dates": int(
                group.status.isin(["fit_failed", "preprocessing_failed"]).sum()
            ),
            "evaluation_start_utc": valid.feature_date_utc.min(),
            "evaluation_end_utc": valid.feature_date_utc.max(),
        }
        if valid.empty:
            row.update(metric_diagnostic="no_common_successful_dates")
        else:
            y = valid.actual.astype("int64")
            predicted = valid.prediction.astype("int64")
            scores = valid.decision_score.astype("float64")
            row.update(calculate_classification_metrics(y, predicted, scores))
            row["metric_diagnostic"] = str(row["metric_diagnostic"]).replace(
                "single_class_validation", "single_class_evaluation"
            )
            tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
            row.update(
                true_negative=int(tn),
                false_positive=int(fp),
                false_negative=int(fn),
                true_positive=int(tp),
                actual_positive=int(y.sum()),
                actual_negative=int(y.eq(0).sum()),
                predicted_positive=int(predicted.sum()),
                predicted_negative=int(predicted.eq(0).sum()),
            )
            if y.nunique() == 2:
                fpr, tpr, thresholds = roc_curve(y, scores)
                roc_rows.extend(
                    {
                        **identifiers,
                        "false_positive_rate": float(x),
                        "true_positive_rate": float(z),
                        "threshold": float(t),
                    }
                    for x, z, t in zip(fpr, tpr, thresholds, strict=True)
                )
                precision, recall, thresholds = precision_recall_curve(y, scores)
                pr_rows.extend(
                    {
                        **identifiers,
                        "precision": float(p),
                        "recall": float(r),
                        "threshold": float(thresholds[i])
                        if i < len(thresholds)
                        else float("nan"),
                    }
                    for i, (p, r) in enumerate(zip(precision, recall, strict=True))
                )
        metrics.append(row)
    names = ["symbol", "target", "window_size", "model"]
    return (
        pd.DataFrame(metrics)
        if metrics
        else pd.DataFrame(
            columns=names
            + [
                "attempted_dates",
                "evaluated_dates",
                "omitted_dates",
                "metric_diagnostic",
            ]
        ),
        pd.DataFrame(
            roc_rows,
            columns=names + ["false_positive_rate", "true_positive_rate", "threshold"],
        ),
        pd.DataFrame(pr_rows, columns=names + ["precision", "recall", "threshold"]),
    )
