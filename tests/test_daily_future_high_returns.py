from pathlib import Path

import pandas as pd
import pytest

from tcc_crypto.daily_future_high_returns import (
    calculate_future_high_returns,
    load_future_high_return_config,
    select_reproducible_symbols,
)


def _prices() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0, 95.0, 90.0, 105.0, 110.0],
            "high": [110.0, 98.0, 99.0, 120.0, 121.0],
        },
        index=pd.date_range("2026-10-03", periods=5, freq="D", tz="UTC"),
    )


def test_calculates_all_horizons_from_the_same_base_open() -> None:
    result = calculate_future_high_returns(
        _prices(),
        start_utc=pd.Timestamp("2026-10-03", tz="UTC"),
        end_utc=pd.Timestamp("2026-10-03", tz="UTC"),
    )

    row = result.iloc[0]
    assert row["base_open"] == 100.0
    assert row["D0"] == pytest.approx(0.10)
    assert row["D1"] == pytest.approx(-0.02)
    assert row["D2"] == pytest.approx(-0.01)
    assert row["D3"] == pytest.approx(0.20)


def test_missing_calendar_day_does_not_shift_a_later_high_backward() -> None:
    prices = _prices().drop(pd.Timestamp("2026-10-04", tz="UTC"))
    result = calculate_future_high_returns(
        prices,
        start_utc=pd.Timestamp("2026-10-03", tz="UTC"),
        end_utc=pd.Timestamp("2026-10-03", tz="UTC"),
    )

    assert pd.isna(result.iloc[0]["D1"])
    assert result.iloc[0]["D2"] == pytest.approx(-0.01)


def test_incomplete_final_horizons_remain_missing() -> None:
    result = calculate_future_high_returns(
        _prices(),
        start_utc=pd.Timestamp("2026-10-07", tz="UTC"),
        end_utc=pd.Timestamp("2026-10-07", tz="UTC"),
    )

    assert result.iloc[0]["D0"] == pytest.approx(0.10)
    assert result.iloc[0][["D1", "D2", "D3"]].isna().all()


def test_seeded_symbol_selection_is_reproducible() -> None:
    eligible = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "XRPUSDT")
    first = select_reproducible_symbols(
        eligible,
        required_symbol="BTCUSDT",
        additional_symbol_count=3,
        random_seed=17,
    )
    second = select_reproducible_symbols(
        eligible,
        required_symbol="BTCUSDT",
        additional_symbol_count=3,
        random_seed=17,
    )

    assert first == second
    assert first[0] == "BTCUSDT"
    assert len(set(first)) == 4


def test_loads_repository_configuration() -> None:
    config = load_future_high_return_config(
        Path("configs/binance_daily_future_high_returns.json")
    )

    assert config.horizons_days == (0, 1, 2, 3)
    assert config.required_symbol == "BTCUSDT"
    assert config.random_seed == 20261002
