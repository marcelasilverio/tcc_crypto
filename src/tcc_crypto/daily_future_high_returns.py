"""Calculate daily future-high returns from a fixed opening price.

The calculation in this module is an outcome construction: it deliberately
uses future daily highs. Its outputs must not be used as features available at
the base timestamp.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd


@dataclass(frozen=True)
class FutureHighReturnConfig:
    """Validated parameters for the daily future-high return calculation."""

    analysis_id: str
    collection_config: Path
    analysis_start_utc: pd.Timestamp
    analysis_end_utc: pd.Timestamp
    required_symbol: str
    additional_symbol_count: int
    random_seed: int
    eligibility_rule: str
    horizons_days: tuple[int, ...]
    output_directory: Path


def _parse_utc_timestamp(value: object, field_name: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"{field_name} must include an explicit UTC offset.")
    return timestamp.tz_convert("UTC")


def load_future_high_return_config(path: Path) -> FutureHighReturnConfig:
    """Load and validate a future-high return JSON configuration."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)

    horizons = tuple(int(value) for value in payload["horizons_days"])
    if horizons != tuple(range(len(horizons))):
        raise ValueError("horizons_days must be consecutive and start at zero.")

    start = _parse_utc_timestamp(payload["analysis_start_utc"], "analysis_start_utc")
    end = _parse_utc_timestamp(payload["analysis_end_utc"], "analysis_end_utc")
    if start >= end:
        raise ValueError("analysis_start_utc must be earlier than analysis_end_utc.")
    if start != start.normalize() or end != end.normalize():
        raise ValueError("Analysis boundaries must be aligned to UTC days.")

    additional_symbol_count = int(payload["additional_symbol_count"])
    if additional_symbol_count < 1:
        raise ValueError("additional_symbol_count must be positive.")

    eligibility_rule = str(payload["eligibility_rule"])
    if eligibility_rule != "observed_on_analysis_start":
        raise ValueError(
            "Only the observed_on_analysis_start eligibility rule is supported."
        )

    return FutureHighReturnConfig(
        analysis_id=str(payload["analysis_id"]),
        collection_config=Path(payload["collection_config"]),
        analysis_start_utc=start,
        analysis_end_utc=end,
        required_symbol=str(payload["required_symbol"]),
        additional_symbol_count=additional_symbol_count,
        random_seed=int(payload["random_seed"]),
        eligibility_rule=eligibility_rule,
        horizons_days=horizons,
        output_directory=Path(payload["output_directory"]),
    )


def load_collection_symbols(path: Path) -> tuple[str, ...]:
    """Return the ordered symbol universe from a collection configuration."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)
    symbols = tuple(str(symbol) for symbol in payload["symbols"])
    if len(symbols) != len(set(symbols)):
        raise ValueError("The collection configuration contains duplicate symbols.")
    return symbols


def find_symbol_csv(raw_directory: Path, symbol: str) -> Path:
    """Resolve the single immutable daily CSV for a symbol."""
    matches = sorted((raw_directory / symbol).glob(f"{symbol}_1d_*.csv.gz"))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"Expected one daily CSV for {symbol}, found {len(matches)}."
        )
    return matches[0]


def load_daily_open_high(path: Path) -> pd.DataFrame:
    """Load and validate UTC timestamps plus positive daily open/high prices."""
    frame = pd.read_csv(path, usecols=["open_time_ms", "open", "high"])
    frame["date_utc"] = pd.to_datetime(frame.pop("open_time_ms"), unit="ms", utc=True)
    frame["open"] = pd.to_numeric(frame["open"], errors="raise")
    frame["high"] = pd.to_numeric(frame["high"], errors="raise")
    frame = frame.set_index("date_utc").sort_index()

    if frame.index.has_duplicates:
        raise ValueError(f"Duplicate daily timestamps found in {path}.")
    if not frame.index.is_monotonic_increasing:
        raise ValueError(f"Daily timestamps are not chronological in {path}.")
    if (frame.index != frame.index.normalize()).any():
        raise ValueError(f"Daily timestamps are not aligned to UTC midnight in {path}.")
    if frame[["open", "high"]].isna().any().any():
        raise ValueError(f"Missing open/high values found in {path}.")
    if (frame[["open", "high"]] <= 0).any().any():
        raise ValueError(f"Non-positive open/high values found in {path}.")
    if (frame["high"] < frame["open"]).any():
        raise ValueError(f"A daily high is below its opening price in {path}.")
    return frame


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
