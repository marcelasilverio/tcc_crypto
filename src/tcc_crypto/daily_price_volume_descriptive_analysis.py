"""Prepare daily Binance price and USDT-volume descriptive analyses."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd

from tcc_crypto.binance_kline_collection import CollectionConfig, load_collection_config

PRICE_FIELDS = ("open", "high", "low", "close")
VOLUME_FIELD = "quote_asset_volume"
DAY_MS = 24 * 60 * 60 * 1000


@dataclass(frozen=True)
class DailyPriceVolumeAnalysisConfig:
    """Validated settings for the daily price and USDT-volume analysis."""

    analysis_id: str
    collection_config_path: Path
    analysis_start_utc: pd.Timestamp
    analysis_end_utc: pd.Timestamp
    price_fields: tuple[str, ...]
    volume_field: str
    quantiles: tuple[float, ...]
    standard_deviation_ddof: int
    kurtosis_definition: str
    semester_time_zone: str
    output_directory: Path
    figure_rows: int
    figure_columns: int
    price_figure_transform: str
    volume_figure_scale: str
    price_figure_filename: str
    volume_figure_filename: str


@dataclass(frozen=True)
class DailySmallMultipleArtifacts:
    """Paths to the two cross-pair daily small-multiple figures."""

    natural_log_open_close_figure: Path
    quote_volume_figure: Path


def load_analysis_config(
    path: Path,
    *,
    repository_root: Path,
) -> tuple[DailyPriceVolumeAnalysisConfig, CollectionConfig]:
    """Load the analysis settings and referenced daily collection settings."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)

    price_fields = tuple(str(field) for field in payload["price_fields"])
    if price_fields != PRICE_FIELDS:
        raise ValueError(f"price_fields must be exactly {PRICE_FIELDS}.")
    volume_field = str(payload["volume_field"])
    if volume_field != VOLUME_FIELD:
        raise ValueError(f"volume_field must be {VOLUME_FIELD!r}.")
    quantiles = tuple(float(value) for value in payload["quantiles"])
    if quantiles != (0.25, 0.5, 0.75):
        raise ValueError("This analysis requires quartiles 0.25, 0.50, and 0.75.")
    ddof = int(payload["standard_deviation_ddof"])
    if ddof != 1:
        raise ValueError("The descriptive analysis uses sample variance (ddof=1).")
    if str(payload["semester_time_zone"]) != "UTC":
        raise ValueError("Semester boundaries must use UTC.")

    analysis_start = pd.Timestamp(payload["analysis_start_utc"])
    analysis_end = pd.Timestamp(payload["analysis_end_utc"])
    if analysis_start.tzinfo is None or analysis_end.tzinfo is None:
        raise ValueError("Analysis boundaries must be timezone-aware.")
    analysis_start = analysis_start.tz_convert("UTC")
    analysis_end = analysis_end.tz_convert("UTC")
    if analysis_start > analysis_end:
        raise ValueError("analysis_start_utc must not follow analysis_end_utc.")

    collection_path = repository_root / str(payload["collection_config"])
    collection_config = load_collection_config(collection_path)
    if collection_config.interval != "1d":
        raise ValueError("The referenced collection must use daily (1d) klines.")
    if collection_config.quote_asset != "USDT":
        raise ValueError("The referenced collection must contain USDT-quoted pairs.")

    figure_rows = int(payload["figure_rows"])
    figure_columns = int(payload["figure_columns"])
    if figure_rows <= 0 or figure_columns <= 0:
        raise ValueError("Figure rows and columns must be positive integers.")
    if figure_rows * figure_columns != len(collection_config.symbols):
        raise ValueError("The figure grid must contain exactly one panel per symbol.")
    if str(payload["price_figure_transform"]) != "natural_log":
        raise ValueError("The price figure must use the natural-log transformation.")
    if str(payload["volume_figure_scale"]) != "linear":
        raise ValueError("The quote-volume figure must use a linear scale.")

    config = DailyPriceVolumeAnalysisConfig(
        analysis_id=str(payload["analysis_id"]),
        collection_config_path=collection_path,
        analysis_start_utc=analysis_start,
        analysis_end_utc=analysis_end,
        price_fields=price_fields,
        volume_field=volume_field,
        quantiles=quantiles,
        standard_deviation_ddof=ddof,
        kurtosis_definition=str(payload["kurtosis_definition"]),
        semester_time_zone="UTC",
        output_directory=repository_root / str(payload["output_directory"]),
        figure_rows=figure_rows,
        figure_columns=figure_columns,
        price_figure_transform="natural_log",
        volume_figure_scale="linear",
        price_figure_filename=str(payload["price_figure_filename"]),
        volume_figure_filename=str(payload["volume_figure_filename"]),
    )
    return config, collection_config


