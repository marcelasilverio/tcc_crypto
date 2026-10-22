"""Data: validation."""

from __future__ import annotations

import math
from datetime import timedelta

import pandas as pd

DAY = timedelta(days=1)


PRICE_FIELDS = ("open", "high", "low", "close")


def _validate_daily_values(
    values: pd.DataFrame, *, require_complete_calendar: bool = True
) -> None:
    required = {*PRICE_FIELDS, "quote_asset_volume"}
    missing = required.difference(values.columns)
    if missing:
        raise ValueError(f"Daily feature input is missing columns: {sorted(missing)}.")
    if values.empty:
        raise ValueError("Daily feature input contains no observations.")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError("Daily feature input must use a DatetimeIndex.")
    if values.index.tz is None:
        raise ValueError("Daily feature timestamps must include timezone information.")
    if str(values.index.tz) != "UTC":
        raise ValueError("Daily feature timestamps must use UTC.")
    if values.index.has_duplicates:
        raise ValueError("Daily feature input contains duplicate timestamps.")
    if not values.index.is_monotonic_increasing:
        raise ValueError("Daily feature input must be chronologically ordered.")
    if (values.index != values.index.normalize()).any():
        raise ValueError("Daily feature timestamps must be aligned to UTC midnight.")
    if (
        require_complete_calendar
        and len(values.index) > 1
        and not (values.index.to_series().diff().iloc[1:] == DAY).all()
    ):
        raise ValueError(
            "Daily feature input contains missing UTC days; align internal gaps "
            "before feature construction."
        )

    numeric = values.loc[:, [*PRICE_FIELDS, "quote_asset_volume"]]
    if numeric.isna().any().any():
        raise ValueError("Daily feature input contains missing values.")
    if not numeric.map(math.isfinite).all().all():
        raise ValueError("Daily feature input contains non-finite values.")
    if not (numeric.loc[:, PRICE_FIELDS] > 0).all().all():
        raise ValueError("Daily feature prices must be strictly positive.")
    if (numeric["quote_asset_volume"] < 0).any():
        raise ValueError("Daily quote-asset volume must be non-negative.")

    inconsistent = (
        (numeric["high"] < numeric[["open", "close"]].max(axis=1))
        | (numeric["low"] > numeric[["open", "close"]].min(axis=1))
        | (numeric["high"] < numeric["low"])
    )
    if inconsistent.any():
        raise ValueError("Daily feature input contains OHLC consistency violations.")
