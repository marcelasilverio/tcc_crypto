"""Reporting: grid search."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from tcc_crypto.data.development import SymbolDevelopmentDataset
from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.modeling.config import DailySvmGridSearchConfig, _load_json
from tcc_crypto.modeling.grid_search import DailySvmGridSearchResult
from tcc_crypto.paths import (
    CONFIGURATION_SNAPSHOT_NAME,
    GRID_TABLE_NAMES,
    RUN_METADATA_NAME,
)
from tcc_crypto.reporting.provenance import _package_version, file_sha256, git_value
from tcc_crypto.targets.daily import DAY


def _git_value(arguments: Sequence[str]) -> str | None:
    return git_value(tuple(arguments)) or None


def _write_csv(frame: pd.DataFrame, path: Path) -> str:
    frame.to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    return file_sha256(path)


def write_grid_search_outputs(
    config: DailySvmGridSearchConfig,
    source: SymbolDevelopmentDataset,
    result: DailySvmGridSearchResult,
) -> tuple[Path, ...]:
    """Persist grid evidence and a reproducibility manifest outside Git."""
    output_directory = config.output_directory / source.symbol
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = {
        name: output_directory / filename for name, filename in GRID_TABLE_NAMES.items()
    }
    checksums = {
        name: _write_csv(getattr(result, name), path) for name, path in paths.items()
    }
    snapshot_path = output_directory / CONFIGURATION_SNAPSHOT_NAME
    snapshot_path.write_text(
        json.dumps(_load_json(config.config_path), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksums["configuration_snapshot"] = file_sha256(snapshot_path)
    metadata_path = output_directory / RUN_METADATA_NAME
    metadata = {
        "experiment_id": config.experiment_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": _git_value(("rev-parse", "HEAD")),
        "working_tree_dirty": bool(_git_value(("status", "--porcelain"))),
        "configuration": str(config.config_path),
        "configuration_sha256": file_sha256(config.config_path),
        "symbol": source.symbol,
        "raw_data_path": str(source.raw_path),
        "raw_data_sha256": source.raw_sha256,
        "development_start_utc": config.development_start_utc.isoformat(),
        "development_end_utc": config.development_end_utc.isoformat(),
        "latest_source_observation_used_utc": (
            config.development_end_utc + DAY
        ).isoformat(),
        "final_test_feature_rows_used": False,
        "random_behavior": False,
        "random_seed": None,
        "candidate_count_per_search": config.candidate_count,
        "eligible_search_count": int(
            (result.eligibility["status"] == "eligible").sum()
        ),
        "fold_result_count": len(result.fold_results),
        "selected_configuration_count": len(result.selected_configurations),
        "input_features": list(ACTIVE_FEATURES),
        "scaler_parameters": StandardScaler().get_params(deep=False),
        "svc_default_parameters": SVC().get_params(deep=False),
        "artifact_sha256": checksums,
        "package_versions": {
            distribution: _package_version(distribution)
            for distribution in (
                "pandas",
                "numpy",
                "scikit-learn",
                "feature-engine",
                "TA-Lib",
            )
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return (*paths.values(), snapshot_path, metadata_path)
