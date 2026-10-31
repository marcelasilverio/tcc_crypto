"""Data: development."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pandas as pd

from tcc_crypto.data.dataset import (
    DailyDataConfig,
    assemble_dataset,
    calculation_period,
    sample_features,
)
from tcc_crypto.data.loaders import find_symbol_csv, load_daily_feature_input
from tcc_crypto.features.daily import calculate_daily_features
from tcc_crypto.modeling.config import DailySvmGridSearchConfig
from tcc_crypto.targets.daily import build_next_day_d0_targets


@dataclass(frozen=True)
class SymbolDevelopmentDataset:
    """One symbol's development-only modeling data and source evidence."""

    symbol: str
    dataset: pd.DataFrame
    raw_path: Path
    raw_sha256: str
    first_observed_utc: pd.Timestamp
    last_observed_utc: pd.Timestamp


def build_symbol_development_dataset(
    config: DailySvmGridSearchConfig, symbol: str
) -> SymbolDevelopmentDataset:
    """Build features and targets without loading final-test observations.

    June 2019 is retained as indicator warm-up. The day immediately after the
    development feature period is loaded only to construct the final next-day
    development target; no feature row from that boundary day is retained.
    """
    if symbol not in config.candidate_symbols:
        raise ValueError(f"{symbol} is not in the configured candidate universe.")
    raw_path = find_symbol_csv(config.raw_directory, symbol)
    aligned = load_daily_feature_input(raw_path, fill_internal_gaps=True)
    first_observed = aligned.index[0]
    last_observed = aligned.index[-1]
    data = DailyDataConfig(
        config.experiment_id,
        symbol,
        config.development_start_utc - pd.Timedelta(days=30),
        config.development_start_utc,
        config.development_end_utc,
    )
    calculation_values = calculation_period(aligned, data)
    features = calculate_daily_features(calculation_values)
    targets = build_next_day_d0_targets(
        calculation_values, sample_features(features, data).index
    )
    dataset = assemble_dataset(features, targets, calculation_values, data)
    dataset.attrs["first_observed_utc"] = first_observed
    dataset.attrs["last_observed_utc"] = last_observed
    dataset.attrs["raw_path"] = str(raw_path)
    return SymbolDevelopmentDataset(
        symbol=symbol,
        dataset=dataset,
        raw_path=raw_path,
        raw_sha256=sha256(raw_path.read_bytes()).hexdigest(),
        first_observed_utc=first_observed,
        last_observed_utc=last_observed,
    )
