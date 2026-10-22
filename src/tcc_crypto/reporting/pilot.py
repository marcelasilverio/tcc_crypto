"""Reporting: pilot."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from tcc_crypto.data.config import DailyModelingDatasetConfig
from tcc_crypto.modeling.pilot import DailySvmPilotResult
from tcc_crypto.paths import PILOT_TABLE_NAMES, RUN_METADATA_NAME
from tcc_crypto.reporting.provenance import (
    _git_revision,
    _git_working_tree_dirty,
    _package_version,
)


def write_daily_svm_pilot_results(
    config: DailyModelingDatasetConfig,
    result: DailySvmPilotResult,
) -> tuple[Path, Path, Path]:
    """Persist pilot predictions, summaries, and reproducibility metadata."""
    output_directory = config.output_directory / "default_svc"
    output_directory.mkdir(parents=True, exist_ok=True)
    predictions_path = output_directory / PILOT_TABLE_NAMES["predictions"]
    summary_path = output_directory / PILOT_TABLE_NAMES["summary"]
    metadata_path = output_directory / RUN_METADATA_NAME
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
