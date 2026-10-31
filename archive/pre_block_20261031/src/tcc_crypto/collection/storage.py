"""Collection: storage."""

from __future__ import annotations

import gzip
import json
import os
import shutil
from pathlib import Path
from typing import Mapping
from uuid import uuid4

import pandas as pd

from tcc_crypto.collection.schema import KLINE_COLUMNS, _add_utc_columns
from tcc_crypto.paths import PairOutputPaths


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    temporary_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as output_file:
            json.dump(payload, output_file, indent=2, sort_keys=True)
            output_file.write("\n")
            output_file.flush()
            os.fsync(output_file.fileno())
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _load_raw_csv(path: Path, *, compressed: bool) -> pd.DataFrame:
    compression = "gzip" if compressed else None
    frame = pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        compression=compression,
    )
    if list(frame.columns) != KLINE_COLUMNS:
        raise ValueError(f"Unexpected raw CSV schema: {path}")
    frame["open_time_ms"] = pd.to_numeric(frame["open_time_ms"], errors="raise")
    frame["close_time_ms"] = pd.to_numeric(frame["close_time_ms"], errors="raise")
    frame["number_of_trades"] = pd.to_numeric(frame["number_of_trades"], errors="raise")
    return _add_utc_columns(frame)


def load_raw_csv_gz(path: Path) -> pd.DataFrame:
    """Load a canonical raw CSV while preserving decimal text columns."""
    return _load_raw_csv(path, compressed=True)


def _compress_partial_csv(paths: PairOutputPaths) -> None:
    if paths.raw_csv_gz.exists():
        raise FileExistsError(f"Refusing to overwrite raw CSV: {paths.raw_csv_gz}")
    temporary_path = paths.raw_csv_gz.with_name(
        f".{paths.raw_csv_gz.name}.{uuid4().hex}.tmp"
    )
    try:
        with paths.partial_csv.open("rb") as source_file:
            with temporary_path.open("xb") as compressed_file:
                with gzip.GzipFile(
                    filename="",
                    mode="wb",
                    fileobj=compressed_file,
                    mtime=0,
                ) as gzip_file:
                    shutil.copyfileobj(source_file, gzip_file)
                compressed_file.flush()
                os.fsync(compressed_file.fileno())
        if paths.raw_csv_gz.exists():
            raise FileExistsError(f"Refusing to overwrite raw CSV: {paths.raw_csv_gz}")
        temporary_path.rename(paths.raw_csv_gz)
    finally:
        temporary_path.unlink(missing_ok=True)
