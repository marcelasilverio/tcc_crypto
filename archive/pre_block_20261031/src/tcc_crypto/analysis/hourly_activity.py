"""Statistical calculations; no filesystem access."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tcc_crypto.analysis.statistics import distribution_statistics

ACTIVITY_FIELDS = (
    "base_asset_volume",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
)


def activity_unit(symbol: str, field: str) -> str:
    """Return the measurement unit for one activity field."""
    if field == "number_of_trades":
        return "trades"
    if "quote_asset" in field:
        return "USDT"
    if "base_asset" in field:
        return symbol.removesuffix("USDT")
    raise ValueError(f"Unknown activity field: {field}")


def describe_market_activity(
    symbol: str,
    activity: pd.DataFrame,
    *,
    ddof: int = 1,
) -> pd.DataFrame:
    """Return explicitly defined statistics for each hourly activity field."""
    rows: list[dict[str, object]] = []
    for field in activity.columns:
        series = activity[field]
        stats = distribution_statistics(series, ddof=ddof)
        q1, median, q3 = stats["q1"], stats["median"], stats["q3"]
        mean = stats["mean"]
        standard_deviation = stats["std"]
        zero_count = int(series.eq(0).sum())
        rows.append(
            {
                "Symbol": symbol,
                "Activity field": field,
                "Unit": activity_unit(symbol, field),
                "Observations": int(series.count()),
                "Missing values": int(series.isna().sum()),
                "Zero observations": zero_count,
                "Zero share (%)": 100 * zero_count / len(series),
                "Total": series.sum(),
                "Mean per hour": mean,
                "Median per hour": median,
                "Standard deviation per hour": standard_deviation,
                "Variance per hour": stats["variance"],
                "Minimum per hour": stats["minimum"],
                "Q1 per hour": q1,
                "Q3 per hour": q3,
                "Maximum per hour": stats["maximum"],
                "Range per hour": stats["maximum"] - stats["minimum"],
                "Interquartile range per hour": q3 - q1,
                "Coefficient of variation (%)": (
                    100 * standard_deviation / mean if mean != 0 else np.nan
                ),
                "Skewness": stats["skewness"],
                "Excess kurtosis": stats["excess_kurtosis"],
            }
        )
    return pd.DataFrame(rows)


def describe_activity_extremes(symbol: str, activity: pd.DataFrame) -> pd.DataFrame:
    """Record hourly activity minima and maxima with exact UTC timestamps."""
    rows = []
    for field in activity.columns:
        rows.append(
            {
                "Symbol": symbol,
                "Activity field": field,
                "Unit": activity_unit(symbol, field),
                "Minimum per hour": activity[field].min(),
                "Minimum timestamp (UTC)": activity[field].idxmin(),
                "Maximum per hour": activity[field].max(),
                "Maximum timestamp (UTC)": activity[field].idxmax(),
            }
        )
    return pd.DataFrame(rows)
