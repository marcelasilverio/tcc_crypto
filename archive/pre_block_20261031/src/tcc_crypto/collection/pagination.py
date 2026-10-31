"""Collection: pagination."""

from __future__ import annotations

from typing import Iterator

import pandas as pd

from tcc_crypto.collection.client import PageRequester, _default_page_requester
from tcc_crypto.collection.config import CollectionConfig
from tcc_crypto.collection.schema import _raw_frame_from_rows, _validate_page


def collect_klines(
    symbol: str,
    config: CollectionConfig,
    *,
    page_requester: PageRequester | None = None,
) -> pd.DataFrame:
    """Collect one symbol in memory; primarily useful for tests and small runs."""
    requester = page_requester or _default_page_requester(config)
    rows: list[list[object]] = []
    for page in iter_kline_pages(symbol, config, requester):
        rows.extend(page)

    if not rows:
        raise ValueError(f"No {config.interval} klines were returned for {symbol}.")
    frame = _raw_frame_from_rows(rows)
    return (
        frame.loc[
            (frame["open_time_ms"] >= config.start_time_ms)
            & (frame["close_time_ms"] <= config.end_time_ms)
        ]
        .sort_values("open_time_ms", kind="stable")
        .reset_index(drop=True)
    )


def iter_kline_pages(
    symbol: str,
    config: CollectionConfig,
    requester: PageRequester,
    *,
    start_time_ms: int | None = None,
) -> Iterator[list[list[object]]]:
    """Yield validated pages using the same boundary rules for every collector."""
    next_start_ms = config.start_time_ms if start_time_ms is None else start_time_ms

    while next_start_ms <= config.end_time_ms:
        parameters: dict[str, object] = {
            "symbol": symbol,
            "interval": config.interval,
            "startTime": next_start_ms,
            "endTime": config.end_time_ms,
            "timeZone": config.time_zone,
            "limit": config.limit,
        }
        page = _validate_page(requester(parameters), symbol, next_start_ms)
        if not page:
            break
        yield page
        next_start_ms = int(page[-1][0]) + 1
        if len(page) < config.limit:
            break
