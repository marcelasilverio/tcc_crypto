"""Describe and visualize canonical Binance hourly trading activity."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tcc_crypto.binance_hourly_collection import CollectionConfig, load_collection_config
from tcc_crypto.hourly_price_descriptive_analysis import (
    canonical_csv_path,
    describe_coverage,
)

ACTIVITY_FIELDS = (
    "base_asset_volume",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
)
HOUR_MS = 60 * 60 * 1000


@dataclass(frozen=True)
class MarketActivityAnalysisConfig:
    """Validated settings for the hourly market-activity analysis."""

    analysis_id: str
    collection_config_path: Path
    activity_fields: tuple[str, ...]
    quantiles: tuple[float, ...]
    standard_deviation_ddof: int
    kurtosis_definition: str
    output_directory: Path


@dataclass(frozen=True)
class MarketActivityArtifacts:
    """Paths and in-memory tables produced by the activity analysis."""

    summary: pd.DataFrame
    coverage: pd.DataFrame
    extremes: pd.DataFrame
    summary_csv: Path
    coverage_csv: Path
    extremes_csv: Path
    quote_volume_overview: Path
    trade_count_overview: Path
    individual_figure_directory: Path


def load_market_activity_config(
    path: Path,
    *,
    repository_root: Path,
) -> tuple[MarketActivityAnalysisConfig, CollectionConfig]:
    """Load activity-analysis settings and the collection they reference."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)

    activity_fields = tuple(str(field) for field in payload["activity_fields"])
    if activity_fields != ACTIVITY_FIELDS:
        raise ValueError(
            "activity_fields must contain the five canonical Binance activity fields "
            "in their approved order."
        )
    quantiles = tuple(float(value) for value in payload["quantiles"])
    if quantiles != (0.25, 0.5, 0.75):
        raise ValueError("This analysis requires quartiles 0.25, 0.50, and 0.75.")
    ddof = int(payload["standard_deviation_ddof"])
    if ddof != 1:
        raise ValueError("The descriptive analysis uses sample variance (ddof=1).")

    collection_config_path = repository_root / str(payload["collection_config"])
    collection_config = load_collection_config(collection_config_path)
    config = MarketActivityAnalysisConfig(
        analysis_id=str(payload["analysis_id"]),
        collection_config_path=collection_config_path,
        activity_fields=activity_fields,
        quantiles=quantiles,
        standard_deviation_ddof=ddof,
        kurtosis_definition=str(payload["kurtosis_definition"]),
        output_directory=repository_root / str(payload["output_directory"]),
    )
    return config, collection_config


def load_hourly_market_activity(
    path: Path,
    activity_fields: Sequence[str] = ACTIVITY_FIELDS,
) -> pd.DataFrame:
    """Load and validate timestamped non-negative hourly activity fields."""
    requested_fields = tuple(activity_fields)
    frame = pd.read_csv(
        path,
        usecols=["open_time_ms", *requested_fields],
        dtype={
            "open_time_ms": "int64",
            **dict.fromkeys(requested_fields, "string"),
        },
    )
    timestamps = pd.to_datetime(frame.pop("open_time_ms"), unit="ms", utc=True)
    activity = frame.apply(pd.to_numeric, errors="raise").astype("float64")
    activity.index = pd.DatetimeIndex(timestamps, name="open_time_utc")

    if activity.empty:
        raise ValueError(f"{path} contains no observations.")
    if activity.index.has_duplicates:
        raise ValueError(f"{path} contains duplicate opening timestamps.")
    if not activity.index.is_monotonic_increasing:
        raise ValueError(f"{path} is not chronologically ordered.")
    timestamp_ms = activity.index.asi8 // 1_000_000
    if np.any(timestamp_ms % HOUR_MS != 0):
        raise ValueError(f"{path} contains timestamps outside UTC hourly boundaries.")
    if not np.isfinite(activity.to_numpy()).all():
        raise ValueError(f"{path} contains missing or non-finite activity values.")
    if (activity.to_numpy() < 0).any():
        raise ValueError(f"{path} contains negative activity values.")
    if "number_of_trades" in activity:
        trade_counts = activity["number_of_trades"]
        if not np.equal(trade_counts, np.floor(trade_counts)).all():
            raise ValueError(f"{path} contains non-integer trade counts.")
    if {"base_asset_volume", "taker_buy_base_asset_volume"}.issubset(activity):
        if (activity["taker_buy_base_asset_volume"] > activity["base_asset_volume"]).any():
            raise ValueError(f"{path} contains taker-buy base volume above total volume.")
    if {"quote_asset_volume", "taker_buy_quote_asset_volume"}.issubset(activity):
        if (activity["taker_buy_quote_asset_volume"] > activity["quote_asset_volume"]).any():
            raise ValueError(f"{path} contains taker-buy quote volume above total volume.")
    return activity


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
        q1, median, q3 = series.quantile([0.25, 0.5, 0.75]).tolist()
        mean = series.mean()
        standard_deviation = series.std(ddof=ddof)
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
                "Variance per hour": series.var(ddof=ddof),
                "Minimum per hour": series.min(),
                "Q1 per hour": q1,
                "Q3 per hour": q3,
                "Maximum per hour": series.max(),
                "Range per hour": series.max() - series.min(),
                "Interquartile range per hour": q3 - q1,
                "Coefficient of variation (%)": (
                    100 * standard_deviation / mean if mean != 0 else np.nan
                ),
                "Skewness": series.skew(),
                "Excess kurtosis": series.kurt(),
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


