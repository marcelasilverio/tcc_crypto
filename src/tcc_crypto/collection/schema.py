"""Collection: schema."""

from __future__ import annotations

from typing import Mapping

import pandas as pd

KLINE_COLUMNS = [
    "open_time_ms",
    "open",
    "high",
    "low",
    "close",
    "base_asset_volume",
    "close_time_ms",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
]


DECIMAL_TEXT_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "base_asset_volume",
    "quote_asset_volume",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
]


INTERVAL_SPECS = {
    "1h": {
        "duration_ms": 60 * 60 * 1000,
        "frequency": "1h",
        "singular": "hour",
        "plural": "hours",
    },
    "1d": {
        "duration_ms": 24 * 60 * 60 * 1000,
        "frequency": "1D",
        "singular": "day",
        "plural": "days",
    },
}


HOUR_MS = int(INTERVAL_SPECS["1h"]["duration_ms"])


def _interval_spec(interval: str) -> Mapping[str, object]:
    """Return the validated temporal specification for a Binance interval."""
    try:
        return INTERVAL_SPECS[interval]
    except KeyError as error:
        supported = ", ".join(sorted(INTERVAL_SPECS))
        raise ValueError(f"Supported collection intervals are: {supported}.") from error


def _validate_page(
    payload: object,
    symbol: str,
    next_start_ms: int,
) -> list[list[object]]:
    if not isinstance(payload, list):
        raise ValueError(f"Unexpected kline response type for {symbol}.")
    if not payload:
        return []
    if any(not isinstance(row, list) or len(row) != 12 for row in payload):
        raise ValueError(
            f"Unexpected kline row schema for {symbol}; expected 12 fields."
        )

    rows = [list(row) for row in payload]
    open_times = [int(row[0]) for row in rows]
    if open_times[0] < next_start_ms:
        raise ValueError(f"Kline pagination moved backwards for {symbol}.")
    if any(
        current <= previous for previous, current in zip(open_times, open_times[1:])
    ):
        raise ValueError(f"Kline page is not strictly chronological for {symbol}.")
    return rows


def _raw_frame_from_rows(rows: list[list[object]]) -> pd.DataFrame:
    """Create a frame while preserving Binance decimal fields as text."""
    frame = pd.DataFrame(rows, columns=KLINE_COLUMNS)
    frame["open_time_ms"] = pd.to_numeric(
        frame["open_time_ms"], errors="raise", downcast="integer"
    )
    frame["close_time_ms"] = pd.to_numeric(
        frame["close_time_ms"], errors="raise", downcast="integer"
    )
    frame["number_of_trades"] = pd.to_numeric(
        frame["number_of_trades"], errors="raise", downcast="integer"
    )
    for column_name in DECIMAL_TEXT_COLUMNS:
        frame[column_name] = frame[column_name].map(str)
    frame["ignore"] = frame["ignore"].map(str)
    return _add_utc_columns(frame)


def _add_utc_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "open_time_utc" not in result.columns:
        result.insert(
            1,
            "open_time_utc",
            pd.to_datetime(result["open_time_ms"], unit="ms", utc=True),
        )
    if "close_time_utc" not in result.columns:
        position = result.columns.get_loc("close_time_ms") + 1
        result.insert(
            position,
            "close_time_utc",
            pd.to_datetime(result["close_time_ms"], unit="ms", utc=True),
        )
    return result
