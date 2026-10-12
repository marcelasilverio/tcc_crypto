"""Run the approved rolling default-SVC pilot without temporal leakage."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Sequence

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from tcc_crypto.daily_feature_selection import DailyFeatureSelector
from tcc_crypto.daily_features import ACTIVE_FEATURES, DailyFeatureSelectionConfig
from tcc_crypto.daily_modeling_dataset import DailyModelingDatasetConfig


@dataclass(frozen=True)
class DailySvmPilotResult:
    """Per-step predictions and grouped pilot diagnostics."""

    predictions: pd.DataFrame
    summary: pd.DataFrame


def _binary_metrics(y_true: Sequence[int], y_pred: Sequence[int]) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def _validate_pilot_dataset(
    dataset: pd.DataFrame,
    feature_columns: Sequence[str],
    target_columns: Sequence[str],
) -> None:
    required = {*feature_columns, *target_columns}
    missing = required.difference(dataset.columns)
    if missing:
        raise ValueError(f"Pilot dataset is missing columns: {sorted(missing)}.")
    if dataset.empty:
        raise ValueError("Pilot dataset contains no observations.")
    if not isinstance(dataset.index, pd.DatetimeIndex):
        raise TypeError("Pilot dataset must use a DatetimeIndex.")
    if dataset.index.tz is None or str(dataset.index.tz) != "UTC":
        raise ValueError("Pilot dataset timestamps must use UTC.")
    if dataset.index.has_duplicates or not dataset.index.is_monotonic_increasing:
        raise ValueError("Pilot dataset timestamps must be unique and chronological.")
    if dataset.loc[:, feature_columns].isna().any().any():
        raise ValueError("Pilot feature values must be complete.")
    if dataset.loc[:, target_columns].isna().any().any():
        raise ValueError("Pilot target values must be complete.")


def run_default_svc_rolling_pilot(
    dataset: pd.DataFrame,
    *,
    selection_config: DailyFeatureSelectionConfig,
    feature_columns: Sequence[str] = ACTIVE_FEATURES,
    target_columns: Sequence[str] = ("target_2pct", "target_3pct", "target_4pct"),
) -> DailySvmPilotResult:
    """Fit selectors, StandardScaler, and default SVC in rolling windows.

    At every step, feature selection and scaling are refitted on the trailing
    training window only. The immediately following row is transformed by the
    fitted objects and is never used for fitting.
    """
    feature_columns = tuple(str(column) for column in feature_columns)
    target_columns = tuple(str(column) for column in target_columns)
    _validate_pilot_dataset(dataset, feature_columns, target_columns)

    features = dataset.loc[:, feature_columns].astype("float64")
    rows: list[dict[str, object]] = []
    for target_column in target_columns:
        labels = dataset[target_column].astype("int64")
        for window_size in selection_config.training_window_sizes:
            if window_size < 2:
                raise ValueError("Training windows must contain at least two rows.")
            for prediction_position in range(window_size, len(dataset)):
                training_slice = slice(
                    prediction_position - window_size, prediction_position
                )
                training_features = features.iloc[training_slice]
                prediction_features = features.iloc[
                    prediction_position : prediction_position + 1
                ]
                training_labels = labels.iloc[training_slice]
                actual = int(labels.iloc[prediction_position])

                selector = DailyFeatureSelector(
                    variance_threshold=selection_config.variance_threshold,
                    correlation_threshold=selection_config.correlation_threshold,
                )
                selected_training = selector.fit_transform(training_features)
                selected_prediction = selector.transform(prediction_features)
                scaler = StandardScaler()
                scaled_training = scaler.fit_transform(selected_training)
                scaled_prediction = scaler.transform(selected_prediction)

                row: dict[str, object] = {
                    "target": target_column,
                    "window_size": window_size,
                    "training_start_utc": training_features.index[0],
                    "training_end_utc": training_features.index[-1],
                    "prediction_time_utc": prediction_features.index[0],
                    "actual": actual,
                    "training_negative": int((training_labels == 0).sum()),
                    "training_positive": int((training_labels == 1).sum()),
                    "selected_feature_count": len(selector.selected_features_),
                    "selected_features": "|".join(selector.selected_features_),
                }
                if training_labels.nunique() < 2:
                    row.update(
                        {
                            "status": "single_class_training",
                            "prediction": pd.NA,
                            "decision_score": float("nan"),
                            "in_sample_accuracy": float("nan"),
                            "in_sample_precision": float("nan"),
                            "in_sample_recall": float("nan"),
                            "in_sample_f1": float("nan"),
                        }
                    )
                    rows.append(row)
                    continue

                estimator = SVC()
                estimator.fit(scaled_training, training_labels)
                in_sample_prediction = estimator.predict(scaled_training)
                in_sample_metrics = _binary_metrics(
                    training_labels.to_numpy(), in_sample_prediction
                )
                prediction = int(estimator.predict(scaled_prediction)[0])
                decision_score = float(
                    estimator.decision_function(scaled_prediction)[0]
                )
                row.update(
                    {
                        "status": "ok",
                        "prediction": prediction,
                        "decision_score": decision_score,
                        "in_sample_accuracy": in_sample_metrics["accuracy"],
                        "in_sample_precision": in_sample_metrics["precision"],
                        "in_sample_recall": in_sample_metrics["recall"],
                        "in_sample_f1": in_sample_metrics["f1"],
                    }
                )
                rows.append(row)

    predictions = pd.DataFrame(rows)
    summary_rows: list[dict[str, object]] = []
    for (target, window_size), group in predictions.groupby(
        ["target", "window_size"], sort=True
    ):
        successful = group.loc[group["status"] == "ok"].copy()
        summary_row: dict[str, object] = {
            "target": target,
            "window_size": int(window_size),
            "prediction_count": len(group),
            "successful_prediction_count": len(successful),
            "single_class_count": int(
                (group["status"] == "single_class_training").sum()
            ),
        }
        if successful.empty:
            summary_row.update(
                {
                    "out_of_sample_accuracy": float("nan"),
                    "out_of_sample_precision": float("nan"),
                    "out_of_sample_recall": float("nan"),
                    "out_of_sample_f1": float("nan"),
                    "true_negative": 0,
                    "false_positive": 0,
                    "false_negative": 0,
                    "true_positive": 0,
                }
            )
        else:
            actual = successful["actual"].astype("int64")
            predicted = successful["prediction"].astype("int64")
            out_metrics = _binary_metrics(actual, predicted)
            true_negative, false_positive, false_negative, true_positive = (
                confusion_matrix(actual, predicted, labels=[0, 1]).ravel()
            )
            summary_row.update(
                {
                    "out_of_sample_accuracy": out_metrics["accuracy"],
                    "out_of_sample_precision": out_metrics["precision"],
                    "out_of_sample_recall": out_metrics["recall"],
                    "out_of_sample_f1": out_metrics["f1"],
                    "true_negative": int(true_negative),
                    "false_positive": int(false_positive),
                    "false_negative": int(false_negative),
                    "true_positive": int(true_positive),
                }
            )
        for metric in ("accuracy", "precision", "recall", "f1"):
            summary_row[f"mean_in_sample_{metric}"] = float(
                successful[f"in_sample_{metric}"].mean()
            )
        summary_rows.append(summary_row)

    return DailySvmPilotResult(
        predictions=predictions,
        summary=pd.DataFrame(summary_rows),
    )


def _package_version(distribution: str) -> str | None:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def _git_revision() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _git_working_tree_dirty() -> bool | None:
    completed = subprocess.run(
        ["git", "status", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return bool(completed.stdout.strip())


def write_daily_svm_pilot_results(
    config: DailyModelingDatasetConfig,
    result: DailySvmPilotResult,
) -> tuple[Path, Path, Path]:
    """Persist pilot predictions, summaries, and reproducibility metadata."""
    output_directory = config.output_directory / "default_svc"
    output_directory.mkdir(parents=True, exist_ok=True)
    predictions_path = output_directory / "rolling_predictions.csv"
    summary_path = output_directory / "metrics_summary.csv"
    metadata_path = output_directory / "run_metadata.json"
    result.predictions.to_csv(predictions_path, index=False)
    result.summary.to_csv(summary_path, index=False)
    metadata = {
        "dataset_id": config.dataset_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": _git_revision(),
        "working_tree_dirty": _git_working_tree_dirty(),
        "symbol": config.symbol,
        "sample_start_utc": config.sample_start_utc.isoformat(),
        "sample_end_utc": config.sample_end_utc.isoformat(),
        "training_window_sizes": list(config.training_window_sizes),
        "target_thresholds": list(config.target_thresholds),
        "target_alignment": "features(t) -> D0(t+1)",
        "estimator": config.estimator,
        "estimator_parameters": SVC().get_params(deep=False),
        "scaler": config.scaler,
        "scaler_parameters": StandardScaler().get_params(deep=False),
        "scaling_fit_scope": config.scaling_fit_scope,
        "scaling_refit_frequency": config.scaling_refit_frequency,
        "scaling_pipeline_position": config.scaling_pipeline_position,
        "evaluation_metrics": list(config.evaluation_metrics),
        "prediction_rows": len(result.predictions),
        "summary_rows": len(result.summary),
        "package_versions": {
            distribution: _package_version(distribution)
            for distribution in (
                "pandas",
                "numpy",
                "scikit-learn",
                "feature-engine",
            )
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return predictions_path, summary_path, metadata_path
