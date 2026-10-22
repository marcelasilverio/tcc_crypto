"""Pure operations for selecting the feature period and joining daily targets."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tcc_crypto.features.warmup import remove_leading_feature_warmup


@dataclass(frozen=True)
class DailyDataConfig:
    """Data preparation settings, independent of estimator and search settings."""

    context_id: str
    symbol: str
    warmup_start_utc: pd.Timestamp
    sample_start_utc: pd.Timestamp
    sample_end_utc: pd.Timestamp
    require_warmup_start: bool = False
    target_thresholds: tuple[float, ...] = (0.02, 0.03, 0.04)


def calculation_period(aligned: pd.DataFrame, config: DailyDataConfig) -> pd.DataFrame:
    """Keep the original warm-up and the extra day needed for the last target."""
    end = config.sample_end_utc + pd.Timedelta(days=1)
    values = aligned.loc[config.warmup_start_utc : end].copy()
    if values.empty:
        raise ValueError("No daily values overlap the configured calculation period.")
    if config.require_warmup_start and values.index[0] != config.warmup_start_utc:
        raise ValueError("The configured warm-up start is not observed or aligned.")
    return values


def sample_features(features: pd.DataFrame, config: DailyDataConfig) -> pd.DataFrame:
    complete = remove_leading_feature_warmup(features)
    sample = complete.loc[config.sample_start_utc : config.sample_end_utc].copy()
    if sample.empty:
        raise ValueError("No complete feature rows overlap the configured sample.")
    return sample


def assemble_dataset(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    aligned: pd.DataFrame,
    config: DailyDataConfig,
) -> pd.DataFrame:
    """Join already calculated features and targets; never recalculate either."""
    sample = sample_features(features, config)
    if not sample.index.equals(targets.index):
        raise ValueError(
            "Targets must have exactly the sample feature dates, in order."
        )
    result = sample.join(targets)
    result.insert(0, "symbol", config.symbol)
    result.insert(
        1,
        "feature_is_imputed",
        aligned["is_imputed"].reindex(result.index).astype("boolean"),
    )
    result.attrs.update(aligned.attrs)
    return result
