"""Statistical calculations; no filesystem access."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.analysis.statistics import distribution_statistics


def describe_price_levels(
    symbol: str,
    prices: pd.DataFrame,
    *,
    ddof: int = 1,
) -> pd.DataFrame:
    """Return one explicitly defined descriptive-statistics row per price field."""
    rows: list[dict[str, object]] = []
    for field in prices.columns:
        series = prices[field]
        stats = distribution_statistics(series, ddof=ddof)
        q1, median, q3 = stats["q1"], stats["median"], stats["q3"]
        mean = stats["mean"]
        standard_deviation = stats["std"]
        rows.append(
            {
                "Symbol": symbol,
                "Price field": field,
                "Observations": int(series.count()),
                "Missing values": int(series.isna().sum()),
                "Mean (USDT)": mean,
                "Median (USDT)": median,
                "Standard deviation (USDT)": standard_deviation,
                "Variance (USDT squared)": stats["variance"],
                "Minimum (USDT)": stats["minimum"],
                "Q1 (USDT)": q1,
                "Q3 (USDT)": q3,
                "Maximum (USDT)": stats["maximum"],
                "Range (USDT)": stats["maximum"] - stats["minimum"],
                "Interquartile range (USDT)": q3 - q1,
                "Coefficient of variation (%)": 100 * standard_deviation / mean,
                "Skewness": stats["skewness"],
                "Excess kurtosis": stats["excess_kurtosis"],
            }
        )
    return pd.DataFrame(rows)


def describe_coverage(symbol: str, prices: pd.DataFrame) -> dict[str, object]:
    """Summarize observed coverage without filling gaps or pre-listing history."""
    expected = pd.date_range(prices.index.min(), prices.index.max(), freq="1h")
    missing_within_span = expected.difference(prices.index)
    return {
        "Symbol": symbol,
        "Observations": len(prices),
        "First open (UTC)": prices.index.min(),
        "Last open (UTC)": prices.index.max(),
        "Observed span (days)": (
            prices.index.max() - prices.index.min()
        ).total_seconds()
        / 86_400,
        "Missing hours within observed span": len(missing_within_span),
    }


def describe_extremes(symbol: str, prices: pd.DataFrame) -> pd.DataFrame:
    """Record the values and UTC timestamps of each price field's extrema."""
    rows = []
    for field in prices.columns:
        rows.append(
            {
                "Symbol": symbol,
                "Price field": field,
                "Minimum (USDT)": prices[field].min(),
                "Minimum timestamp (UTC)": prices[field].idxmin(),
                "Maximum (USDT)": prices[field].max(),
                "Maximum timestamp (UTC)": prices[field].idxmax(),
            }
        )
    return pd.DataFrame(rows)
