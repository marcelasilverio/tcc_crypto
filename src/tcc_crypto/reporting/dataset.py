"""Reporting: dataset."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pandas as pd

from tcc_crypto.data.config import DailyModelingDatasetConfig
from tcc_crypto.reporting.provenance import (
    _git_revision,
    _git_working_tree_dirty,
    _package_version,
)
from tcc_crypto.workflows.datasets import modeling_feature_columns


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
