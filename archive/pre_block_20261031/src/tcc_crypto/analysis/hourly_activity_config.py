"""Configuration for hourly_activity."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tcc_crypto.analysis.hourly_activity import ACTIVITY_FIELDS
from tcc_crypto.collection.config import CollectionConfig, load_collection_config
from tcc_crypto.paths import analysis_output_directory, reject_legacy_analysis_paths


@dataclass(frozen=True)
class MarketActivityAnalysisConfig:
    """Validated settings for the hourly market-activity analysis."""

    analysis_id: str
    collection_config_path: Path
    activity_fields: tuple[str, ...]
    quantiles: tuple[float, ...]
    standard_deviation_ddof: int
    kurtosis_definition: str
    output_directory: Path


def load_market_activity_config(
    path: Path,
    *,
    repository_root: Path,
) -> tuple[MarketActivityAnalysisConfig, CollectionConfig]:
    """Load activity-analysis settings and the collection they reference."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)
    reject_legacy_analysis_paths(payload)

    activity_fields = tuple(str(field) for field in payload["activity_fields"])
    if activity_fields != ACTIVITY_FIELDS:
        raise ValueError(
            "activity_fields must contain the five canonical Binance activity fields "
            "in their approved order."
        )
    quantiles = tuple(float(value) for value in payload["quantiles"])
    if quantiles != (0.25, 0.5, 0.75):
        raise ValueError("This analysis requires quartiles 0.25, 0.50, and 0.75.")
    ddof = int(payload["standard_deviation_ddof"])
    if ddof != 1:
        raise ValueError("The descriptive analysis uses sample variance (ddof=1).")

    collection_config_path = repository_root / str(payload["collection_config"])
    collection_config = load_collection_config(collection_config_path)
    config = MarketActivityAnalysisConfig(
        analysis_id=str(payload["analysis_id"]),
        collection_config_path=collection_config_path,
        activity_fields=activity_fields,
        quantiles=quantiles,
        standard_deviation_ddof=ddof,
        kurtosis_definition=str(payload["kurtosis_definition"]),
        output_directory=analysis_output_directory(
            repository_root, "hourly-activity", str(payload["analysis_id"])
        ),
    )
    return config, collection_config
