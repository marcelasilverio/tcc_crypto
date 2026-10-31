"""Inspection workbook for already calculated final classifier evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import pandas as pd

from tcc_crypto.reporting.workbooks import configuration_table, write_workbook


def _configuration_items(configuration: Mapping[str, object], prefix: str = ""):
    """Keep nested provenance inspectable instead of clipping one large JSON cell."""
    for key, value in configuration.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            yield from _configuration_items(value, name)
        else:
            yield name, value


def write_final_workbook(
    path: Path,
    tables: Mapping[str, pd.DataFrame],
    configuration: Mapping[str, object],
    *,
    overwrite: bool = False,
) -> Path:
    evaluation = configuration.get("evaluation", {})
    data = configuration.get("full_period", {}).get("data", {})
    summary = {
        "Evaluation": "Frozen-parameter daily walk-forward",
        "Evaluation identifier": evaluation.get("evaluation_id", ""),
        "Symbol": data.get("symbol", ""),
        "Feature start UTC": evaluation.get("feature_start_utc", ""),
        "Feature end UTC": evaluation.get("feature_end_utc", ""),
        "Excluded gap observations": evaluation.get("gap", ""),
        "Comparison sample": "Same successful dates for all four classifiers; omissions retained in predictions",
        "Universe": "Ex-post fixed 2026 snapshot; not a historically reconstructed investable universe",
        "Interpretation": "Classifier performance only; no portfolio returns or financial backtest",
        "Attempted model observations": len(tables["predictions"]),
        "Infinite curve thresholds": "CSV retains infinity; Excel displays non-finite thresholds as blank cells",
    }
    return write_workbook(
        path,
        {
            "Summary": configuration_table(summary),
            "Metrics": tables["metrics"],
            "Eligibility": tables["eligibility"],
            "Frozen configurations": tables["selected_configurations"],
            "Dated predictions": tables["predictions"],
            "ROC points": tables["roc"],
            "Precision recall points": tables["precision_recall"],
            "Configuration": configuration_table(
                dict(_configuration_items(configuration))
            ),
        },
        overwrite=overwrite,
    )
