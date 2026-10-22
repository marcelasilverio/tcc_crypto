"""Data: loaders."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tcc_crypto.data.gaps import fill_internal_daily_gaps
from tcc_crypto.data.validation import PRICE_FIELDS, _validate_daily_values


def load_daily_feature_input(
    path: Path, *, fill_internal_gaps: bool = False
) -> pd.DataFrame:
    """Load OHLC and USDT quote volume from one immutable raw CSV.

    When ``fill_internal_gaps`` is true, the returned frame follows the
    approved forward-fill policy and includes an ``is_imputed`` audit column.
    """
    columns = ["open_time_ms", *PRICE_FIELDS, "quote_asset_volume"]
    frame = pd.read_csv(path, usecols=columns)
    timestamps = pd.to_datetime(frame.pop("open_time_ms"), unit="ms", utc=True)
    values = frame.apply(pd.to_numeric, errors="raise").astype("float64")
    values.index = pd.DatetimeIndex(timestamps, name="open_time_utc")
    if fill_internal_gaps:
        return fill_internal_daily_gaps(values)
    _validate_daily_values(values)
    return values


def find_symbol_csv(raw_directory: Path, symbol: str) -> Path:
    """Resolve the single immutable daily CSV for a symbol."""
    matches = sorted((raw_directory / symbol).glob(f"{symbol}_1d_*.csv.gz"))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected one daily CSV for {symbol}, found {len(matches)}."
        )
    return matches[0]
