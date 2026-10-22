"""In-memory dataset builders retained for existing callers."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.data.config import DailyModelingDatasetConfig
from tcc_crypto.data.dataset import (
    DailyDataConfig,
    assemble_dataset,
    calculation_period,
    sample_features,
)
from tcc_crypto.data.loaders import find_symbol_csv, load_daily_feature_input
from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.features.daily import calculate_daily_features
from tcc_crypto.targets.daily import build_next_day_d0_targets


def build_daily_modeling_dataset(config: DailyModelingDatasetConfig) -> pd.DataFrame:
    data = DailyDataConfig(
        config.dataset_id,
        config.symbol,
        config.warmup_start_utc,
        config.sample_start_utc,
        config.sample_end_utc,
        True,
        config.target_thresholds,
    )
    raw_path = find_symbol_csv(config.raw_directory, config.symbol)
    aligned = calculation_period(
        load_daily_feature_input(raw_path, fill_internal_gaps=True), data
    )
    features = calculate_daily_features(aligned)
    targets = build_next_day_d0_targets(
        aligned,
        sample_features(features, data).index,
        thresholds=data.target_thresholds,
    )
    return assemble_dataset(features, targets, aligned, data)


def modeling_feature_columns() -> tuple[str, ...]:
    return ACTIVE_FEATURES
