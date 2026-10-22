"""Reusable exploratory figures and readable result previews."""

from __future__ import annotations

from math import ceil
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.reporting.tables import ensure_writable


def hourly_overviews(
    values: dict[str, pd.DataFrame], *, activity: bool
) -> dict[str, plt.Figure]:
    """Construct a panel per symbol in configured order, using observed timestamps."""
    fields = (
        [
            ("quote_asset_volume", "Hourly quote volume", "USDT"),
            ("number_of_trades", "Hourly number of trades", "Trades"),
        ]
        if activity
        else [
            ("prices", "Hourly opening and closing prices", "USDT per base-asset unit")
        ]
    )
    result = {}
    columns = min(4, len(values))
    for key, title, unit in fields:
        figure, axes = plt.subplots(
            ceil(len(values) / columns),
            columns,
            squeeze=False,
            figsize=(6 * columns, max(5, 3.4 * ceil(len(values) / columns))),
        )
        for axis, (symbol, frame) in zip(axes.flat, values.items()):
            for field in ["open", "close"] if key == "prices" else [key]:
                axis.plot(frame.index, frame[field], linewidth=0.45, label=field)
            axis.set_title(symbol)
            axis.set_ylabel(unit)
            axis.grid(alpha=0.15)
            locator = mdates.AutoDateLocator(minticks=3, maxticks=5)
            axis.xaxis.set_major_locator(locator)
            axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        for axis in list(axes.flat)[len(values) :]:
            axis.set_visible(False)
        figure.suptitle(f"Binance {title.lower()} by trading pair")
        if key == "prices":
            handles, labels = axes.flat[0].get_legend_handles_labels()
            figure.legend(
                handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.94), ncol=2
            )
        figure.supxlabel("Candle opening time (UTC)")
        figure.tight_layout(rect=(0, 0, 1, 0.88 if key == "prices" else 0.97))
        result[key] = figure
    return result


def hourly_symbol_figures(
    values: dict[str, pd.DataFrame], *, activity: bool
) -> dict[str, plt.Figure]:
    result = {}
    for symbol, frame in values.items():
        fields = list(frame.columns) if activity else ["open", "close"]
        figure, axes = plt.subplots(
            len(fields) if activity else 1,
            1,
            squeeze=False,
            figsize=(12, 3 * len(fields) if activity else 5),
        )
        for position, field in enumerate(fields):
            axis = axes.flat[position if activity else 0]
            axis.plot(frame.index, frame[field], label=field, linewidth=0.45)
            axis.set_ylabel(
                "Trades"
                if field == "number_of_trades"
                else "Base-asset units"
                if "base_asset" in field
                else "USDT"
            )
            axis.legend()
            axis.grid(alpha=0.2)
        figure.suptitle(
            f"{symbol} hourly "
            + ("market activity" if activity else "opening and closing prices")
        )
        figure.supxlabel("Candle opening time (UTC)")
        figure.tight_layout()
        result[symbol] = figure
    return result


def correlation_heatmap(matrix: pd.DataFrame, *, title: str) -> plt.Figure:
    figure, axis = plt.subplots(
        figsize=(max(7, len(matrix) * 0.55), max(6, len(matrix) * 0.5))
    )
    image = axis.imshow(matrix.to_numpy(), cmap="coolwarm", vmin=-1, vmax=1)
    axis.set_xticks(range(len(matrix)), matrix.columns, rotation=90)
    axis.set_yticks(range(len(matrix)), matrix.index)
    axis.set_title(title)
    figure.colorbar(image, ax=axis, label="Pearson correlation coefficient")
    figure.tight_layout()
    return figure


def feature_frequency_overview(frequency: pd.DataFrame) -> pd.DataFrame:
    return (
        frequency.groupby(["feature", "window_size"])["selection_rate"]
        .mean()
        .unstack("window_size")
        .reindex(ACTIVE_FEATURES)
    )


def feature_frequency_heatmap(frequency: pd.DataFrame) -> plt.Figure:
    overview = feature_frequency_overview(frequency)
    figure, axis = plt.subplots(figsize=(8, max(7, 0.35 * len(overview))))
    image = axis.imshow(
        overview.to_numpy(), aspect="auto", vmin=0, vmax=1, cmap="viridis"
    )
    axis.set_xticks(range(len(overview.columns)), overview.columns)
    axis.set_yticks(range(len(overview)), overview.index)
    axis.set_xlabel("Training window (daily observations)")
    axis.set_title("Mean feature-selection rate across ready assets")
    figure.colorbar(image, ax=axis, label="Selection rate")
    figure.tight_layout()
    return figure


def save_figures(
    figures: dict[str, plt.Figure], directory: Path, *, overwrite: bool = False
) -> dict[str, Path]:
    paths = {name: directory / (name + ".png") for name in figures}
    ensure_writable(list(paths.values()), overwrite=overwrite)
    directory.mkdir(parents=True, exist_ok=True)
    for name, figure in figures.items():
        figure.savefig(paths[name], dpi=150, bbox_inches="tight")
    return paths


def preview_table(frame: pd.DataFrame, *, rows: int = 10) -> pd.DataFrame:
    """Select a manageable preview without hiding full saved tables."""
    return frame.head(rows)
