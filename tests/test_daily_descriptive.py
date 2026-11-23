"""Check the descriptive notebook formulas with manually verifiable inputs."""

import ast
import json

import numpy as np
import pandas as pd
import pytest

from tcc_crypto.paths import DESCRIPTIVE_NOTEBOOK, ROOT
from tcc_crypto.preparation import DAY_MS, KLINE_COLUMNS, inspect_candles


@pytest.fixture
def formulas():
    notebook = json.loads((ROOT / DESCRIPTIVE_NOTEBOOK).read_text())
    scope = {"pd": pd, "np": np, "size": 3}
    names = {"prepare_daily", "activity_summary", "paired_correlation"}
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            for function in ast.parse("".join(cell["source"])).body:
                if isinstance(function, ast.FunctionDef) and function.name in names:
                    module = ast.Module(body=[function], type_ignores=[])
                    exec(compile(module, "descriptive-notebook", "exec"), scope)
    assert names <= scope.keys()
    return scope


def test_gaps_amplitude_and_sample_volatility(formulas):
    days = pd.date_range("2025-01-01", periods=9, tz="UTC")
    panel = pd.DataFrame(
        {
            "close": [100.0, 98, 98, 99.96, np.nan, 10, 11, 11, 11],
            "open": [100.0] * 9,
            "high": [110.0] * 9,
            "low": [90.0] * 9,
            "quote_asset_volume": [15.0] * 9,
            "number_of_trades": [3] * 9,
        },
        index=days,
    )
    result = formulas["prepare_daily"](panel)
    assert result["amplitude_pct"].iloc[0] == 20
    np.testing.assert_allclose(
        result["return_pct"].iloc[:6], [np.nan, -2, 0, 2, np.nan, np.nan], atol=1e-12
    )
    assert result["moving_volatility_pp"].iloc[3] == pytest.approx(2)
    assert result["moving_volatility_pp"].iloc[4:8].isna().all()
    assert result["moving_volatility_pp"].iloc[8] == pytest.approx(10 / np.sqrt(3))


def test_daily_and_trade_weighted_averages(formulas):
    data = pd.DataFrame(
        {
            "close": [10, 10, 10],
            "open": [10, 10, 10],
            "high": [10, 10, 10],
            "low": [10, 10, 10],
            "quote_asset_volume": [100, 20, 0],
            "number_of_trades": [4, 1, 0],
        }
    )
    daily = formulas["prepare_daily"](data)
    np.testing.assert_allclose(daily["value_per_trade_usdt"], [25, 20, np.nan])
    result = formulas["activity_summary"](daily)
    assert result["weighted_value_per_trade_usdt"] == 24
    assert result["daily_median_value_per_trade_usdt"] == 22.5
    assert result["trades_zero_days"] == 1
    assert result["days_with_defined_trade_value"] == 2


def test_pairwise_correlations_and_undefined_support(formulas):
    days = pd.date_range("2025-01-01", periods=4, tz="UTC")
    returns = pd.DataFrame({"a": [1, 2, np.nan, 3], "b": [1, 4, 10, 9]}, index=days)
    matched = returns.dropna()
    assert list(matched.index) == [days[0], days[1], days[3]]
    pearson, spearman = formulas["paired_correlation"](matched)
    assert pearson == pytest.approx(24 / np.sqrt(588))
    assert spearman == pytest.approx(1)
    assert np.isnan(formulas["paired_correlation"](matched.iloc[:1])).all()
    assert np.isnan(formulas["paired_correlation"](matched.assign(b=1))).all()


def test_raw_inspection_flags_short_and_invalid_without_filling():
    start = 86_400_000
    raw = pd.DataFrame(
        [
            [start, 2, 3, 1, 2, 100, start + DAY_MS // 2 - 1, 10, 3, 2, 1, 0],
            [start * 3, 2, 1, 1, 2, 100, start * 4 - 1, 10, 3, 2, 1, 0],
        ],
        columns=KLINE_COLUMNS,
    )
    frame, quality = inspect_candles(raw, "TESTUSDT")
    assert len(frame) == 2
    assert frame.index[1] - frame.index[0] == pd.Timedelta(days=2)
    assert quality["valid"].tolist() == [True, False]
    assert quality["shortened_candle"].tolist() == [True, False]
    assert quality["reason"].tolist() == ["", "inconsistent_ohlc"]
    with pytest.raises(ValueError, match="duplicate dates"):
        inspect_candles(pd.concat([raw.iloc[:1], raw]), "TESTUSDT")
