"""Describe and visualize canonical Binance hourly OHLC price series."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from tcc_crypto.binance_hourly_collection import CollectionConfig, load_collection_config

PRICE_FIELDS = ("open", "high", "low", "close")
HOUR_MS = 60 * 60 * 1000


@dataclass(frozen=True)
class DescriptiveAnalysisConfig:
    """Validated settings for the hourly price descriptive analysis."""

    analysis_id: str
    collection_config_path: Path
    price_fields: tuple[str, ...]
    chart_fields: tuple[str, ...]
    quantiles: tuple[float, ...]
    standard_deviation_ddof: int
    kurtosis_definition: str
    output_directory: Path


@dataclass(frozen=True)
class AnalysisArtifacts:
    """Paths and in-memory tables produced by the analysis."""

    summary: pd.DataFrame
    coverage: pd.DataFrame
    extremes: pd.DataFrame
    summary_csv: Path
    coverage_csv: Path
    extremes_csv: Path
    workbook: Path
    overview_figure: Path
    individual_figure_directory: Path


def load_analysis_config(
    path: Path,
    *,
    repository_root: Path,
) -> tuple[DescriptiveAnalysisConfig, CollectionConfig]:
    """Load analysis settings and the referenced collection configuration."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)

    price_fields = tuple(str(field) for field in payload["price_fields"])
    chart_fields = tuple(str(field) for field in payload["chart_fields"])
    if not price_fields or len(set(price_fields)) != len(price_fields):
        raise ValueError("price_fields must contain unique field names.")
    if any(field not in PRICE_FIELDS for field in price_fields):
        raise ValueError(f"price_fields must be selected from {PRICE_FIELDS}.")
    if any(field not in price_fields for field in chart_fields):
        raise ValueError("Every chart field must also be a configured price field.")

    quantiles = tuple(float(value) for value in payload["quantiles"])
    if quantiles != (0.25, 0.5, 0.75):
        raise ValueError("This analysis requires quartiles 0.25, 0.50, and 0.75.")

    ddof = int(payload["standard_deviation_ddof"])
    if ddof != 1:
        raise ValueError("The descriptive analysis uses sample variance (ddof=1).")

    collection_config_path = repository_root / str(payload["collection_config"])
    collection_config = load_collection_config(collection_config_path)
    config = DescriptiveAnalysisConfig(
        analysis_id=str(payload["analysis_id"]),
        collection_config_path=collection_config_path,
        price_fields=price_fields,
        chart_fields=chart_fields,
        quantiles=quantiles,
        standard_deviation_ddof=ddof,
        kurtosis_definition=str(payload["kurtosis_definition"]),
        output_directory=repository_root / str(payload["output_directory"]),
    )
    return config, collection_config


def canonical_csv_path(
    repository_root: Path,
    collection_config: CollectionConfig,
    symbol: str,
) -> Path:
    """Resolve the single canonical raw CSV for a configured symbol."""
    symbol_directory = (
        repository_root / collection_config.output_directory / symbol
    )
    candidates = sorted(symbol_directory.glob(f"{symbol}_{collection_config.interval}_*.csv.gz"))
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"Expected one canonical CSV for {symbol}, found {len(candidates)} in "
            f"{symbol_directory}."
        )
    return candidates[0]


