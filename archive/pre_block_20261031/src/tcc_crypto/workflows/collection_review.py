"""Explicit collection entrypoints for the hourly and daily review notebooks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tcc_crypto.collection.config import load_collection_config
from tcc_crypto.collection.pipeline import run_collection
from tcc_crypto.paths import pair_output_paths, repository_root
from tcc_crypto.reporting.workbooks import configuration_table

COLLECTION_CONFIGS = {
    "1h": Path("configs/binance_selected_usdt_hourly_collection.json"),
    "1d": Path("configs/binance_selected_usdt_daily_collection.json"),
}


def configuration(interval: str, *, root: Path | None = None):
    return load_collection_config(repository_root(root) / COLLECTION_CONFIGS[interval])


def inventory(config, *, root: Path | None = None) -> pd.DataFrame:
    root = repository_root(root)
    return pd.DataFrame(
        [
            {
                "Symbol": symbol,
                "Raw CSV": str(pair_output_paths(symbol, config, root).raw_csv_gz),
                "Metadata": str(pair_output_paths(symbol, config, root).metadata_json),
                "Workbook": str(pair_output_paths(symbol, config, root).workbook),
            }
            for symbol in config.symbols
        ]
    )


def summary(config) -> pd.DataFrame:
    return configuration_table(
        {
            "Collection": config.collection_id,
            "Symbols": config.symbols,
            "Interval": config.interval,
            "Start UTC": config.start_time_utc,
            "End UTC": config.end_time_utc,
        }
    )


def collect(config, *, root: Path | None = None):
    return run_collection(config, repository_root=repository_root(root))
