"""Adapt existing experiment JSONs to explicit data and artifact contexts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

import pandas as pd

from tcc_crypto.data.config import (
    DailyModelingDatasetConfig,
    load_daily_modeling_dataset_config,
)
from tcc_crypto.data.dataset import DailyDataConfig
from tcc_crypto.features.config import DailyFeatureConfig, load_daily_feature_config
from tcc_crypto.modeling.config import (
    DailySvmGridSearchConfig,
    load_daily_svm_grid_search_config,
)
from tcc_crypto.paths import (
    GRID_CONFIG_PATH,
    PILOT_CONFIG_PATH,
    ArtifactPaths,
    repository_root,
    resolve_path,
)
from tcc_crypto.reporting.provenance import file_sha256


@dataclass(frozen=True)
class DailyContext:
    root: Path
    profile: Literal["pilot", "development"]
    data: DailyDataConfig
    paths: ArtifactPaths
    features: DailyFeatureConfig
    model: DailyModelingDatasetConfig | DailySvmGridSearchConfig
    configuration_files: tuple[Path, ...]

    @property
    def kind(self) -> str:
        return "pilot" if self.profile == "pilot" else "grid-search"

    def signature(self) -> dict[str, object]:
        """Include scientific settings and referenced file hashes, not execution time."""
        value = {
            "profile": self.profile,
            "data": asdict(self.data),
            "features": asdict(self.features),
            "model": asdict(self.model),
            "configuration_sha256": {
                str(p): file_sha256(p) for p in self.configuration_files
            },
        }
        return json.loads(json.dumps(value, default=str))


def load_context(
    profile: str = "development",
    *,
    config_path: Path | None = None,
    symbol: str | None = None,
    root: Path | None = None,
) -> DailyContext:
    root = repository_root(root)
    if profile not in ("pilot", "development"):
        raise ValueError("Profile must be pilot or development.")
    path = resolve_path(
        root,
        config_path or (PILOT_CONFIG_PATH if profile == "pilot" else GRID_CONFIG_PATH),
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if profile == "pilot":
        model = load_daily_modeling_dataset_config(path)
        symbol = symbol or model.symbol
        if symbol != model.symbol:
            raise ValueError(f"The pilot configuration only permits {model.symbol}.")
        data = DailyDataConfig(
            model.dataset_id,
            symbol,
            model.warmup_start_utc,
            model.sample_start_utc,
            model.sample_end_utc,
            True,
            model.target_thresholds,
        )
    else:
        model = load_daily_svm_grid_search_config(path, repository_root=root)
        symbol = symbol or "BTCUSDT"
        if symbol not in model.candidate_symbols:
            raise ValueError(f"{symbol} is not in the configured candidate universe.")
        data = DailyDataConfig(
            model.experiment_id,
            symbol,
            model.development_start_utc - pd.Timedelta(days=30),
            model.development_start_utc,
            model.development_end_utc,
        )
    feature_path = resolve_path(root, model.feature_config)
    features = load_daily_feature_config(feature_path)
    collection_path = resolve_path(root, features.collection_config)
    feature_payload = json.loads(feature_path.read_text(encoding="utf-8"))
    model = replace(
        model,
        raw_directory=resolve_path(root, model.raw_directory),
        feature_config=feature_path,
        output_directory=resolve_path(root, model.output_directory),
    )
    paths = ArtifactPaths(
        root,
        data.context_id,
        symbol,
        model.raw_directory,
        Path(payload["output_directory"]) if "output_directory" in payload else None,
        Path(feature_payload["feature_output_directory"])
        if "feature_output_directory" in feature_payload
        else None,
    )
    return DailyContext(
        root,
        profile,
        data,
        paths,
        features,
        model,
        (path, feature_path, collection_path),
    )
