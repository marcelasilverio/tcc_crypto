"""Configuration for daily_descriptive."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tcc_crypto.collection.config import CollectionConfig, load_collection_config
from tcc_crypto.paths import analysis_output_directory, reject_legacy_analysis_paths

PRICE_FIELDS = ("open", "high", "low", "close")
VOLUME_FIELD = "quote_asset_volume"


@dataclass(frozen=True)
class DailyPriceVolumeAnalysisConfig:
    """Validated settings for the daily price and USDT-volume analysis."""

    analysis_id: str
    collection_config_path: Path
    analysis_start_utc: pd.Timestamp
    analysis_end_utc: pd.Timestamp
    price_fields: tuple[str, ...]
    volume_field: str
    quantiles: tuple[float, ...]
    standard_deviation_ddof: int
    kurtosis_definition: str
    semester_time_zone: str
    output_directory: Path
    figure_rows: int
    figure_columns: int
    price_figure_transform: str
    volume_figure_scale: str
    price_figure_filename: str
    volume_figure_filename: str


def load_analysis_config(
    path: Path,
    *,
    repository_root: Path,
) -> tuple[DailyPriceVolumeAnalysisConfig, CollectionConfig]:
    """Load the analysis settings and referenced daily collection settings."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)
    reject_legacy_analysis_paths(payload)

    price_fields = tuple(str(field) for field in payload["price_fields"])
    if price_fields != PRICE_FIELDS:
        raise ValueError(f"price_fields must be exactly {PRICE_FIELDS}.")
    volume_field = str(payload["volume_field"])
    if volume_field != VOLUME_FIELD:
        raise ValueError(f"volume_field must be {VOLUME_FIELD!r}.")
    quantiles = tuple(float(value) for value in payload["quantiles"])
    if quantiles != (0.25, 0.5, 0.75):
        raise ValueError("This analysis requires quartiles 0.25, 0.50, and 0.75.")
    ddof = int(payload["standard_deviation_ddof"])
    if ddof != 1:
        raise ValueError("The descriptive analysis uses sample variance (ddof=1).")
    if str(payload["semester_time_zone"]) != "UTC":
        raise ValueError("Semester boundaries must use UTC.")

    analysis_start = pd.Timestamp(payload["analysis_start_utc"])
    analysis_end = pd.Timestamp(payload["analysis_end_utc"])
    if analysis_start.tzinfo is None or analysis_end.tzinfo is None:
        raise ValueError("Analysis boundaries must be timezone-aware.")
    analysis_start = analysis_start.tz_convert("UTC")
    analysis_end = analysis_end.tz_convert("UTC")
    if analysis_start > analysis_end:
        raise ValueError("analysis_start_utc must not follow analysis_end_utc.")

    collection_path = repository_root / str(payload["collection_config"])
    collection_config = load_collection_config(collection_path)
    if collection_config.interval != "1d":
        raise ValueError("The referenced collection must use daily (1d) klines.")
    if collection_config.quote_asset != "USDT":
        raise ValueError("The referenced collection must contain USDT-quoted pairs.")

    figure_rows = int(payload["figure_rows"])
    figure_columns = int(payload["figure_columns"])
    if figure_rows <= 0 or figure_columns <= 0:
        raise ValueError("Figure rows and columns must be positive integers.")
    if figure_rows * figure_columns != len(collection_config.symbols):
        raise ValueError("The figure grid must contain exactly one panel per symbol.")
    if str(payload["price_figure_transform"]) != "natural_log":
        raise ValueError("The price figure must use the natural-log transformation.")
    if str(payload["volume_figure_scale"]) != "linear":
        raise ValueError("The quote-volume figure must use a linear scale.")

    config = DailyPriceVolumeAnalysisConfig(
        analysis_id=str(payload["analysis_id"]),
        collection_config_path=collection_path,
        analysis_start_utc=analysis_start,
        analysis_end_utc=analysis_end,
        price_fields=price_fields,
        volume_field=volume_field,
        quantiles=quantiles,
        standard_deviation_ddof=ddof,
        kurtosis_definition=str(payload["kurtosis_definition"]),
        semester_time_zone="UTC",
        output_directory=analysis_output_directory(
            repository_root, "daily-descriptive", str(payload["analysis_id"])
        ),
        figure_rows=figure_rows,
        figure_columns=figure_columns,
        price_figure_transform="natural_log",
        volume_figure_scale="linear",
        price_figure_filename=str(payload["price_figure_filename"]),
        volume_figure_filename=str(payload["volume_figure_filename"]),
    )
    return config, collection_config
