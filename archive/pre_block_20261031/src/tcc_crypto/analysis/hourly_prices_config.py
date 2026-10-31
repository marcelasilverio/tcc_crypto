"""Configuration for hourly_prices."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tcc_crypto.collection.config import CollectionConfig, load_collection_config
from tcc_crypto.paths import analysis_output_directory, reject_legacy_analysis_paths

PRICE_FIELDS = ("open", "high", "low", "close")


@dataclass(frozen=True)
class DescriptiveAnalysisConfig:
    """Validated settings for the hourly price descriptive analysis."""

    analysis_id: str
    collection_config_path: Path
    price_fields: tuple[str, ...]
    chart_fields: tuple[str, ...]
    quantiles: tuple[float, ...]
    standard_deviation_ddof: int
    kurtosis_definition: str
    output_directory: Path


def load_analysis_config(
    path: Path,
    *,
    repository_root: Path,
) -> tuple[DescriptiveAnalysisConfig, CollectionConfig]:
    """Load analysis settings and the referenced collection configuration."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)
    reject_legacy_analysis_paths(payload)

    price_fields = tuple(str(field) for field in payload["price_fields"])
    chart_fields = tuple(str(field) for field in payload["chart_fields"])
    if not price_fields or len(set(price_fields)) != len(price_fields):
        raise ValueError("price_fields must contain unique field names.")
    if any(field not in PRICE_FIELDS for field in price_fields):
        raise ValueError(f"price_fields must be selected from {PRICE_FIELDS}.")
    if any(field not in price_fields for field in chart_fields):
        raise ValueError("Every chart field must also be a configured price field.")

    quantiles = tuple(float(value) for value in payload["quantiles"])
    if quantiles != (0.25, 0.5, 0.75):
        raise ValueError("This analysis requires quartiles 0.25, 0.50, and 0.75.")

    ddof = int(payload["standard_deviation_ddof"])
    if ddof != 1:
        raise ValueError("The descriptive analysis uses sample variance (ddof=1).")

    collection_config_path = repository_root / str(payload["collection_config"])
    collection_config = load_collection_config(collection_config_path)
    config = DescriptiveAnalysisConfig(
        analysis_id=str(payload["analysis_id"]),
        collection_config_path=collection_config_path,
        price_fields=price_fields,
        chart_fields=chart_fields,
        quantiles=quantiles,
        standard_deviation_ddof=ddof,
        kurtosis_definition=str(payload["kurtosis_definition"]),
        output_directory=analysis_output_directory(
            repository_root, "hourly-prices", str(payload["analysis_id"])
        ),
    )
    return config, collection_config
