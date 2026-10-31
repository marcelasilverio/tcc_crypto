"""Collection: config."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tcc_crypto.collection.schema import _interval_spec
from tcc_crypto.data.time import _parse_utc_timestamp as _parse_utc_timestamp


@dataclass(frozen=True)
class CollectionConfig:
    """Validated configuration for one fixed Binance kline collection."""

    collection_id: str
    market: str
    quote_asset: str
    selection_source: str
    selection_snapshot_end_utc: pd.Timestamp
    selection_measure: str
    selection_rule: str
    symbols: tuple[str, ...]
    interval: str
    start_time_utc: pd.Timestamp
    end_time_utc: pd.Timestamp
    base_url: str
    kline_path: str
    time_zone: str
    limit: int
    request_timeout_seconds: int
    max_retries: int
    max_workers: int
    output_directory: Path

    @property
    def start_time_ms(self) -> int:
        """Return the inclusive collection start in Unix milliseconds."""
        return int(self.start_time_utc.timestamp() * 1000)

    @property
    def end_time_ms(self) -> int:
        """Return the inclusive collection end in Unix milliseconds."""
        return int(self.end_time_utc.timestamp() * 1000)


def load_collection_config(path: Path) -> CollectionConfig:
    """Load and validate a JSON collection configuration."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)

    symbols = tuple(str(symbol) for symbol in payload["symbols"])
    if len(symbols) != 40:
        raise ValueError(f"Expected exactly 40 symbols, received {len(symbols)}.")
    if len(set(symbols)) != len(symbols):
        raise ValueError("The configured symbol list contains duplicates.")

    quote_asset = str(payload["quote_asset"])
    if any(not symbol.endswith(quote_asset) for symbol in symbols):
        raise ValueError(f"Every symbol must be quoted in {quote_asset}.")

    interval = str(payload["interval"])
    _interval_spec(interval)

    start_time = _parse_utc_timestamp(payload["start_time_utc"], "start_time_utc")
    end_time = _parse_utc_timestamp(payload["end_time_utc"], "end_time_utc")
    if start_time >= end_time:
        raise ValueError("start_time_utc must be earlier than end_time_utc.")
    if start_time.minute or start_time.second or start_time.microsecond:
        raise ValueError("start_time_utc must be aligned to an hourly boundary.")
    if interval == "1d" and start_time.hour:
        raise ValueError("start_time_utc must be aligned to a UTC day boundary.")
    expected_end = (
        end_time.normalize() + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
    )
    if end_time != expected_end:
        raise ValueError("end_time_utc must be the final millisecond of a UTC day.")

    limit = int(payload["limit"])
    if not 1 <= limit <= 1000:
        raise ValueError("Binance kline limit must be between 1 and 1000.")

    return CollectionConfig(
        collection_id=str(payload["collection_id"]),
        market=str(payload["market"]),
        quote_asset=quote_asset,
        selection_source=str(payload["selection_source"]),
        selection_snapshot_end_utc=_parse_utc_timestamp(
            payload["selection_snapshot_end_utc"],
            "selection_snapshot_end_utc",
        ),
        selection_measure=str(payload["selection_measure"]),
        selection_rule=str(payload["selection_rule"]),
        symbols=symbols,
        interval=interval,
        start_time_utc=start_time,
        end_time_utc=end_time,
        base_url=str(payload["base_url"]).rstrip("/"),
        kline_path=str(payload["kline_path"]),
        time_zone=str(payload["time_zone"]),
        limit=limit,
        request_timeout_seconds=int(payload["request_timeout_seconds"]),
        max_retries=int(payload["max_retries"]),
        max_workers=int(payload["max_workers"]),
        output_directory=Path(payload["output_directory"]),
    )
