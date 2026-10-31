"""Read immutable exploratory inputs without filling gaps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd

from tcc_crypto.analysis.hourly_activity import ACTIVITY_FIELDS
from tcc_crypto.collection.config import CollectionConfig

PRICE_FIELDS = ("open", "high", "low", "close")
VOLUME_FIELD = "quote_asset_volume"
HOUR_MS = 3600000
DAY_MS = 86400000


def canonical_csv_path(
    repository_root: Path,
    collection_config: CollectionConfig,
    symbol: str,
) -> Path:
    """Resolve the single canonical raw CSV for a configured symbol."""
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
        if (
            activity["taker_buy_base_asset_volume"] > activity["base_asset_volume"]
        ).any():
            raise ValueError(
                f"{path} contains taker-buy base volume above total volume."
            )
    if {"quote_asset_volume", "taker_buy_quote_asset_volume"}.issubset(activity):
        if (
            activity["taker_buy_quote_asset_volume"] > activity["quote_asset_volume"]
        ).any():
            raise ValueError(
                f"{path} contains taker-buy quote volume above total volume."
            )
    return activity


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


def load_collection_symbols(path: Path) -> tuple[str, ...]:
    """Return the ordered symbol universe from a collection configuration."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)
    symbols = tuple(str(symbol) for symbol in payload["symbols"])
    if len(symbols) != len(set(symbols)):
        raise ValueError("The collection configuration contains duplicate symbols.")
    return symbols


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
