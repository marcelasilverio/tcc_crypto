"""Statistical calculations; no filesystem access."""

from __future__ import annotations

import numpy as np
import pandas as pd

from tcc_crypto.analysis.statistics import distribution_statistics

PRICE_FIELDS = ("open", "high", "low", "close")
VOLUME_FIELD = "quote_asset_volume"


def filter_analysis_window(
    values: pd.DataFrame,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
) -> pd.DataFrame:
    """Return observed rows inside the approved inclusive UTC interval."""
    filtered = values.loc[
        (values.index >= start_utc) & (values.index <= end_utc)
    ].copy()
    if filtered.empty:
        raise ValueError("No observations fall inside the configured analysis window.")
    return filtered


def natural_log_open_close(values: pd.DataFrame) -> pd.DataFrame:
    """Return daily open and close natural logs with real date gaps explicit."""
    prices = values.loc[:, ["open", "close"]]
    if (prices <= 0).any().any():
        raise ValueError("Natural-log price plots require strictly positive prices.")
    daily_index = pd.date_range(prices.index.min(), prices.index.max(), freq="1D")
    return np.log(prices.reindex(daily_index))


def daily_quote_volume_billions(values: pd.DataFrame) -> pd.Series:
    """Return daily USDT quote volume in billions with real gaps explicit."""
    volume = values[VOLUME_FIELD]
    if (volume < 0).any():
        raise ValueError("Quote-volume plots require non-negative values.")
    daily_index = pd.date_range(volume.index.min(), volume.index.max(), freq="1D")
    return volume.reindex(daily_index) / 1_000_000_000


def semester_label(timestamp: pd.Timestamp) -> str:
    """Return the UTC calendar-semester label for one timestamp."""
    half = 1 if timestamp.month <= 6 else 2
    return f"{timestamp.year}-H{half}"


def semester_bounds(label: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return inclusive UTC day boundaries for a YYYY-H1 or YYYY-H2 label."""
    year_text, half = label.split("-H", maxsplit=1)
    year = int(year_text)
    if half == "1":
        return pd.Timestamp(year=year, month=1, day=1, tz="UTC"), pd.Timestamp(
            year=year, month=6, day=30, tz="UTC"
        )
    if half == "2":
        return pd.Timestamp(year=year, month=7, day=1, tz="UTC"), pd.Timestamp(
            year=year, month=12, day=31, tz="UTC"
        )
    raise ValueError(f"Invalid semester label: {label}")


def _series_statistics(
    series: pd.Series,
    *,
    field: str,
    unit: str,
    ddof: int,
) -> dict[str, object]:
    stats = distribution_statistics(series, ddof=ddof)
    q1, median, q3 = stats["q1"], stats["median"], stats["q3"]
    mean = stats["mean"]
    standard_deviation = stats["std"]
    row: dict[str, object] = {
        "Field": field,
        "Unit": unit,
        "Observations": int(series.count()),
        "Missing values": int(series.isna().sum()),
        "Zero observations": None,
        "Zero share": None,
        "Total": None,
        "Mean": mean,
        "Median": median,
        "Sample standard deviation": standard_deviation,
        "Sample variance": stats["variance"],
        "Minimum": stats["minimum"],
        "Q1": q1,
        "Q3": q3,
        "Maximum": stats["maximum"],
        "Range": stats["maximum"] - stats["minimum"],
        "Interquartile range": q3 - q1,
        "Coefficient of variation": standard_deviation / mean if mean != 0 else np.nan,
        "Skewness": stats["skewness"],
        "Excess kurtosis": stats["excess_kurtosis"],
    }
    if field == VOLUME_FIELD:
        zero_count = int(series.eq(0).sum())
        row["Zero observations"] = zero_count
        row["Zero share"] = zero_count / len(series)
        row["Total"] = series.sum()
    return row


def describe_statistics(
    values: pd.DataFrame,
    *,
    ddof: int = 1,
) -> pd.DataFrame:
    """Return one descriptive-statistics row for each analyzed field."""
    rows = []
    for field in values.columns:
        unit = "USDT" if field == VOLUME_FIELD else "USDT per base-asset unit"
        rows.append(
            _series_statistics(values[field], field=field, unit=unit, ddof=ddof)
        )
    return pd.DataFrame(rows)


def describe_semesters(
    values: pd.DataFrame,
    *,
    analysis_start_utc: pd.Timestamp,
    analysis_end_utc: pd.Timestamp,
    ddof: int = 1,
) -> pd.DataFrame:
    """Return field statistics for each observed UTC calendar semester."""
    labels = values.index.map(semester_label)
    rows: list[pd.DataFrame] = []
    for label in dict.fromkeys(labels):
        semester_values = values.loc[labels == label]
        nominal_start, nominal_end = semester_bounds(label)
        status = (
            "Complete"
            if semester_values.index.min() <= nominal_start
            and semester_values.index.max() >= nominal_end
            else "Partial"
        )
        statistics = describe_statistics(semester_values, ddof=ddof)
        statistics.insert(0, "Observed end (UTC)", semester_values.index.max())
        statistics.insert(0, "Observed start (UTC)", semester_values.index.min())
        statistics.insert(0, "Status", status)
        statistics.insert(0, "Semester", label)
        rows.append(statistics)
    return pd.concat(rows, ignore_index=True)


def describe_coverage(symbol: str, values: pd.DataFrame) -> dict[str, object]:
    """Summarize daily coverage without filling gaps or pre-listing history."""
    expected = pd.date_range(values.index.min(), values.index.max(), freq="1D")
    missing_days = expected.difference(values.index)
    return {
        "Symbol": symbol,
        "Observations": len(values),
        "First open (UTC)": values.index.min(),
        "Last open (UTC)": values.index.max(),
        "Observed span (calendar days)": int(
            (values.index.max() - values.index.min()).days + 1
        ),
        "Missing daily openings within observed span": len(missing_days),
    }


def describe_extrema(symbol: str, values: pd.DataFrame) -> pd.DataFrame:
    """Record each analyzed field's minimum and maximum with UTC dates."""
    rows = []
    for field in values.columns:
        unit = "USDT" if field == VOLUME_FIELD else "USDT per base-asset unit"
        rows.append(
            {
                "Symbol": symbol,
                "Field": field,
                "Unit": unit,
                "Minimum": values[field].min(),
                "Minimum date (UTC)": values[field].idxmin(),
                "Maximum": values[field].max(),
                "Maximum date (UTC)": values[field].idxmax(),
            }
        )
    return pd.DataFrame(rows)