def load_hourly_prices(path: Path, price_fields: Sequence[str]) -> pd.DataFrame:
    """Load and validate timestamped positive finite OHLC prices."""
    requested_fields = tuple(price_fields)
    frame = pd.read_csv(
        path,
        usecols=["open_time_ms", *requested_fields],
        dtype={"open_time_ms": "int64", **dict.fromkeys(requested_fields, "string")},
    )
    timestamps = pd.to_datetime(frame.pop("open_time_ms"), unit="ms", utc=True)
    prices = frame.apply(pd.to_numeric, errors="raise").astype("float64")
    prices.index = pd.DatetimeIndex(timestamps, name="open_time_utc")

    if prices.empty:
        raise ValueError(f"{path} contains no observations.")
    if prices.index.has_duplicates:
        raise ValueError(f"{path} contains duplicate opening timestamps.")
    if not prices.index.is_monotonic_increasing:
        raise ValueError(f"{path} is not chronologically ordered.")
    timestamp_ms = prices.index.asi8 // 1_000_000
    if np.any(timestamp_ms % HOUR_MS != 0):
        raise ValueError(f"{path} contains timestamps outside UTC hourly boundaries.")
    if not np.isfinite(prices.to_numpy()).all():
        raise ValueError(f"{path} contains missing or non-finite prices.")
    if not (prices.to_numpy() > 0).all():
        raise ValueError(f"{path} contains non-positive prices.")
    if set(PRICE_FIELDS).issubset(prices.columns):
        inconsistent = (
            (prices["high"] < prices[["open", "close"]].max(axis=1))
            | (prices["low"] > prices[["open", "close"]].min(axis=1))
            | (prices["high"] < prices["low"])
        )
        if inconsistent.any():
            raise ValueError(f"{path} contains OHLC consistency violations.")
    return prices


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
        q1, median, q3 = series.quantile([0.25, 0.5, 0.75]).tolist()
        mean = series.mean()
        standard_deviation = series.std(ddof=ddof)
        rows.append(
            {
                "Symbol": symbol,
                "Price field": field,
                "Observations": int(series.count()),
                "Missing values": int(series.isna().sum()),
                "Mean (USDT)": mean,
                "Median (USDT)": median,
                "Standard deviation (USDT)": standard_deviation,
                "Variance (USDT squared)": series.var(ddof=ddof),
                "Minimum (USDT)": series.min(),
                "Q1 (USDT)": q1,
                "Q3 (USDT)": q3,
                "Maximum (USDT)": series.max(),
                "Range (USDT)": series.max() - series.min(),
                "Interquartile range (USDT)": q3 - q1,
                "Coefficient of variation (%)": 100 * standard_deviation / mean,
                "Skewness": series.skew(),
                "Excess kurtosis": series.kurt(),
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
        "Observed span (days)": (prices.index.max() - prices.index.min()).total_seconds() / 86_400,
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


def plot_symbol_open_close(
    symbol: str,
    prices: pd.DataFrame,
    output_path: Path,
) -> None:
    """Save one full-span hourly opening- and closing-price line chart."""
    figure, axis = plt.subplots(figsize=(12, 5))
    axis.plot(prices.index, prices["open"], label="Open", linewidth=0.45, alpha=0.85)
    axis.plot(prices.index, prices["close"], label="Close", linewidth=0.45, alpha=0.75)
    axis.set_title(f"{symbol} hourly opening and closing prices")
    axis.set_xlabel("Opening time (UTC)")
    axis.set_ylabel("Price (USDT)")
    date_locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
    axis.xaxis.set_major_locator(date_locator)
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(date_locator))
    axis.grid(alpha=0.2)
    axis.legend(loc="upper left")
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _write_workbook(
    path: Path,
    summary: pd.DataFrame,
    coverage: pd.DataFrame,
    extremes: pd.DataFrame,
    config: DescriptiveAnalysisConfig,
) -> None:
    """Write consolidated tables and explicit statistical definitions."""
    excel_coverage = coverage.copy()
    excel_extremes = extremes.copy()
    for column in ("First open (UTC)", "Last open (UTC)"):
        excel_coverage[column] = excel_coverage[column].map(
            lambda value: value.isoformat()
        )
    for column in ("Minimum timestamp (UTC)", "Maximum timestamp (UTC)"):
        excel_extremes[column] = excel_extremes[column].map(
            lambda value: value.isoformat()
        )

    definitions = pd.DataFrame(
        [
            ("Price unit", "USDT per unit of the base asset"),
            ("Observation frequency", "Hourly Binance Spot klines"),
            ("Standard deviation and variance", "Sample estimators with ddof=1"),
            ("Quartiles", "Pandas linear interpolation at 25%, 50%, and 75%"),
            ("Skewness", "Pandas unbiased normalized sample skewness"),
            ("Excess kurtosis", config.kurtosis_definition),
            ("Missing data", "No interpolation, forward fill, backfill, or synthesis"),
            ("Interpretation", "Price levels are non-stationary and sample spans differ by listing date"),
        ],
        columns=["Item", "Definition"],
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Price Statistics", index=False)
        excel_coverage.to_excel(writer, sheet_name="Coverage", index=False)
        excel_extremes.to_excel(writer, sheet_name="Extrema", index=False)
        definitions.to_excel(writer, sheet_name="Definitions", index=False)


def run_descriptive_analysis(
    config_path: Path,
    *,
    repository_root: Path,
) -> AnalysisArtifacts:
    """Generate descriptive tables and full-span open/close charts for all assets."""
    config, collection_config = load_analysis_config(
        config_path,
        repository_root=repository_root,
    )
    output_directory = config.output_directory
    figure_directory = output_directory / "figures" / "open_close_by_symbol"
    output_directory.mkdir(parents=True, exist_ok=True)
    figure_directory.mkdir(parents=True, exist_ok=True)

    summaries: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, object]] = []
    extremes: list[pd.DataFrame] = []
    overview_figure, overview_axes = plt.subplots(
        10,
        4,
        figsize=(24, 34),
    )
    overview_figure.subplots_adjust(
        top=0.955,
        bottom=0.025,
        hspace=0.62,
        wspace=0.22,
    )

    for axis, symbol in zip(overview_axes.flat, collection_config.symbols, strict=True):
        source_path = canonical_csv_path(repository_root, collection_config, symbol)
        prices = load_hourly_prices(source_path, config.price_fields)
        summaries.append(
            describe_price_levels(
                symbol,
                prices,
                ddof=config.standard_deviation_ddof,
            )
        )
        coverage_rows.append(describe_coverage(symbol, prices))
        extremes.append(describe_extremes(symbol, prices))
        plot_symbol_open_close(
            symbol,
            prices,
            figure_directory / f"{symbol}_hourly_open_close.png",
        )
        axis.plot(prices.index, prices["open"], label="Open", linewidth=0.3, alpha=0.85)
        axis.plot(prices.index, prices["close"], label="Close", linewidth=0.3, alpha=0.70)
        axis.set_title(symbol)
        axis.set_ylabel("USDT")
        date_locator = mdates.AutoDateLocator(minticks=3, maxticks=5)
        axis.xaxis.set_major_locator(date_locator)
        axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(date_locator))
        axis.grid(alpha=0.15)

    handles, labels = overview_axes.flat[0].get_legend_handles_labels()
    overview_figure.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.974),
        ncol=2,
    )
    overview_figure.suptitle(
        "Binance hourly opening and closing prices by trading pair",
        fontsize=18,
        y=0.994,
    )
    overview_figure_path = output_directory / "binance_hourly_open_close_overview.png"
    overview_figure.savefig(overview_figure_path, dpi=150, bbox_inches="tight")
    plt.close(overview_figure)

    summary = pd.concat(summaries, ignore_index=True)
    coverage = pd.DataFrame(coverage_rows)
    extremes_table = pd.concat(extremes, ignore_index=True)
    summary_csv = output_directory / "price_level_statistics.csv"
    coverage_csv = output_directory / "price_series_coverage.csv"
    extremes_csv = output_directory / "price_level_extrema.csv"
    workbook = output_directory / "binance_hourly_price_descriptive_analysis.xlsx"
    summary.to_csv(summary_csv, index=False)
    coverage.to_csv(coverage_csv, index=False)
    extremes_table.to_csv(extremes_csv, index=False)
    _write_workbook(workbook, summary, coverage, extremes_table, config)

    return AnalysisArtifacts(
        summary=summary,
        coverage=coverage,
        extremes=extremes_table,
        summary_csv=summary_csv,
        coverage_csv=coverage_csv,
        extremes_csv=extremes_csv,
        workbook=workbook,
        overview_figure=overview_figure_path,
        individual_figure_directory=figure_directory,
    )