def canonical_csv_path(
    repository_root: Path,
    collection_config: CollectionConfig,
    symbol: str,
) -> Path:
    """Resolve the single canonical raw daily CSV for one configured symbol."""
    symbol_directory = repository_root / collection_config.output_directory / symbol
    candidates = sorted(
        symbol_directory.glob(f"{symbol}_{collection_config.interval}_*.csv.gz")
    )
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"Expected one canonical CSV for {symbol}, found {len(candidates)} in "
            f"{symbol_directory}."
        )
    return candidates[0]


def load_daily_price_volume(
    path: Path,
    price_fields: Sequence[str] = PRICE_FIELDS,
    volume_field: str = VOLUME_FIELD,
) -> pd.DataFrame:
    """Load and validate daily OHLC prices and non-negative USDT volume."""
    requested_prices = tuple(price_fields)
    frame = pd.read_csv(
        path,
        usecols=["open_time_ms", *requested_prices, volume_field],
        dtype={
            "open_time_ms": "int64",
            **dict.fromkeys((*requested_prices, volume_field), "string"),
        },
    )
    timestamps = pd.to_datetime(frame.pop("open_time_ms"), unit="ms", utc=True)
    values = frame.apply(pd.to_numeric, errors="raise").astype("float64")
    values.index = pd.DatetimeIndex(timestamps, name="open_time_utc")

    if values.empty:
        raise ValueError(f"{path} contains no observations.")
    if values.index.has_duplicates:
        raise ValueError(f"{path} contains duplicate opening timestamps.")
    if not values.index.is_monotonic_increasing:
        raise ValueError(f"{path} is not chronologically ordered.")
    timestamp_ms = values.index.asi8 // 1_000_000
    if np.any(timestamp_ms % DAY_MS != 0):
        raise ValueError(f"{path} contains timestamps outside UTC daily boundaries.")
    if not np.isfinite(values.to_numpy()).all():
        raise ValueError(f"{path} contains missing or non-finite analyzed values.")
    if not (values.loc[:, requested_prices].to_numpy() > 0).all():
        raise ValueError(f"{path} contains non-positive prices.")
    if (values[volume_field] < 0).any():
        raise ValueError(f"{path} contains negative quote-asset volume.")

    inconsistent = (
        (values["high"] < values[["open", "close"]].max(axis=1))
        | (values["low"] > values[["open", "close"]].min(axis=1))
        | (values["high"] < values["low"])
    )
    if inconsistent.any():
        raise ValueError(f"{path} contains OHLC consistency violations.")
    return values


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


def _configure_small_multiple_axis(
    axis: plt.Axes,
    *,
    symbol: str,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
) -> None:
    """Apply consistent, compact styling to one time-series panel."""
    axis.set_title(symbol, fontsize=9, fontweight="bold", pad=3)
    axis.set_xlim(start_utc.to_pydatetime(), end_utc.to_pydatetime())
    axis.xaxis.set_major_locator(mdates.YearLocator(2))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axis.yaxis.set_major_locator(MaxNLocator(nbins=3))
    axis.tick_params(axis="both", labelsize=7)
    axis.grid(alpha=0.18, linewidth=0.4)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


