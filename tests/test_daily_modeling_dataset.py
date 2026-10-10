"""Tests for daily modeling alignment and approved missing-data treatment."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tcc_crypto.daily_features import fill_internal_daily_gaps
from tcc_crypto.daily_modeling_dataset import (
    build_next_day_d0_targets,
    load_daily_modeling_dataset_config,
)


def _daily_values() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0, 200.0, 300.0, 400.0],
            "high": [101.0, 206.0, 312.0, 420.0],
            "low": [99.0, 198.0, 297.0, 396.0],
            "close": [100.5, 204.0, 305.0, 410.0],
            "quote_asset_volume": [1_000.0, 2_000.0, 3_000.0, 4_000.0],
        },
        index=pd.date_range("2019-06-01", periods=4, freq="D", tz="UTC"),
    )


def test_fills_only_internal_days_and_marks_imputed_rows() -> None:
    values = _daily_values().drop(pd.Timestamp("2019-06-02", tz="UTC"))

    aligned = fill_internal_daily_gaps(values)

    assert aligned.index[0] == values.index[0]
    assert aligned.index[-1] == values.index[-1]
    assert aligned.loc["2019-06-02", "is_imputed"]
    assert aligned.loc["2019-06-02", "open"] == values.loc["2019-06-01", "open"]
    assert aligned.loc["2019-06-02", "quote_asset_volume"] == values.loc[
        "2019-06-01", "quote_asset_volume"
    ]
    assert aligned["is_imputed"].sum() == 1


def test_next_day_target_uses_next_day_open_and_high() -> None:
    values = _daily_values()
    feature_index = values.index[:3]

    targets = build_next_day_d0_targets(values, feature_index)

    assert targets.loc[feature_index[0], "target_date_utc"] == feature_index[1]
    assert targets.loc[feature_index[0], "next_day_d0"] == pytest.approx(0.03)
    assert targets.loc[feature_index[0], "target_2pct"] == 1
    assert targets.loc[feature_index[0], "target_3pct"] == 1
    assert targets.loc[feature_index[0], "target_4pct"] == 0
    assert targets.loc[feature_index[1], "next_day_d0"] == pytest.approx(0.04)


def test_next_day_target_does_not_use_current_day_d0() -> None:
    values = _daily_values()
    feature_index = values.index[:1]

    targets = build_next_day_d0_targets(values, feature_index)

    current_day_d0 = values.iloc[0]["high"] / values.iloc[0]["open"] - 1.0
    assert current_day_d0 == pytest.approx(0.01)
    assert targets.iloc[0]["next_day_d0"] == pytest.approx(0.03)


def test_missing_next_day_remains_unlabeled() -> None:
    values = _daily_values().iloc[:1]

    targets = build_next_day_d0_targets(values, values.index)

    assert pd.isna(targets.iloc[0]["next_day_d0"])
    assert pd.isna(targets.iloc[0]["target_2pct"])


def test_loads_approved_btc_pilot_configuration() -> None:
    config = load_daily_modeling_dataset_config(
        Path("configs/binance_daily_svm_pilot_dataset.json")
    )

    assert config.symbol == "BTCUSDT"
    assert config.warmup_start_utc == pd.Timestamp("2019-06-01", tz="UTC")
    assert config.sample_start_utc == pd.Timestamp("2019-07-01", tz="UTC")
    assert config.sample_end_utc == pd.Timestamp("2019-12-31", tz="UTC")
    assert config.target_thresholds == (0.02, 0.03, 0.04)
    assert config.training_window_sizes == (60, 75, 90)
    assert config.estimator == "sklearn.svm.SVC"
    assert config.estimator_parameters == "defaults"
    assert config.model_training_status == "pending_scaling_and_metric_approval"
