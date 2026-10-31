"""Compose the 22 approved daily features without reading or writing files."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.data.validation import PRICE_FIELDS, _validate_daily_values
from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.features.indicators import (
    _chaikin_ad,
    _on_balance_volume,
    _true_range,
    _wilder_atr,
    _wilder_rsi,
    momentum,
    parabolic_sar,
)
from tcc_crypto.features.price import calculate_price_features


def calculate_daily_features(values: pd.DataFrame) -> pd.DataFrame:
    """Return ordered features using only current/past rows; retain warm-up NaNs."""
    _validate_daily_values(values)
    source = values.loc[:, [*PRICE_FIELDS, "quote_asset_volume"]].astype("float64")
    features = calculate_price_features(source)
    features["momentum_10"] = momentum(source["close"])
    features["rsi_14"] = _wilder_rsi(source["close"], period=14)
    features["parabolic_sar"] = parabolic_sar(source)
    features["true_range"] = _true_range(source)
    features["atr_14"] = _wilder_atr(features["true_range"], period=14)
    features["chaikin_ad"] = _chaikin_ad(source)
    features["obv"] = _on_balance_volume(source)
    return features.loc[:, ACTIVE_FEATURES]
