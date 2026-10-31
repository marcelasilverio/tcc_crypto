"""Reproducible exploratory symbol selection."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from tcc_crypto.analysis.future_high_config import FutureHighReturnConfig
from tcc_crypto.data.exploratory import load_daily_open_high
from tcc_crypto.data.loaders import find_symbol_csv
from tcc_crypto.targets.future_high import calculate_future_high_returns


def symbols_observed_on_date(
    symbols: Iterable[str], raw_directory: Path, date_utc: pd.Timestamp
) -> tuple[str, ...]:
    """Return symbols whose raw data contains an observation on a UTC date."""
    target = pd.Timestamp(date_utc)
    if target.tzinfo is None:
        raise ValueError("date_utc must include timezone information.")
    target = target.tz_convert("UTC")

    eligible: list[str] = []
    for symbol in symbols:
        frame = load_daily_open_high(find_symbol_csv(raw_directory, symbol))
        if target in frame.index:
            eligible.append(symbol)
    return tuple(eligible)


def select_reproducible_symbols(
    eligible_symbols: Sequence[str],
    *,
    required_symbol: str,
    additional_symbol_count: int,
    random_seed: int,
) -> tuple[str, ...]:
    """Keep one required symbol and sample the others with an explicit seed."""
    if required_symbol not in eligible_symbols:
        raise ValueError(f"Required symbol {required_symbol} is not eligible.")
    candidates = [symbol for symbol in eligible_symbols if symbol != required_symbol]
    if len(candidates) < additional_symbol_count:
        raise ValueError("The eligible universe is smaller than the requested sample.")
    sampled = random.Random(random_seed).sample(candidates, additional_symbol_count)
    return (required_symbol, *sampled)


def build_selected_symbol_returns(
    selected_symbols: Sequence[str],
    *,
    raw_directory: Path,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
    horizons_days: Sequence[int] = (0, 1, 2, 3),
) -> pd.DataFrame:
    """Build one tidy result table for all selected symbols."""
    frames: list[pd.DataFrame] = []
    for symbol in selected_symbols:
        prices = load_daily_open_high(find_symbol_csv(raw_directory, symbol))
        returns = calculate_future_high_returns(
            prices,
            start_utc=start_utc,
            end_utc=end_utc,
            horizons_days=horizons_days,
        ).reset_index()
        returns.insert(0, "symbol", symbol)
        frames.append(returns)
    return pd.concat(frames, ignore_index=True)


def analyze_future_high(
    values_by_symbol: dict[str, pd.DataFrame], config: FutureHighReturnConfig
) -> dict[str, pd.DataFrame]:
    symbols = tuple(values_by_symbol)
    eligible = tuple(
        (
            symbol
            for symbol, values in values_by_symbol.items()
            if config.analysis_start_utc in values.index
        )
    )
    selected = select_reproducible_symbols(
        eligible,
        required_symbol=config.required_symbol,
        additional_symbol_count=config.additional_symbol_count,
        random_seed=config.random_seed,
    )
    returns = pd.concat(
        [
            calculate_future_high_returns(
                values_by_symbol[symbol],
                start_utc=config.analysis_start_utc,
                end_utc=config.analysis_end_utc,
                horizons_days=config.horizons_days,
            )
            .reset_index()
            .assign(symbol=symbol)
            for symbol in selected
        ],
        ignore_index=True,
    )
    returns = returns[
        ["symbol", "date_utc", "base_open", *[f"D{h}" for h in config.horizons_days]]
    ]
    summary = returns.groupby("symbol")[[f"D{h}" for h in config.horizons_days]].agg(
        ["count", "mean", "median", "min", "max"]
    )
    summary.columns = ["_".join(col) for col in summary.columns]
    return {
        "outcomes": returns,
        "summary": summary,
        "eligibility": pd.DataFrame(
            {
                "symbol": symbols,
                "eligible": [s in eligible for s in symbols],
                "selected": [s in selected for s in symbols],
            }
        ),
    }
