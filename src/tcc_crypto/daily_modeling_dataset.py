"""Build leakage-safe daily features and next-day D0 binary targets."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pandas as pd

from tcc_crypto.daily_feature_selection import remove_leading_feature_warmup
from tcc_crypto.daily_features import (
    ACTIVE_FEATURES,
    calculate_daily_features,
    load_daily_feature_input,
)
from tcc_crypto.daily_future_high_returns import find_symbol_csv

DAY = pd.Timedelta(1, unit="D")


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


def _parse_utc_day(value: object, field_name: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"{field_name} must include an explicit UTC offset.")
    timestamp = timestamp.tz_convert("UTC")
    if timestamp != timestamp.normalize():
        raise ValueError(f"{field_name} must be aligned to a UTC day.")
    return timestamp


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
        raw_directory=Path(payload["raw_directory"]),
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
        output_directory=Path(payload["output_directory"]),
    )


def build_next_day_d0_targets(
    daily_values: pd.DataFrame,
    feature_index: pd.DatetimeIndex,
    *,
    thresholds: tuple[float, ...] = (0.02, 0.03, 0.04),
) -> pd.DataFrame:
    """Align each feature date with the following day's same-day D0 outcome."""
    required = {"open", "high"}
    if not required.issubset(daily_values.columns):
        raise ValueError("daily_values must contain open and high columns.")
    if not isinstance(daily_values.index, pd.DatetimeIndex):
        raise TypeError("daily_values must use a DatetimeIndex.")
    if daily_values.index.tz is None or str(daily_values.index.tz) != "UTC":
        raise ValueError("daily_values timestamps must use UTC.")
    if not isinstance(feature_index, pd.DatetimeIndex):
        raise TypeError("feature_index must be a DatetimeIndex.")
    if feature_index.tz is None or str(feature_index.tz) != "UTC":
        raise ValueError("feature_index timestamps must use UTC.")
    if tuple(float(value) for value in thresholds) != (0.02, 0.03, 0.04):
        raise ValueError("Approved target thresholds are 0.02, 0.03, and 0.04.")

    target_dates = feature_index + DAY
    next_day_open = daily_values["open"].reindex(target_dates)
    next_day_high = daily_values["high"].reindex(target_dates)
    next_day_d0 = next_day_high.div(next_day_open).sub(1.0)
    next_day_d0.index = feature_index

    result = pd.DataFrame(index=feature_index)
    result.index.name = "feature_date_utc"
    result["target_date_utc"] = target_dates
    result["next_day_open"] = next_day_open.to_numpy()
    result["next_day_high"] = next_day_high.to_numpy()
    result["next_day_d0"] = next_day_d0

    if "is_imputed" in daily_values.columns:
        target_imputed = daily_values["is_imputed"].reindex(target_dates)
        target_imputed.index = feature_index
        result["target_is_imputed"] = target_imputed.astype("boolean")
    else:
        result["target_is_imputed"] = pd.Series(
            False, index=feature_index, dtype="boolean"
        )

    for threshold in thresholds:
        label = next_day_d0.ge(threshold).astype("Int8")
        label[next_day_d0.isna()] = pd.NA
        result[f"target_{int(round(threshold * 100))}pct"] = label
    return result


def build_daily_modeling_dataset(
    config: DailyModelingDatasetConfig,
) -> pd.DataFrame:
    """Build the configured pilot dataset without modifying immutable raw data."""
    raw_path = find_symbol_csv(config.raw_directory, config.symbol)
    aligned = load_daily_feature_input(raw_path, fill_internal_gaps=True)
    required_end = config.sample_end_utc + DAY
    calculation_values = aligned.loc[
        (aligned.index >= config.warmup_start_utc)
        & (aligned.index <= required_end)
    ].copy()
    if calculation_values.empty:
        raise ValueError("No daily values overlap the configured pilot period.")
    if calculation_values.index[0] != config.warmup_start_utc:
        raise ValueError("The configured warm-up start is not observed or aligned.")

    features = calculate_daily_features(calculation_values)
    complete_features = remove_leading_feature_warmup(features)
    sample_features = complete_features.loc[
        (complete_features.index >= config.sample_start_utc)
        & (complete_features.index <= config.sample_end_utc)
    ].copy()
    if sample_features.empty:
        raise ValueError("No complete feature rows overlap the configured sample.")

    targets = build_next_day_d0_targets(
        calculation_values,
        sample_features.index,
        thresholds=config.target_thresholds,
    )
    result = sample_features.join(targets)
    result.insert(0, "symbol", config.symbol)
    feature_imputed = calculation_values["is_imputed"].reindex(result.index)
    result.insert(1, "feature_is_imputed", feature_imputed.astype("boolean"))
    return result


def modeling_feature_columns() -> tuple[str, ...]:
    """Return the ordered feature columns used by the pilot dataset."""
    return ACTIVE_FEATURES


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


def write_daily_modeling_dataset(
    config: DailyModelingDatasetConfig,
    dataset: pd.DataFrame,
) -> tuple[Path, Path]:
    """Persist the generated dataset and reproducibility metadata."""
    if dataset.empty:
        raise ValueError("Cannot write an empty modeling dataset.")
    config.output_directory.mkdir(parents=True, exist_ok=True)
    csv_path = config.output_directory / f"{config.dataset_id}.csv"
    metadata_path = config.output_directory / f"{config.dataset_id}.metadata.json"
    dataset.to_csv(csv_path, index=True, date_format="%Y-%m-%dT%H:%M:%S%z")

    target_columns = [
        f"target_{int(round(threshold * 100))}pct"
        for threshold in config.target_thresholds
    ]
    target_summary = {
        column: {
            "labeled": int(dataset[column].notna().sum()),
            "positive": int(dataset[column].fillna(0).sum()),
            "negative": int((dataset[column] == 0).sum()),
        }
        for column in target_columns
    }
    metadata = {
        "dataset_id": config.dataset_id,
        "feature_config": str(config.feature_config),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": _git_revision(),
        "working_tree_dirty": _git_working_tree_dirty(),
        "symbol": config.symbol,
        "warmup_start_utc": config.warmup_start_utc.isoformat(),
        "sample_start_utc": config.sample_start_utc.isoformat(),
        "sample_end_utc": config.sample_end_utc.isoformat(),
        "target_offset_days": config.target_offset_days,
        "target_source": config.target_source,
        "target_thresholds": list(config.target_thresholds),
        "missing_data_policy": config.missing_data_policy,
        "training_window_sizes": list(config.training_window_sizes),
        "estimator": config.estimator,
        "estimator_parameters": config.estimator_parameters,
        "scaler": config.scaler,
        "scaling_fit_scope": config.scaling_fit_scope,
        "scaling_refit_frequency": config.scaling_refit_frequency,
        "scaling_pipeline_position": config.scaling_pipeline_position,
        "evaluation_metrics": list(config.evaluation_metrics),
        "model_training_status": config.model_training_status,
        "row_count": len(dataset),
        "feature_columns": list(modeling_feature_columns()),
        "feature_imputed_rows": int(dataset["feature_is_imputed"].sum()),
        "target_imputed_rows": int(dataset["target_is_imputed"].fillna(False).sum()),
        "target_summary": target_summary,
        "csv_sha256": sha256(csv_path.read_bytes()).hexdigest(),
        "package_versions": {
            distribution: _package_version(distribution)
            for distribution in (
                "pandas",
                "numpy",
                "TA-Lib",
                "scikit-learn",
                "feature-engine",
            )
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return csv_path, metadata_path
