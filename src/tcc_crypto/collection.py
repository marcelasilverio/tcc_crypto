"""Collection: client."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import shutil
import time
from http.client import IncompleteRead, RemoteDisconnected
from pathlib import Path
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

import pandas as pd

from tcc_crypto.paths import raw_paths
from tcc_crypto.preparation import KLINE_COLUMNS
from tcc_crypto.results import file_sha256, write_json


def request_json(
    url: str,
    parameters: Mapping[str, object],
    *,
    timeout_seconds: int,
    max_retries: int,
) -> object:
    """Request public Binance JSON with bounded transient-error retries."""
    request_url = f"{url}?{urlencode(parameters)}"
    for attempt in range(max_retries + 1):
        request = Request(
            request_url,
            headers={"User-Agent": "tcc-crypto-research/0.1"},
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return json.load(response)
        except HTTPError as error:
            is_transient = error.code == 429 or 500 <= error.code < 600
            if is_transient and attempt < max_retries:
                retry_after = error.headers.get("Retry-After")
                delay_seconds = (
                    float(retry_after)
                    if retry_after is not None
                    else min(2**attempt, 30)
                )
                time.sleep(delay_seconds)
                continue
            response_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Binance returned HTTP {error.code} for {url}: {response_body}"
            ) from error
        except URLError as error:
            if attempt < max_retries:
                time.sleep(min(2**attempt, 30))
                continue
            raise RuntimeError(
                f"Could not reach Binance at {url}: {error.reason}"
            ) from error
        except (IncompleteRead, RemoteDisconnected) as error:
            if attempt < max_retries:
                time.sleep(min(2**attempt, 30))
                continue
            raise RuntimeError(
                f"Binance connection was interrupted for {url}: {error}"
            ) from error

    raise RuntimeError(f"Request retry loop ended unexpectedly for {url}.")


def collect_symbol(symbol: str, settings: dict, root: Path, *, requester=None) -> Path:
    """Resume old checkpoints, preserve raw bytes, and prove pagination completion."""
    paths = raw_paths(root, symbol, settings)
    if paths["raw"].exists():
        # Existing raw files are inputs, not an opportunity to rewrite metadata.
        validate_raw(paths, symbol, settings)
        return paths["raw"]
    start = int(pd.Timestamp(settings["start_time_utc"]).timestamp() * 1000)
    end = int(pd.Timestamp(settings["end_time_utc"]).timestamp() * 1000)
    payload = {
        "symbol": symbol,
        "interval": "1d",
        "start_time_ms": start,
        "end_time_ms": end,
        "base_url": settings["base_url"],
        "kline_path": settings["kline_path"],
        "time_zone": settings["time_zone"],
        "columns": KLINE_COLUMNS,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    paths["raw"].parent.mkdir(parents=True, exist_ok=True)
    if paths["checkpoint"].exists():
        saved = json.loads(paths["checkpoint"].read_text())
        if saved["fingerprint"] != fingerprint:
            raise ValueError(f"{symbol}: checkpoint configuration differs.")
    elif paths["partial"].exists():
        raise ValueError(f"{symbol}: partial data without checkpoint.")
    else:
        write_json(paths["checkpoint"], {"fingerprint": fingerprint, "rows_written": 0})
    if not paths["partial"].exists():
        with paths["partial"].open("x", newline="") as stream:
            csv.writer(stream).writerow(KLINE_COLUMNS)
    next_start, count, last = start, 0, None
    with paths["partial"].open(newline="") as stream:
        reader = csv.reader(stream)
        if next(reader) != KLINE_COLUMNS:
            raise ValueError("Unexpected checkpoint schema.")
        for row in reader:
            if len(row) != 12 or (last is not None and int(row[0]) <= last):
                raise ValueError("Malformed or unordered checkpoint.")
            last = int(row[0])
            count += 1
    if last is not None:
        next_start = last + 1
    if requester is None:

        def requester(parameters):
            return request_json(
                settings["base_url"] + settings["kline_path"],
                parameters,
                timeout_seconds=settings["request_timeout_seconds"],
                max_retries=settings["max_retries"],
            )

    completion = "requested_boundary"
    while next_start <= end:
        parameters = {
            "symbol": symbol,
            "interval": "1d",
            "startTime": next_start,
            "endTime": end,
            "timeZone": settings["time_zone"],
            "limit": settings["limit"],
        }
        page = requester(parameters)
        if not isinstance(page, list) or any(
            not isinstance(row, list) or not 1 <= len(row) <= 12 for row in page
        ):
            raise ValueError("Malformed Binance response; collection is incomplete.")
        if not page:
            completion = "empty_page"
            break
        # Preserve truncated trailing fields as missing, for preparation to assess.
        page = [row + [None] * (12 - len(row)) for row in page]
        times = [int(row[0]) for row in page]
        if (
            times[0] < next_start
            or times[-1] > end
            or any(b <= a for a, b in zip(times, times[1:]))
        ):
            raise ValueError("Pagination timestamps are inconsistent.")
        with paths["partial"].open("a", newline="") as stream:
            csv.writer(stream).writerows(page)
            stream.flush()
            os.fsync(stream.fileno())
        count += len(page)
        next_start = times[-1] + 1
        write_json(
            paths["checkpoint"],
            {
                "fingerprint": fingerprint,
                "rows_written": count,
                "last_open_time_ms": times[-1],
                "next_start_time_ms": next_start,
            },
        )
        # Request again even after a short page to distinguish exhaustion explicitly.
    temporary = paths["raw"].with_name(f".{uuid4().hex}.tmp")
    try:
        with paths["partial"].open("rb") as source, temporary.open("xb") as target:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=target, mtime=0
            ) as compressed:
                shutil.copyfileobj(source, compressed)
        if paths["raw"].exists():
            raise FileExistsError("Raw output appeared during collection.")
        temporary.rename(paths["raw"])
    finally:
        temporary.unlink(missing_ok=True)
    write_json(
        paths["metadata"],
        {
            "symbol": symbol,
            "requested": settings,
            "rows": count,
            "completion": completion,
            "last_request_start_ms": next_start,
            "sha256": file_sha256(paths["raw"]),
            "collected_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        },
    )
    # Completed checkpoints remain as resumability evidence; raw always takes precedence.
    return paths["raw"]


def validate_raw(paths: dict[str, Path], symbol: str, settings: dict) -> None:
    """Validate current or legacy raw provenance without rewriting either format."""
    if not paths["metadata"].exists():
        raise FileNotFoundError(
            "Missing raw collection metadata; inspect the collect stage before preparation."
        )
    meta = json.loads(paths["metadata"].read_text())
    if "requested" in meta:
        recorded = meta["requested"]
        expected_hash = meta["sha256"]
        recorded_symbol = meta["symbol"]
        if meta.get("completion") not in {"empty_page", "requested_boundary"}:
            raise ValueError("Raw collection has no successful completion evidence.")
    else:
        legacy = meta["metadata"]
        expected_hash = meta["raw_csv_sha256"]
        recorded_symbol = legacy["Trading pair"]
        recorded = {
            "interval": legacy["Interval"],
            "start_time_utc": legacy["Requested start (UTC)"],
            "end_time_utc": legacy["Requested end (UTC)"],
            "time_zone": "0" if legacy["Timezone"] == "UTC" else legacy["Timezone"],
        }
    if file_sha256(paths["raw"]) != expected_hash:
        raise ValueError("Raw data checksum differs from collection metadata.")
    if (
        recorded_symbol != symbol
        or recorded["interval"] != settings["interval"]
        or recorded["time_zone"] != settings["time_zone"]
    ):
        raise ValueError("Raw collection identity differs from configuration.")
    if any(
        pd.Timestamp(recorded[k]) != pd.Timestamp(settings[k])
        for k in ("start_time_utc", "end_time_utc")
    ):
        raise ValueError("Raw collection period differs from configuration.")
