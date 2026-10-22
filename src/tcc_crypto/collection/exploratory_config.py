"""Parameters inherited from exploratory collection notebooks 01–04."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tcc_crypto.paths import reject_legacy_analysis_paths


@dataclass(frozen=True)
class ExplorationCollectionConfig:
    analysis_id: str
    base_url: str
    quote_asset: str
    symbols: tuple[str, ...]
    intervals: tuple[str, ...]
    spot_only: bool
    timeout_seconds: int
    max_retries: int
    max_workers: int
    limit: int
    start_utc: pd.Timestamp
    end_policy: str


def load_exploration_collection_config(path: Path) -> ExplorationCollectionConfig:
    payload = json.loads(path.read_text())
    reject_legacy_analysis_paths(payload)
    start = pd.Timestamp(payload["start_utc"])
    if start.tzinfo is None:
        raise ValueError("Collection start must include a timezone.")
    if payload["end_policy"] not in ("execution_time", "previous_utc_day"):
        raise ValueError("Unknown collection cutoff policy.")
    if (
        any(
            int(payload[key]) < 1 for key in ("timeout_seconds", "max_workers", "limit")
        )
        or int(payload["max_retries"]) < 0
    ):
        raise ValueError("Invalid request limits.")
    return ExplorationCollectionConfig(
        payload["analysis_id"],
        payload["base_url"],
        payload["quote_asset"],
        tuple(payload["symbols"]),
        tuple(payload["intervals"]),
        payload["spot_only"],
        int(payload["timeout_seconds"]),
        int(payload["max_retries"]),
        int(payload["max_workers"]),
        int(payload["limit"]),
        start.tz_convert("UTC"),
        payload["end_policy"],
    )


def collection_cutoff(
    config: ExplorationCollectionConfig, execution_time: pd.Timestamp
) -> pd.Timestamp:
    execution_time = execution_time.tz_convert("UTC")
    return (
        execution_time.normalize() - pd.Timedelta(milliseconds=1)
        if config.end_policy == "previous_utc_day"
        else execution_time
    )
