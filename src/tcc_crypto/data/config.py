"""Data: config."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tcc_crypto.data.time import _parse_utc_day as _parse_utc_day
from tcc_crypto.paths import RAW_DAILY_DIR, SVM_PILOT_RESULTS_DIR


@dataclass(frozen=True)
class DailyModelingDatasetConfig:
    """Validated settings for the approved single-asset pilot dataset."""

    dataset_id: str
    feature_config: Path
    symbol: str
    raw_directory: Path
    warmup_start_utc: pd.Timestamp
    sample_start_utc: pd.Timestamp
    sample_end_utc: pd.Timestamp
    target_offset_days: int
    target_source: str
    target_thresholds: tuple[float, ...]
    missing_data_policy: str
    training_window_sizes: tuple[int, ...]
    estimator: str
    estimator_parameters: str
    scaler: str
    scaling_fit_scope: str
    scaling_refit_frequency: str
    scaling_pipeline_position: str
    evaluation_metrics: tuple[str, ...]
    model_training_status: str
    output_directory: Path


def load_daily_modeling_dataset_config(path: Path) -> DailyModelingDatasetConfig:
    """Load and validate the approved pilot dataset configuration."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)

    warmup_start = _parse_utc_day(payload["warmup_start_utc"], "warmup_start_utc")
    sample_start = _parse_utc_day(payload["sample_start_utc"], "sample_start_utc")
    sample_end = _parse_utc_day(payload["sample_end_utc"], "sample_end_utc")
    if not warmup_start < sample_start <= sample_end:
        raise ValueError(
            "Expected warmup_start_utc < sample_start_utc <= sample_end_utc."
        )

    thresholds = tuple(float(value) for value in payload["target_thresholds"])
    if thresholds != (0.02, 0.03, 0.04):
        raise ValueError("Approved target thresholds are 0.02, 0.03, and 0.04.")
    if int(payload["target_offset_days"]) != 1:
        raise ValueError("The approved target offset is one day.")
    if payload["target_source"] != "next_day_d0":
        raise ValueError("The approved target source is next_day_d0.")
    if payload["missing_data_policy"] != "forward_fill_internal":
        raise ValueError("The approved missing-data policy is forward_fill_internal.")
    training_window_sizes = tuple(
        int(value) for value in payload["training_window_sizes"]
    )
    if training_window_sizes != (60, 75, 90):
        raise ValueError("Approved training windows are 60, 75, and 90 days.")
    if payload["estimator"] != "sklearn.svm.SVC":
        raise ValueError("The approved pilot estimator is sklearn.svm.SVC.")
    if payload["estimator_parameters"] != "defaults":
        raise ValueError("The initial pilot must use default SVC parameters.")
    scaling = payload["scaling"]
    if scaling["transformer"] != "sklearn.preprocessing.StandardScaler":
        raise ValueError("The approved pilot scaler is StandardScaler.")
    if scaling["fit_scope"] != "training_only":
        raise ValueError("StandardScaler must be fitted on training data only.")
    if scaling["refit_frequency"] != "every_prediction":
        raise ValueError("StandardScaler must be refitted for every prediction.")
    if scaling["pipeline_position"] != "after_feature_selection":
        raise ValueError("StandardScaler must run after feature selection.")
    metrics = tuple(str(value) for value in payload["evaluation_metrics"])
    if metrics != ("accuracy", "precision", "recall", "f1"):
        raise ValueError(
            "Configured pilot metrics are accuracy, precision, recall, and f1."
        )
    if payload["model_training_status"] != "approved_default_pilot":
        raise ValueError("The default SVC pilot must be approved for training.")

    return DailyModelingDatasetConfig(
        dataset_id=str(payload["dataset_id"]),
        feature_config=Path(payload["feature_config"]),
        symbol=str(payload["symbol"]),
        raw_directory=Path(payload.get("raw_directory", RAW_DAILY_DIR)),
        warmup_start_utc=warmup_start,
        sample_start_utc=sample_start,
        sample_end_utc=sample_end,
        target_offset_days=1,
        target_source="next_day_d0",
        target_thresholds=thresholds,
        missing_data_policy="forward_fill_internal",
        training_window_sizes=training_window_sizes,
        estimator="sklearn.svm.SVC",
        estimator_parameters="defaults",
        scaler="sklearn.preprocessing.StandardScaler",
        scaling_fit_scope="training_only",
        scaling_refit_frequency="every_prediction",
        scaling_pipeline_position="after_feature_selection",
        evaluation_metrics=metrics,
        model_training_status="approved_default_pilot",
        output_directory=Path(
            payload.get(
                "output_directory", SVM_PILOT_RESULTS_DIR / str(payload["dataset_id"])
            )
        ),
    )