def create_daily_small_multiple_figures(
    config_path: Path,
    *,
    repository_root: Path,
) -> DailySmallMultipleArtifacts:
    """Create 40-panel daily price-log and quote-volume figures."""
    config, collection_config = load_analysis_config(
        config_path,
        repository_root=repository_root,
    )
    figure_directory = config.output_directory / "figures"
    figure_directory.mkdir(parents=True, exist_ok=True)

    price_figure, price_axes = plt.subplots(
        config.figure_rows,
        config.figure_columns,
        figsize=(24, 30),
        sharex=True,
    )
    volume_figure, volume_axes = plt.subplots(
        config.figure_rows,
        config.figure_columns,
        figsize=(24, 30),
        sharex=True,
    )

    for price_axis, volume_axis, symbol in zip(
        price_axes.flat,
        volume_axes.flat,
        collection_config.symbols,
        strict=True,
    ):
        source_path = canonical_csv_path(repository_root, collection_config, symbol)
        source_values = load_daily_price_volume(
            source_path,
            config.price_fields,
            config.volume_field,
        )
        values = filter_analysis_window(
            source_values,
            config.analysis_start_utc,
            config.analysis_end_utc,
        )
        logged_prices = natural_log_open_close(values)
        quote_volume_billions = daily_quote_volume_billions(values)

        price_axis.plot(
            logged_prices.index,
            logged_prices["open"],
            color="#1f77b4",
            linewidth=0.55,
            label="Open",
        )
        price_axis.plot(
            logged_prices.index,
            logged_prices["close"],
            color="#d97706",
            linewidth=0.45,
            alpha=0.85,
            label="Close",
        )
        _configure_small_multiple_axis(
            price_axis,
            symbol=symbol,
            start_utc=config.analysis_start_utc,
            end_utc=config.analysis_end_utc,
        )

        volume_axis.plot(
            quote_volume_billions.index,
            quote_volume_billions,
            color="#1f77b4",
            linewidth=0.55,
        )
        volume_axis.set_ylim(bottom=0)
        _configure_small_multiple_axis(
            volume_axis,
            symbol=symbol,
            start_utc=config.analysis_start_utc,
            end_utc=config.analysis_end_utc,
        )

    price_figure.legend(
        *price_axes.flat[0].get_legend_handles_labels(),
        loc="upper center",
        bbox_to_anchor=(0.5, 0.972),
        ncol=2,
        frameon=False,
    )
    price_figure.suptitle(
        "Binance daily opening and closing prices by trading pair",
        fontsize=20,
        y=0.992,
    )
    price_figure.text(
        0.5,
        0.977,
        "Natural logarithm applied pointwise; independent y-axis per pair; gaps remain unfilled",
        ha="center",
        fontsize=10,
    )
    price_figure.supxlabel("Daily candle opening date (UTC)", fontsize=11)
    price_figure.supylabel(
        "Natural log price: ln(USDT per base-asset unit)",
        fontsize=11,
    )
    price_figure.subplots_adjust(
        top=0.955,
        bottom=0.045,
        left=0.06,
        right=0.985,
        hspace=0.48,
        wspace=0.24,
    )

    volume_figure.suptitle(
        "Binance daily USDT quote volume by trading pair",
        fontsize=20,
        y=0.992,
    )
    volume_figure.text(
        0.5,
        0.977,
        "Linear scale in billions of USDT; independent y-axis per pair; gaps remain unfilled",
        ha="center",
        fontsize=10,
    )
    volume_figure.supxlabel("Daily candle opening date (UTC)", fontsize=11)
    volume_figure.supylabel("Daily quote volume (USDT billions)", fontsize=11)
    volume_figure.subplots_adjust(
        top=0.955,
        bottom=0.045,
        left=0.06,
        right=0.985,
        hspace=0.48,
        wspace=0.24,
    )

    price_path = figure_directory / config.price_figure_filename
    volume_path = figure_directory / config.volume_figure_filename
    price_figure.savefig(price_path, dpi=180, facecolor="white")
    volume_figure.savefig(volume_path, dpi=180, facecolor="white")
    plt.close(price_figure)
    plt.close(volume_figure)
    return DailySmallMultipleArtifacts(
        natural_log_open_close_figure=price_path,
        quote_volume_figure=volume_path,
    )


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
    q1, median, q3 = series.quantile([0.25, 0.5, 0.75], interpolation="linear").tolist()
    mean = series.mean()
    standard_deviation = series.std(ddof=ddof)
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
        "Sample variance": series.var(ddof=ddof),
        "Minimum": series.min(),
        "Q1": q1,
        "Q3": q3,
        "Maximum": series.max(),
        "Range": series.max() - series.min(),
        "Interquartile range": q3 - q1,
        "Coefficient of variation": standard_deviation / mean if mean != 0 else np.nan,
        "Skewness": series.skew(),
        "Excess kurtosis": series.kurt(),
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


