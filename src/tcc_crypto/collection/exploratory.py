"""Exploratory API collection with immutable, resumable request snapshots."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from typing import Callable, Mapping

import pandas as pd

from tcc_crypto.collection.client import request_json
from tcc_crypto.collection.exploratory_config import (
    ExplorationCollectionConfig,
    collection_cutoff,
)
from tcc_crypto.collection.schema import _validate_page
from tcc_crypto.reporting.tables import write_json

Requester = Callable[[str, Mapping[str, object]], object]


def snapshot_requester(
    directory: Path,
    config: ExplorationCollectionConfig,
    requester: Requester | None = None,
) -> Requester:
    """Reuse an exact request snapshot; never replace a previously saved response."""

    def fetch(endpoint: str, parameters: Mapping[str, object]) -> object:
        url = config.base_url.rstrip("/") + endpoint
        identity = {"url": url, "parameters": dict(parameters)}
        key = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        path = directory / (key + ".json")
        if path.exists():
            saved = json.loads(path.read_text())
            digest = sha256(
                json.dumps(saved["response"], sort_keys=True).encode()
            ).hexdigest()
            if saved["request"] != identity or saved["response_sha256"] != digest:
                raise ValueError(f"Invalid request snapshot: {path}")
            return saved["response"]
        payload = (
            requester(endpoint, parameters)
            if requester
            else request_json(
                url,
                parameters,
                timeout_seconds=config.timeout_seconds,
                max_retries=config.max_retries,
            )
        )
        write_json(
            path,
            {
                "request": identity,
                "requested_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                "response": payload,
                "response_sha256": sha256(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest(),
            },
        )
        return payload

    return fetch


def discover_symbols(
    payload: object, *, quote_asset: str, spot_only: bool
) -> pd.DataFrame:
    """Preserve current catalog statuses, including BREAK; never infer historical eligibility."""
    if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), list):
        raise ValueError("Unexpected exchangeInfo response.")
    rows = [
        {
            "Trading Pair": item["symbol"],
            "Base Asset": item["baseAsset"],
            "Quote Asset": item["quoteAsset"],
            "Current Status": item["status"],
            "Spot Trading Currently Allowed": item.get("isSpotTradingAllowed"),
        }
        for item in payload["symbols"]
        if item.get("quoteAsset") == quote_asset
        and (not spot_only or item.get("isSpotTradingAllowed", False))
    ]
    if not rows:
        raise ValueError(f"No symbols returned for quote asset {quote_asset}.")
    result = pd.DataFrame(rows).sort_values("Trading Pair").reset_index(drop=True)
    if result["Trading Pair"].duplicated().any():
        raise ValueError("Duplicate symbols in exchangeInfo response.")
    return result


def first_kline(
    symbol: str, interval: str, requester: Requester, *, include_timezone: bool = True
) -> list[object]:
    params = {"symbol": symbol, "interval": interval, "startTime": 0, "limit": 1}
    if include_timezone:
        params["timeZone"] = 0
    page = _validate_page(requester("/api/v3/klines", params), symbol, 0)
    if not page:
        raise ValueError(f"No {interval} kline returned for {symbol}.")
    validate_exploratory_rows(page, interval)
    return page[0]


def exploratory_klines(
    symbol: str,
    interval: str,
    *,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
    requester: Requester,
    limit: int,
    closed_only: bool,
) -> list[list[object]]:
    """Page by observed opening timestamp, including a partial monthly candle when requested."""
    cursor, end = start_utc.value // 1_000_000, end_utc.value // 1_000_000
    rows = []
    while cursor <= end:
        page = _validate_page(
            requester(
                "/api/v3/klines",
                {
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": cursor,
                    "endTime": end,
                    "limit": limit,
                    "timeZone": 0,
                },
            ),
            symbol,
            cursor,
        )
        if not page:
            break
        validate_exploratory_rows(page, interval)
        rows.extend(
            row
            for row in page
            if int(row[0]) <= end and (not closed_only or int(row[6]) <= end)
        )
        cursor = int(page[-1][0]) + 1
        if len(page) < limit or int(page[-1][0]) >= end:
            break
    return rows


def collect_exploration(
    analysis: str,
    config: ExplorationCollectionConfig,
    *,
    requester: Requester,
    execution_time: pd.Timestamp,
    record_sink: Callable[[dict], dict] | None = None,
) -> dict:
    """Return raw records; orchestration and request persistence are separate."""
    cutoff = collection_cutoff(config, execution_time)
    if analysis == "earliest":
        records = [
            {
                "symbol": symbol,
                "interval": interval,
                "row": first_kline(symbol, interval, requester, include_timezone=False),
            }
            for symbol in config.symbols
            for interval in config.intervals
        ]
        return {
            "records": records,
            "execution_time": execution_time.isoformat(),
            "cutoff": cutoff.isoformat(),
        }
    pairs = discover_symbols(
        requester("/api/v3/exchangeInfo", {}),
        quote_asset=config.quote_asset,
        spot_only=config.spot_only,
    )

    def collect_pair(pair: dict) -> dict:
        symbol = pair["Trading Pair"]
        if analysis == "coverage":
            records = {
                interval: first_kline(symbol, interval, requester)
                for interval in config.intervals
            }
        else:
            interval = config.intervals[0]
            records = {
                interval: exploratory_klines(
                    symbol,
                    interval,
                    start_utc=config.start_utc,
                    end_utc=cutoff,
                    requester=requester,
                    limit=config.limit,
                    closed_only=analysis == "trade-counts",
                )
            }
        item = {"pair": pair, "records": records}
        return record_sink(item) if record_sink else item

    # map preserves catalog order; errors propagate after snapshots have been saved.
    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        records = list(executor.map(collect_pair, pairs.to_dict("records")))
    return {
        "records": records,
        "execution_time": execution_time.isoformat(),
        "cutoff": cutoff.isoformat(),
    }


def validate_exploratory_rows(rows: list[list[object]], interval: str) -> None:
    """Validate observed API values without filling or altering any candle."""
    import numpy as np

    if not rows:
        return
    numbers = np.asarray(
        [
            [float(row[position]) for position in (1, 2, 3, 4, 5, 7, 8, 9, 10)]
            for row in rows
        ]
    )
    if not np.isfinite(numbers).all():
        raise ValueError("Non-finite exploratory kline value.")
    prices = numbers[:, :4]
    if (prices <= 0).any() or (numbers[:, 4:] < 0).any():
        raise ValueError("Non-positive prices or negative kline activity.")
    if (
        (prices[:, 1] < np.maximum(prices[:, 0], prices[:, 3])).any()
        or (prices[:, 2] > np.minimum(prices[:, 0], prices[:, 3])).any()
        or (prices[:, 1] < prices[:, 2]).any()
    ):
        raise ValueError("Exploratory OHLC consistency violation.")
    if not np.equal(numbers[:, 6], np.floor(numbers[:, 6])).all():
        raise ValueError("Trade counts must be integers.")
    opens = pd.to_datetime([int(row[0]) for row in rows], unit="ms", utc=True)
    closes = np.asarray([int(row[6]) for row in rows])
    if (closes < opens.asi8 // 1_000_000).any():
        raise ValueError("A kline closes before it opens.")
    if interval == "1d" and not (opens == opens.normalize()).all():
        raise ValueError("Daily exploratory candles require UTC midnight openings.")
    if interval == "1M" and not ((opens.day == 1) & (opens == opens.normalize())).all():
        raise ValueError(
            "Monthly exploratory candles require UTC month-opening boundaries."
        )
