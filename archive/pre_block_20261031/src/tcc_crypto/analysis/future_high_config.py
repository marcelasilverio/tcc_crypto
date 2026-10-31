"""Configuration for future_high."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tcc_crypto.data.time import _parse_utc_timestamp
from tcc_crypto.paths import analysis_output_directory, reject_legacy_analysis_paths
from tcc_crypto.paths import repository_root as default_root


@dataclass(frozen=True)
class FutureHighReturnConfig:
    """Validated parameters for the daily future-high return calculation."""

    analysis_id: str
    collection_config: Path
    analysis_start_utc: pd.Timestamp
    analysis_end_utc: pd.Timestamp
    required_symbol: str
    additional_symbol_count: int
    random_seed: int
    eligibility_rule: str
    horizons_days: tuple[int, ...]
    output_directory: Path


def load_future_high_return_config(
    path: Path, *, repository_root: Path | None = None
) -> FutureHighReturnConfig:
    """Load and validate a future-high return JSON configuration."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)
    reject_legacy_analysis_paths(payload)

    horizons = tuple(int(value) for value in payload["horizons_days"])
    if horizons != tuple(range(len(horizons))):
        raise ValueError("horizons_days must be consecutive and start at zero.")

    start = _parse_utc_timestamp(payload["analysis_start_utc"], "analysis_start_utc")
    end = _parse_utc_timestamp(payload["analysis_end_utc"], "analysis_end_utc")
    if start >= end:
        raise ValueError("analysis_start_utc must be earlier than analysis_end_utc.")
    if start != start.normalize() or end != end.normalize():
        raise ValueError("Analysis boundaries must be aligned to UTC days.")

    additional_symbol_count = int(payload["additional_symbol_count"])
    if additional_symbol_count < 1:
        raise ValueError("additional_symbol_count must be positive.")

    eligibility_rule = str(payload["eligibility_rule"])
    if eligibility_rule != "observed_on_analysis_start":
        raise ValueError(
            "Only the observed_on_analysis_start eligibility rule is supported."
        )

    return FutureHighReturnConfig(
        analysis_id=str(payload["analysis_id"]),
        collection_config=Path(payload["collection_config"]),
        analysis_start_utc=start,
        analysis_end_utc=end,
        required_symbol=str(payload["required_symbol"]),
        additional_symbol_count=additional_symbol_count,
        random_seed=int(payload["random_seed"]),
        eligibility_rule=eligibility_rule,
        horizons_days=horizons,
        output_directory=analysis_output_directory(
            default_root(repository_root), "future-high", str(payload["analysis_id"])
        ),
    )
