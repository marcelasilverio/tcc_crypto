"""Features: indicators."""

from __future__ import annotations

import pandas as pd
import talib


def _wilder_rsi(close: pd.Series, period: int) -> pd.Series:
    result = pd.Series(float("nan"), index=close.index, dtype="float64")
    if len(close) <= period:
        return result

    differences = close.diff()
    gains = differences.clip(lower=0.0)
    losses = -differences.clip(upper=0.0)
    average_gain = float(gains.iloc[1 : period + 1].mean())
    average_loss = float(losses.iloc[1 : period + 1].mean())

    def rsi_value(gain: float, loss: float) -> float:
        if loss == 0.0:
            return 100.0 if gain > 0.0 else 0.0
        return 100.0 - (100.0 / (1.0 + gain / loss))

    result.iloc[period] = rsi_value(average_gain, average_loss)
    for position in range(period + 1, len(close)):
        average_gain = (
            average_gain * (period - 1) + float(gains.iloc[position])
        ) / period
        average_loss = (
            average_loss * (period - 1) + float(losses.iloc[position])
        ) / period
        result.iloc[position] = rsi_value(average_gain, average_loss)
    return result


def _true_range(values: pd.DataFrame) -> pd.Series:
    previous_close = values["close"].shift(1)
    components = pd.concat(
        [
            values["high"] - values["low"],
            (values["high"] - previous_close).abs(),
            (values["low"] - previous_close).abs(),
        ],
        axis=1,
    )
    result = components.max(axis=1)
    result.iloc[0] = float("nan")
    return result.astype("float64")


def _wilder_atr(true_range: pd.Series, period: int) -> pd.Series:
    result = pd.Series(float("nan"), index=true_range.index, dtype="float64")
    if len(true_range) <= period:
        return result

    average = float(true_range.iloc[1 : period + 1].mean())
    result.iloc[period] = average
    for position in range(period + 1, len(true_range)):
        average = (average * (period - 1) + float(true_range.iloc[position])) / period
        result.iloc[position] = average
    return result


def _chaikin_ad(values: pd.DataFrame) -> pd.Series:
    price_range = values["high"] - values["low"]
    multiplier = pd.Series(0.0, index=values.index, dtype="float64")
    nonzero_range = price_range != 0.0
    multiplier.loc[nonzero_range] = (
        (values.loc[nonzero_range, "close"] - values.loc[nonzero_range, "low"])
        - (values.loc[nonzero_range, "high"] - values.loc[nonzero_range, "close"])
    ) / price_range.loc[nonzero_range]
    return multiplier.mul(values["quote_asset_volume"]).cumsum()


def _on_balance_volume(values: pd.DataFrame) -> pd.Series:
    direction = (
        values["close"]
        .diff()
        .map(lambda change: 1.0 if change > 0 else (-1.0 if change < 0 else 0.0))
    )
    direction.iloc[0] = 1.0
    return direction.mul(values["quote_asset_volume"]).cumsum()


def momentum(close: pd.Series, period: int = 10) -> pd.Series:
    """Current close minus the close `period` daily observations earlier."""
    return close - close.shift(period)


def parabolic_sar(values: pd.DataFrame) -> pd.Series:
    """Provisional Silva SAR: acceleration=maximum=0; verification pending."""
    return pd.Series(
        talib.SAR(
            values["high"].to_numpy(),
            values["low"].to_numpy(),
            acceleration=0.0,
            maximum=0.0,
        ),
        index=values.index,
    )
