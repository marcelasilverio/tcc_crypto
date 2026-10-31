"""Figures for daily descriptive analysis; filesystem effects belong to reporting."""

from __future__ import annotations

from math import ceil

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator

from tcc_crypto.analysis.daily_descriptive import (
    daily_quote_volume_billions,
    natural_log_open_close,
)
from tcc_crypto.analysis.daily_descriptive_config import DailyPriceVolumeAnalysisConfig


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


def daily_small_multiples(
    values_by_symbol: dict[str, pd.DataFrame], config: DailyPriceVolumeAnalysisConfig
) -> dict[str, plt.Figure]:
    """Build figures from already validated observed values; never load or save."""
    columns = min(config.figure_columns, len(values_by_symbol))
    rows = ceil(len(values_by_symbol) / columns)
    price_figure, price_axes = plt.subplots(
        rows,
        columns,
        figsize=(max(12, 4.8 * columns), max(6, 3.75 * rows)),
        sharex=True,
        squeeze=False,
    )
    volume_figure, volume_axes = plt.subplots(
        rows,
        columns,
        figsize=(max(12, 4.8 * columns), max(6, 3.75 * rows)),
        sharex=True,
        squeeze=False,
    )

    for price_axis, volume_axis, symbol in zip(
        price_axes.flat,
        volume_axes.flat,
        values_by_symbol,
    ):
        values = values_by_symbol[symbol]
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

    for axis in (
        list(price_axes.flat)[len(values_by_symbol) :]
        + list(volume_axes.flat)[len(values_by_symbol) :]
    ):
        axis.set_visible(False)
    price_figure.legend(
        *price_axes.flat[0].get_legend_handles_labels(),
        loc="upper center",
        bbox_to_anchor=(0.5, 0.972 if rows >= 4 else 0.86),
        ncol=2,
        frameon=False,
    )
    price_figure.suptitle(
        "Binance daily opening and closing prices by trading pair",
        fontsize=20,
        y=0.992 if rows >= 4 else 0.985,
    )
    price_figure.text(
        0.5,
        0.977 if rows >= 4 else 0.925,
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
        top=0.955 if rows >= 4 else 0.74,
        bottom=0.045 if rows >= 4 else 0.12,
        left=0.06,
        right=0.985,
        hspace=0.48,
        wspace=0.24,
    )

    volume_figure.suptitle(
        "Binance daily USDT quote volume by trading pair",
        fontsize=20,
        y=0.992 if rows >= 4 else 0.985,
    )
    volume_figure.text(
        0.5,
        0.977 if rows >= 4 else 0.925,
        "Linear scale in billions of USDT; independent y-axis per pair; gaps remain unfilled",
        ha="center",
        fontsize=10,
    )
    volume_figure.supxlabel("Daily candle opening date (UTC)", fontsize=11)
    volume_figure.supylabel("Daily quote volume (USDT billions)", fontsize=11)
    volume_figure.subplots_adjust(
        top=0.955 if rows >= 4 else 0.74,
        bottom=0.045 if rows >= 4 else 0.12,
        left=0.06,
        right=0.985,
        hspace=0.48,
        wspace=0.24,
    )

    return {"daily_ln_open_close": price_figure, "daily_quote_volume": volume_figure}
