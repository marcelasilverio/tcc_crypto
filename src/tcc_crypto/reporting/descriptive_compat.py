"""Explicit packet export retained for existing callers; new workflows use typed tables."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tcc_crypto.analysis.daily_descriptive import (
    VOLUME_FIELD,
    describe_coverage,
    describe_extrema,
    describe_semesters,
    describe_statistics,
    filter_analysis_window,
)
from tcc_crypto.analysis.daily_descriptive_config import (
    DailyPriceVolumeAnalysisConfig,
    load_analysis_config,
)
from tcc_crypto.data.exploratory import canonical_csv_path, load_daily_price_volume
from tcc_crypto.reporting.descriptive_definitions import definition_rows
from tcc_crypto.reporting.provenance import file_sha256 as _sha256


def _json_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {column: _json_value(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def build_pair_payload(
    symbol: str,
    values: pd.DataFrame,
    *,
    source_path: Path,
    repository_root: Path,
    config: DailyPriceVolumeAnalysisConfig,
) -> dict[str, Any]:
    """Build one JSON-serializable workbook payload for a trading pair."""
    coverage = describe_coverage(symbol, values)
    overall = describe_statistics(values, ddof=config.standard_deviation_ddof)
    semesters = describe_semesters(
        values,
        analysis_start_utc=config.analysis_start_utc,
        analysis_end_utc=config.analysis_end_utc,
        ddof=config.standard_deviation_ddof,
    )
    extrema = describe_extrema(symbol, values)
    chart_data = values[["open", "close", VOLUME_FIELD]].reset_index()
    chart_data["open_time_utc"] = chart_data["open_time_utc"].dt.strftime("%Y-%m-%d")
    relative_source = source_path.relative_to(repository_root).as_posix()
    return {
        "analysis_id": config.analysis_id,
        "symbol": symbol,
        "source": {
            "relative_path": relative_source,
            "sha256": _sha256(source_path),
        },
        "configured_start_utc": config.analysis_start_utc.isoformat(),
        "configured_end_utc": config.analysis_end_utc.isoformat(),
        "coverage": {key: _json_value(value) for key, value in coverage.items()},
        "overall_statistics": _records(overall),
        "semester_statistics": _records(semesters),
        "extrema": _records(extrema),
        "chart_data": _records(chart_data),
        "definitions": definition_rows(config),
    }


def prepare_analysis_packets(
    config_path: Path,
    *,
    repository_root: Path,
    packet_directory: Path,
) -> pd.DataFrame:
    """Validate all configured pairs and write one workbook-input JSON per pair."""
    config, collection_config = load_analysis_config(
        config_path,
        repository_root=repository_root,
    )
    packet_directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for symbol in collection_config.symbols:
        source_path = canonical_csv_path(repository_root, collection_config, symbol)
        source_values = load_daily_price_volume(
            source_path,
            config.price_fields,
            config.volume_field,
        )
        values = filter_analysis_window(
            source_values,
            config.analysis_start_utc,
            config.analysis_end_utc,
        )
        payload = build_pair_payload(
            symbol,
            values,
            source_path=source_path,
            repository_root=repository_root,
            config=config,
        )
        packet_path = packet_directory / f"{symbol}.json"
        packet_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        rows.append(
            {
                "Symbol": symbol,
                "Status": "PREPARED",
                "Observations": payload["coverage"]["Observations"],
                "First open (UTC)": payload["coverage"]["First open (UTC)"],
                "Last open (UTC)": payload["coverage"]["Last open (UTC)"],
                "Missing daily openings": payload["coverage"][
                    "Missing daily openings within observed span"
                ],
                "Packet": str(packet_path),
            }
        )
    return pd.DataFrame(rows)
