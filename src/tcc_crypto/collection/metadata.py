"""Collection: metadata."""

from __future__ import annotations

import json
import os
import platform
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import openpyxl
import pandas as pd

from tcc_crypto.collection.config import CollectionConfig
from tcc_crypto.collection.schema import _interval_spec
from tcc_crypto.collection.validation import (
    missing_kline_intervals,
    nonstandard_candle_durations,
)
from tcc_crypto.paths import PairOutputPaths
from tcc_crypto.reporting.provenance import file_sha256 as _sha256_file
from tcc_crypto.reporting.provenance import git_value


def _git_revision(repository_root: Path) -> str:
    """Keep the collection's historical unavailable marker."""
    return git_value(("rev-parse", "HEAD"), repository_root) or "unavailable"


def _selection_source_sha256(
    config: CollectionConfig,
    repository_root: Path,
) -> str:
    source_path = repository_root / config.selection_source
    return _sha256_file(source_path) if source_path.exists() else "unavailable"


def build_metadata(
    symbol: str,
    frame: pd.DataFrame,
    config: CollectionConfig,
    repository_root: Path,
    collected_at_utc: datetime,
    raw_csv_sha256: str,
) -> pd.DataFrame:
    """Build auditable collection metadata for a pair workbook."""
    interval_plural = str(_interval_spec(config.interval)["plural"])
    missing = missing_kline_intervals(frame, config)
    shortened = nonstandard_candle_durations(frame, config)
    first_open = frame["open_time_utc"].min()
    last_close = frame["close_time_utc"].max()
    records = [
        ("Collection ID", config.collection_id),
        ("Collection timestamp (UTC)", collected_at_utc.isoformat()),
        ("Code revision", _git_revision(repository_root)),
        ("Python version", platform.python_version()),
        ("pandas version", pd.__version__),
        ("openpyxl version", openpyxl.__version__),
        ("Market", config.market),
        ("Trading pair", symbol),
        ("Quote asset", config.quote_asset),
        ("Interval", config.interval),
        ("Timezone", "UTC"),
        ("Requested start (UTC)", config.start_time_utc.isoformat()),
        ("Requested end (UTC)", config.end_time_utc.isoformat()),
        ("First observed open (UTC)", first_open.isoformat()),
        ("Last observed close (UTC)", last_close.isoformat()),
        (f"Observed {config.interval} klines", len(frame)),
        (f"Missing {interval_plural} within observed span", len(missing)),
        ("Shortened candle durations", len(shortened)),
        ("Selection source", config.selection_source),
        (
            "Selection source SHA-256",
            _selection_source_sha256(config, repository_root),
        ),
        ("Selection snapshot end (UTC)", config.selection_snapshot_end_utc.isoformat()),
        ("Selection measure", config.selection_measure),
        ("Selection rule", config.selection_rule),
        ("Source endpoint", f"{config.base_url}{config.kline_path}"),
        (
            "Canonical raw format",
            "gzip-compressed CSV with Binance decimal text preserved",
        ),
        ("Canonical raw CSV SHA-256", raw_csv_sha256),
        (
            "Excel role",
            "Derived human-review copy; numeric cells use Excel floating point",
        ),
    ]
    return pd.DataFrame(records, columns=["Field", "Value"])


def _write_pair_metadata_json(
    paths: PairOutputPaths,
    metadata: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    raw_hash = metadata.set_index("Field").loc[
        "Canonical raw CSV SHA-256",
        "Value",
    ]
    if paths.metadata_json.exists():
        with paths.metadata_json.open(encoding="utf-8") as metadata_file:
            existing = json.load(metadata_file)
        if existing.get("raw_csv_sha256") != raw_hash:
            raise ValueError(
                f"Existing metadata checksum differs: {paths.metadata_json}"
            )
        if existing.get("workbook_sha256") != _sha256_file(paths.workbook):
            raise ValueError(
                f"Existing workbook checksum differs: {paths.metadata_json}"
            )
        recorded_metadata = existing.get("metadata", {})
        selection_hash = metadata.set_index("Field").loc[
            "Selection source SHA-256",
            "Value",
        ]
        if recorded_metadata.get("Selection source SHA-256") != selection_hash:
            raise ValueError(
                f"Selection source checksum differs: {paths.metadata_json}"
            )
        return

    metadata_map = {str(row["Field"]): row["Value"] for _, row in metadata.iterrows()}
    payload = {
        "metadata": metadata_map,
        "validation": validation.to_dict(orient="records"),
        "raw_csv_sha256": raw_hash,
        "workbook_sha256": _sha256_file(paths.workbook),
    }
    temporary_path = paths.metadata_json.with_name(
        f".{paths.metadata_json.name}.{uuid4().hex}.tmp"
    )
    try:
        with temporary_path.open("x", encoding="utf-8") as output_file:
            json.dump(payload, output_file, indent=2, sort_keys=True, default=str)
            output_file.write("\n")
            output_file.flush()
            os.fsync(output_file.fileno())
        if paths.metadata_json.exists():
            raise FileExistsError(
                f"Refusing to overwrite metadata: {paths.metadata_json}"
            )
        temporary_path.rename(paths.metadata_json)
    finally:
        temporary_path.unlink(missing_ok=True)
