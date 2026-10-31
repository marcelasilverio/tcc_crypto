"""Future outcomes, never features available at the base timestamp."""

from __future__ import annotations

from typing import Sequence

import pandas as pd

from tcc_crypto.data.time import _parse_utc_timestamp


def calculate_future_high_returns(
    daily_prices: pd.DataFrame,
    *,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
    horizons_days: Sequence[int] = (0, 1, 2, 3),
) -> pd.DataFrame:
    """Calculate ``(high[t+h] - open[t]) / open[t]`` for exact UTC dates.

    Missing calendar days and horizons beyond the observed data remain missing;
    observations are never shifted across a gap or synthesized.
    """
    required_columns = {"open", "high"}
    if not required_columns.issubset(daily_prices.columns):
        raise ValueError("daily_prices must contain open and high columns.")
    if not isinstance(daily_prices.index, pd.DatetimeIndex):
        raise TypeError("daily_prices must use a DatetimeIndex.")
    if daily_prices.index.tz is None:
        raise ValueError("daily_prices timestamps must include timezone information.")
    if daily_prices.index.has_duplicates:
        raise ValueError("daily_prices contains duplicate timestamps.")

    horizons = tuple(int(value) for value in horizons_days)
    if horizons != tuple(range(len(horizons))):
        raise ValueError("horizons_days must be consecutive and start at zero.")

    start = _parse_utc_timestamp(start_utc, "start_utc")
    end = _parse_utc_timestamp(end_utc, "end_utc")
    prices = daily_prices.sort_index().copy()
    prices.index = prices.index.tz_convert("UTC")
    base = prices.loc[(prices.index >= start) & (prices.index <= end), ["open"]].copy()
    result = base.rename(columns={"open": "base_open"})

    for horizon in horizons:
        target_dates = result.index + pd.Timedelta(days=horizon)
        future_high = prices["high"].reindex(target_dates)
        future_high.index = result.index
        result[f"D{horizon}"] = future_high.div(result["base_open"]).sub(1.0)

    result.index.name = "date_utc"
    return result