def definition_rows(config: DailyPriceVolumeAnalysisConfig) -> list[dict[str, str]]:
    """Return concise workbook definitions and interpretation limits."""
    definitions = [
        ("Open", "First traded price recorded in the daily Binance Spot candle."),
        ("High", "Highest traded price recorded in the daily candle."),
        ("Low", "Lowest traded price recorded in the daily candle."),
        ("Close", "Last traded price recorded in the daily candle."),
        (
            "Quote asset volume",
            "Total exchange-reported daily trading volume expressed in USDT.",
        ),
        ("Observations", "Number of observed daily candles used in the calculation."),
        (
            "Missing values",
            "Observed rows with a missing analyzed value; source validation requires zero.",
        ),
        (
            "Missing daily openings",
            "Expected UTC dates absent inside the observed span; gaps are not filled.",
        ),
        (
            "Zero observations",
            "Number of daily USDT-volume observations equal to zero.",
        ),
        (
            "Zero share",
            "Zero-volume observations divided by all observed candles in the period.",
        ),
        ("Total", "Sum of daily quote-asset volume in USDT; reported only for volume."),
        ("Mean", "Arithmetic average of the observed values."),
        (
            "Median",
            "50th percentile; half the observations are at or below this value.",
        ),
        (
            "Sample standard deviation",
            "Sample dispersion around the mean, calculated with ddof=1.",
        ),
        (
            "Sample variance",
            "Square of the sample standard deviation, calculated with ddof=1.",
        ),
        ("Minimum", "Smallest observed value in the specified period."),
        ("Q1", "25th percentile using linear interpolation."),
        ("Q3", "75th percentile using linear interpolation."),
        ("Maximum", "Largest observed value in the specified period."),
        ("Range", "Maximum minus minimum."),
        (
            "Interquartile range",
            "Q3 minus Q1; spread of the central 50% of observations.",
        ),
        (
            "Coefficient of variation",
            "Sample standard deviation divided by the arithmetic mean.",
        ),
        (
            "Skewness",
            "Unbiased normalized sample skewness; positive values indicate a longer right tail.",
        ),
        (
            "Excess kurtosis",
            config.kurtosis_definition
            + "; zero corresponds to normal-distribution kurtosis.",
        ),
        (
            "Semester",
            "UTC calendar semester: H1 is January-June and H2 is July-December.",
        ),
        (
            "Partial semester",
            "A semester without observations covering both nominal UTC calendar-semester boundaries.",
        ),
        (
            "Missing-data treatment",
            "No interpolation, forward fill, backfill, or synthetic observations.",
        ),
        (
            "Listing treatment",
            "Each pair begins on 2019-07-01 UTC or its later first Binance candle.",
        ),
        (
            "Interpretation",
            "Price levels are non-stationary and coverage differs by listing date; these statistics are not return or risk estimates.",
        ),
        (
            "Volume limitation",
            "Kline volume is aggregated exchange-reported activity, not transaction-level data.",
        ),
    ]
    return [
        {"Item": item, "Definition": definition} for item, definition in definitions
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {column: _json_value(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def build_pair_payload(
    symbol: str,
    values: pd.DataFrame,
    *,
    source_path: Path,
    repository_root: Path,
    config: DailyPriceVolumeAnalysisConfig,
) -> dict[str, Any]:
    """Build one JSON-serializable workbook payload for a trading pair."""
    coverage = describe_coverage(symbol, values)
    overall = describe_statistics(values, ddof=config.standard_deviation_ddof)
    semesters = describe_semesters(
        values,
        analysis_start_utc=config.analysis_start_utc,
        analysis_end_utc=config.analysis_end_utc,
        ddof=config.standard_deviation_ddof,
    )
    extrema = describe_extrema(symbol, values)
    chart_data = values[["open", "close", VOLUME_FIELD]].reset_index()
    chart_data["open_time_utc"] = chart_data["open_time_utc"].dt.strftime("%Y-%m-%d")
    relative_source = source_path.relative_to(repository_root).as_posix()
    return {
        "analysis_id": config.analysis_id,
        "symbol": symbol,
        "source": {
            "relative_path": relative_source,
            "sha256": _sha256(source_path),
        },
        "configured_start_utc": config.analysis_start_utc.isoformat(),
        "configured_end_utc": config.analysis_end_utc.isoformat(),
        "coverage": {key: _json_value(value) for key, value in coverage.items()},
        "overall_statistics": _records(overall),
        "semester_statistics": _records(semesters),
        "extrema": _records(extrema),
        "chart_data": _records(chart_data),
        "definitions": definition_rows(config),
    }


def prepare_analysis_packets(
    config_path: Path,
    *,
    repository_root: Path,
    packet_directory: Path,
) -> pd.DataFrame:
    """Validate all configured pairs and write one workbook-input JSON per pair."""
    config, collection_config = load_analysis_config(
        config_path,
        repository_root=repository_root,
    )
    packet_directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for symbol in collection_config.symbols:
        source_path = canonical_csv_path(repository_root, collection_config, symbol)
        source_values = load_daily_price_volume(
            source_path,
            config.price_fields,
            config.volume_field,
        )
        values = filter_analysis_window(
            source_values,
            config.analysis_start_utc,
            config.analysis_end_utc,
        )
        payload = build_pair_payload(
            symbol,
            values,
            source_path=source_path,
            repository_root=repository_root,
            config=config,
        )
        packet_path = packet_directory / f"{symbol}.json"
        packet_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        rows.append(
            {
                "Symbol": symbol,
                "Status": "PREPARED",
                "Observations": payload["coverage"]["Observations"],
                "First open (UTC)": payload["coverage"]["First open (UTC)"],
                "Last open (UTC)": payload["coverage"]["Last open (UTC)"],
                "Missing daily openings": payload["coverage"][
                    "Missing daily openings within observed span"
                ],
                "Packet": str(packet_path),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    """Prepare workbook-input packets from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--packet-directory", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare_analysis_packets(
        args.config,
        repository_root=args.repository_root,
        packet_directory=args.packet_directory,
    )
    print(manifest.to_string(index=False))


if __name__ == "__main__":
    main()