def _configure_time_axis(axis: plt.Axes, *, maximum_ticks: int) -> None:
    locator = mdates.AutoDateLocator(minticks=3, maxticks=maximum_ticks)
    axis.xaxis.set_major_locator(locator)
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    axis.grid(alpha=0.2)


def plot_symbol_activity(
    symbol: str,
    activity: pd.DataFrame,
    output_path: Path,
) -> None:
    """Save base-volume, quote-volume, and trade-count panels for one asset."""
    base_asset = activity_unit(symbol, "base_asset_volume")
    figure, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    axes[0].plot(activity.index, activity["base_asset_volume"], label="Total", linewidth=0.45)
    axes[0].plot(
        activity.index,
        activity["taker_buy_base_asset_volume"],
        label="Taker buy",
        linewidth=0.4,
        alpha=0.8,
    )
    axes[0].set_ylabel(f"Volume ({base_asset})")
    axes[0].legend(loc="upper right")

    axes[1].plot(activity.index, activity["quote_asset_volume"], label="Total", linewidth=0.45)
    axes[1].plot(
        activity.index,
        activity["taker_buy_quote_asset_volume"],
        label="Taker buy",
        linewidth=0.4,
        alpha=0.8,
    )
    axes[1].set_ylabel("Volume (USDT)")
    axes[1].legend(loc="upper right")

    axes[2].plot(activity.index, activity["number_of_trades"], linewidth=0.45)
    axes[2].set_ylabel("Number of trades")
    axes[2].set_xlabel("Opening time (UTC)")
    for axis in axes:
        _configure_time_axis(axis, maximum_ticks=7)
    figure.suptitle(f"{symbol} hourly trading activity")
    figure.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(figure)


def _prepare_overview(title: str) -> tuple[plt.Figure, np.ndarray]:
    figure, axes = plt.subplots(10, 4, figsize=(24, 34))
    figure.subplots_adjust(top=0.97, bottom=0.025, hspace=0.62, wspace=0.22)
    figure.suptitle(title, fontsize=18, y=0.992)
    return figure, axes


def run_market_activity_analysis(
    config_path: Path,
    *,
    repository_root: Path,
) -> MarketActivityArtifacts:
    """Generate activity tables and hourly charts for every configured asset."""
    config, collection_config = load_market_activity_config(
        config_path,
        repository_root=repository_root,
    )
    output_directory = config.output_directory
    figure_directory = output_directory / "figures" / "activity_by_symbol"
    output_directory.mkdir(parents=True, exist_ok=True)
    figure_directory.mkdir(parents=True, exist_ok=True)

    summaries: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, object]] = []
    extremes: list[pd.DataFrame] = []
    quote_figure, quote_axes = _prepare_overview(
        "Binance hourly quote-asset volume by trading pair"
    )
    trades_figure, trades_axes = _prepare_overview(
        "Binance hourly number of trades by trading pair"
    )

    for quote_axis, trades_axis, symbol in zip(
        quote_axes.flat,
        trades_axes.flat,
        collection_config.symbols,
        strict=True,
    ):
        source_path = canonical_csv_path(repository_root, collection_config, symbol)
        activity = load_hourly_market_activity(source_path, config.activity_fields)
        summaries.append(
            describe_market_activity(
                symbol,
                activity,
                ddof=config.standard_deviation_ddof,
            )
        )
        coverage_rows.append(describe_coverage(symbol, activity))
        extremes.append(describe_activity_extremes(symbol, activity))
        plot_symbol_activity(
            symbol,
            activity,
            figure_directory / f"{symbol}_hourly_activity.png",
        )

        quote_axis.plot(
            activity.index,
            activity["quote_asset_volume"],
            linewidth=0.35,
            color="#1f77b4",
        )
        quote_axis.set_title(symbol)
        quote_axis.set_ylabel("USDT")
        _configure_time_axis(quote_axis, maximum_ticks=5)

        trades_axis.plot(
            activity.index,
            activity["number_of_trades"],
            linewidth=0.35,
            color="#d97706",
        )
        trades_axis.set_title(symbol)
        trades_axis.set_ylabel("Trades")
        _configure_time_axis(trades_axis, maximum_ticks=5)

    quote_overview = output_directory / "binance_hourly_quote_volume_overview.png"
    trade_overview = output_directory / "binance_hourly_trade_count_overview.png"
    quote_figure.savefig(quote_overview, dpi=150, bbox_inches="tight")
    trades_figure.savefig(trade_overview, dpi=150, bbox_inches="tight")
    plt.close(quote_figure)
    plt.close(trades_figure)

    summary = pd.concat(summaries, ignore_index=True)
    coverage = pd.DataFrame(coverage_rows)
    extremes_table = pd.concat(extremes, ignore_index=True)
    summary_csv = output_directory / "market_activity_statistics.csv"
    coverage_csv = output_directory / "market_activity_coverage.csv"
    extremes_csv = output_directory / "market_activity_extrema.csv"
    summary.to_csv(summary_csv, index=False)
    coverage.to_csv(coverage_csv, index=False)
    extremes_table.to_csv(extremes_csv, index=False)

    return MarketActivityArtifacts(
        summary=summary,
        coverage=coverage,
        extremes=extremes_table,
        summary_csv=summary_csv,
        coverage_csv=coverage_csv,
        extremes_csv=extremes_csv,
        quote_volume_overview=quote_overview,
        trade_count_overview=trade_overview,
        individual_figure_directory=figure_directory,
    )
