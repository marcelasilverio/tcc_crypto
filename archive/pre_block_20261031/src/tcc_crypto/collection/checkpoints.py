"""Collection: checkpoints."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from tcc_crypto.collection.client import PageRequester, _default_page_requester
from tcc_crypto.collection.config import CollectionConfig
from tcc_crypto.collection.pagination import iter_kline_pages
from tcc_crypto.collection.schema import KLINE_COLUMNS
from tcc_crypto.collection.storage import _atomic_write_json
from tcc_crypto.paths import PairOutputPaths


def _checkpoint_fingerprint(symbol: str, config: CollectionConfig) -> str:
    payload = {
        "symbol": symbol,
        "interval": config.interval,
        "start_time_ms": config.start_time_ms,
        "end_time_ms": config.end_time_ms,
        "base_url": config.base_url,
        "kline_path": config.kline_path,
        "time_zone": config.time_zone,
        "columns": KLINE_COLUMNS,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _initialize_or_validate_checkpoint(
    symbol: str,
    config: CollectionConfig,
    paths: PairOutputPaths,
) -> tuple[int, int]:
    """Return the next request timestamp and existing checkpoint row count."""
    paths.directory.mkdir(parents=True, exist_ok=True)
    fingerprint = _checkpoint_fingerprint(symbol, config)

    if paths.checkpoint_json.exists():
        with paths.checkpoint_json.open(encoding="utf-8") as checkpoint_file:
            checkpoint = json.load(checkpoint_file)
        if checkpoint.get("fingerprint") != fingerprint:
            raise ValueError(
                f"Checkpoint configuration differs for {symbol}: "
                f"{paths.checkpoint_json}"
            )
    else:
        if paths.partial_csv.exists():
            raise ValueError(
                f"Partial CSV exists without its checkpoint: {paths.partial_csv}"
            )
        _atomic_write_json(
            paths.checkpoint_json,
            {
                "symbol": symbol,
                "fingerprint": fingerprint,
                "rows_written": 0,
                "last_open_time_ms": None,
                "next_start_time_ms": config.start_time_ms,
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )

    if not paths.partial_csv.exists():
        with paths.partial_csv.open("x", encoding="utf-8", newline="") as output_file:
            csv.writer(output_file).writerow(KLINE_COLUMNS)
            output_file.flush()
            os.fsync(output_file.fileno())

    row_count = 0
    last_open_time_ms: int | None = None
    with paths.partial_csv.open(encoding="utf-8", newline="") as input_file:
        reader = csv.reader(input_file)
        header = next(reader, None)
        if header != KLINE_COLUMNS:
            raise ValueError(f"Unexpected checkpoint CSV header for {symbol}.")
        for row in reader:
            if len(row) != len(KLINE_COLUMNS):
                raise ValueError(f"Malformed checkpoint CSV row for {symbol}.")
            open_time_ms = int(row[0])
            if last_open_time_ms is not None and open_time_ms <= last_open_time_ms:
                raise ValueError(
                    f"Checkpoint is not strictly chronological for {symbol}."
                )
            last_open_time_ms = open_time_ms
            row_count += 1

    next_start_ms = (
        config.start_time_ms if last_open_time_ms is None else last_open_time_ms + 1
    )
    return next_start_ms, row_count


def _append_checkpoint_page(
    paths: PairOutputPaths,
    symbol: str,
    config: CollectionConfig,
    rows: list[list[object]],
    previous_row_count: int,
) -> int:
    filtered_rows = [
        row
        for row in rows
        if int(row[0]) >= config.start_time_ms and int(row[6]) <= config.end_time_ms
    ]
    if filtered_rows:
        with paths.partial_csv.open("a", encoding="utf-8", newline="") as output_file:
            csv.writer(output_file).writerows(filtered_rows)
            output_file.flush()
            os.fsync(output_file.fileno())
    row_count = previous_row_count + len(filtered_rows)
    last_open_time_ms = int(rows[-1][0])
    _atomic_write_json(
        paths.checkpoint_json,
        {
            "symbol": symbol,
            "fingerprint": _checkpoint_fingerprint(symbol, config),
            "rows_written": row_count,
            "last_open_time_ms": last_open_time_ms,
            "next_start_time_ms": last_open_time_ms + 1,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )
    return row_count


def collect_to_checkpoint(
    symbol: str,
    config: CollectionConfig,
    paths: PairOutputPaths,
    *,
    page_requester: PageRequester | None = None,
) -> Path:
    """Collect pages into a resumable uncompressed CSV checkpoint."""
    requester = page_requester or _default_page_requester(config)
    next_start_ms, row_count = _initialize_or_validate_checkpoint(
        symbol,
        config,
        paths,
    )

    for page in iter_kline_pages(
        symbol, config, requester, start_time_ms=next_start_ms
    ):
        row_count = _append_checkpoint_page(paths, symbol, config, page, row_count)

    if row_count == 0:
        raise ValueError(f"No {config.interval} klines were returned for {symbol}.")
    return paths.partial_csv
