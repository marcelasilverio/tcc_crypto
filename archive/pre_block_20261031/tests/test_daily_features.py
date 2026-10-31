"""Tests for daily feature construction without look-ahead."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from tcc_crypto.data.gaps import fill_internal_daily_gaps
from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.features.config import load_daily_feature_config
from tcc_crypto.features.daily import calculate_daily_features


def _daily_values(periods: int = 20) -> pd.DataFrame:
    positions = list(range(periods))
    opens = [100.0 + position for position in positions]
    closes = [
        value + (1.0 if position % 2 == 0 else -0.5)
        for position, value in enumerate(opens)
    ]
    return pd.DataFrame(
        {
            "open": opens,
            "high": [
                max(open_price, close) + 2.0 for open_price, close in zip(opens, closes)
            ],
            "low": [
                min(open_price, close) - 1.0 for open_price, close in zip(opens, closes)
            ],
            "close": closes,
            "quote_asset_volume": [1_000.0 + 10.0 * position for position in positions],
        },
        index=pd.date_range("2026-01-01", periods=periods, freq="D", tz="UTC"),
    )


def test_loads_approved_daily_feature_configuration() -> None:
    config = load_daily_feature_config(Path("configs/binance_daily_features.json"))

    assert config.interval == "1d"
    assert config.volume_field == "quote_asset_volume"
    assert config.missing_data_policy == "forward_fill_internal"
    assert config.imputation_marker == "is_imputed"
    assert config.active_features == ACTIVE_FEATURES
    assert config.parabolic_sar_acceleration == 0.0
    assert config.parabolic_sar_maximum == 0.0
    assert config.parabolic_sar_verification_required is True
    assert config.features_requiring_verification == ("parabolic_sar",)
    assert config.feature_output_directory == Path(
        "data/processed/binance/spot/1d/features"
    )
    assert config.analysis_output_directory == Path(
        "outputs/binance/spot/feature-selection/binance_daily_silva_2026_features_v1"
    )


def test_calculates_price_features_from_current_and_past_rows() -> None:
    values = _daily_values()
    features = calculate_daily_features(values)
    position = 4

    assert features.iloc[position]["r1"] == pytest.approx(
        math.log(values.iloc[position]["close"] / values.iloc[position - 1]["close"])
    )
    assert features.iloc[position]["r4"] == pytest.approx(
        math.log(
            values.iloc[position - 3]["close"] / values.iloc[position - 4]["close"]
        )
    )
    assert features.iloc[position]["r6"] == pytest.approx(
        math.log(values.iloc[position]["high"] / values.iloc[position - 1]["open"])
    )
    assert features.iloc[position]["r9"] == pytest.approx(
        math.log(values.iloc[position - 1]["high"] / values.iloc[position - 1]["open"])
    )
    assert features.iloc[position]["r15"] == pytest.approx(
        math.log(values.iloc[position - 3]["low"] / values.iloc[position - 3]["open"])
    )


def test_uses_quote_asset_volume_for_volume_features() -> None:
    values = _daily_values(periods=3)
    features = calculate_daily_features(values)

    first_multiplier = (
        (values.iloc[0]["close"] - values.iloc[0]["low"])
        - (values.iloc[0]["high"] - values.iloc[0]["close"])
    ) / (values.iloc[0]["high"] - values.iloc[0]["low"])
    assert features.iloc[0]["chaikin_ad"] == pytest.approx(
        first_multiplier * values.iloc[0]["quote_asset_volume"]
    )
    assert features.iloc[0]["obv"] == values.iloc[0]["quote_asset_volume"]
    assert features.iloc[1]["obv"] == pytest.approx(
        values.iloc[0]["quote_asset_volume"] + (-values.iloc[1]["quote_asset_volume"])
    )


def test_indicator_warm_up_is_preserved_as_missing() -> None:
    values = _daily_values()
    features = calculate_daily_features(values)

    assert features["momentum_10"].iloc[:10].isna().all()
    assert features["momentum_10"].iloc[10] == pytest.approx(
        values["close"].iloc[10] - values["close"].iloc[0]
    )
    assert features["rsi_14"].iloc[:14].isna().all()
    assert pd.notna(features["rsi_14"].iloc[14])
    assert features["atr_14"].iloc[:14].isna().all()
    assert pd.notna(features["atr_14"].iloc[14])


def test_future_rows_do_not_change_earlier_features() -> None:
    values = _daily_values()
    baseline = calculate_daily_features(values)
    changed = values.copy()
    changed.iloc[-1, changed.columns.get_loc("high")] *= 10.0
    changed.iloc[-1, changed.columns.get_loc("close")] *= 5.0
    changed.iloc[-1, changed.columns.get_loc("quote_asset_volume")] *= 20.0
    changed.iloc[-1, changed.columns.get_loc("low")] = changed.iloc[-1]["open"]
    changed.iloc[-1, changed.columns.get_loc("high")] = max(
        changed.iloc[-1]["high"], changed.iloc[-1]["close"]
    )

    recalculated = calculate_daily_features(changed)
    pd.testing.assert_frame_equal(baseline.iloc[:-1], recalculated.iloc[:-1])


def test_rejects_missing_calendar_days_instead_of_crossing_gap() -> None:
    values = _daily_values().drop(pd.Timestamp("2026-01-05", tz="UTC"))

    with pytest.raises(ValueError, match="align internal gaps"):
        calculate_daily_features(values)

    aligned = fill_internal_daily_gaps(values)
    features = calculate_daily_features(aligned)

    assert aligned.loc["2026-01-05", "is_imputed"]
    assert len(features) == len(_daily_values())


def test_parabolic_sar_reproduces_zero_valued_talib_parameters() -> None:
    high = [3.0, 4.0, 5.0, 4.5, 4.0, 3.5, 3.0, 3.5, 4.0, 4.5]
    low = [1.0, 2.0, 3.0, 2.5, 2.0, 1.5, 1.0, 1.5, 2.0, 2.5]
    values = pd.DataFrame(
        {
            "open": [(upper + lower) / 2.0 for upper, lower in zip(high, low)],
            "high": high,
            "low": low,
            "close": [(upper + lower) / 2.0 for upper, lower in zip(high, low)],
            "quote_asset_volume": [1_000.0] * len(high),
        },
        index=pd.date_range("2026-01-01", periods=len(high), freq="D", tz="UTC"),
    )
    features = calculate_daily_features(values)

    assert tuple(features.columns) == ACTIVE_FEATURES
    assert pd.isna(features["parabolic_sar"].iloc[0])
    assert features["parabolic_sar"].iloc[1:6].tolist() == [1.0] * 5
    assert features["parabolic_sar"].iloc[6:].tolist() == [5.0] * 4
