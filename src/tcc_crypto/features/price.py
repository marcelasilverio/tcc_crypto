"""Features: price."""

from __future__ import annotations

import math

import pandas as pd


def _natural_log_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator).map(
        lambda value: math.log(value) if pd.notna(value) else float("nan")
    )


def calculate_price_features(source: pd.DataFrame) -> pd.DataFrame:
    """Calculate r1-r15 exactly as approved; all lags refer to UTC days."""
    features = pd.DataFrame(index=source.index)
    features["r1"] = _natural_log_ratio(source["close"], source["close"].shift(1))
    features["r2"] = _natural_log_ratio(
        source["close"].shift(1), source["close"].shift(2)
    )
    features["r3"] = _natural_log_ratio(
        source["close"].shift(2), source["close"].shift(3)
    )
    features["r4"] = _natural_log_ratio(
        source["close"].shift(3), source["close"].shift(4)
    )
    features["r5"] = _natural_log_ratio(source["high"], source["open"])
    features["r6"] = _natural_log_ratio(source["high"], source["open"].shift(1))
    features["r7"] = _natural_log_ratio(source["high"], source["open"].shift(2))
    features["r8"] = _natural_log_ratio(source["high"], source["open"].shift(3))
    features["r9"] = _natural_log_ratio(
        source["high"].shift(1), source["open"].shift(1)
    )
    features["r10"] = _natural_log_ratio(
        source["high"].shift(2), source["open"].shift(2)
    )
    features["r11"] = _natural_log_ratio(
        source["high"].shift(3), source["open"].shift(3)
    )
    features["r12"] = _natural_log_ratio(source["low"], source["open"])
    features["r13"] = _natural_log_ratio(
        source["low"].shift(1), source["open"].shift(1)
    )
    features["r14"] = _natural_log_ratio(
        source["low"].shift(2), source["open"].shift(2)
    )
    features["r15"] = _natural_log_ratio(
        source["low"].shift(3), source["open"].shift(3)
    )

    return features
