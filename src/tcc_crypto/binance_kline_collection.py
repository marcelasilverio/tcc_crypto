"""Interval-neutral public interface for Binance Spot kline collection.

The implementation remains in the historical hourly module so existing
notebooks and imports continue to work. New collection workflows should import
this module.
"""

from tcc_crypto.binance_hourly_collection import (  # noqa: F401
    CollectionConfig,
    PairOutputPaths,
    build_metadata,
    collect_klines,
    collect_symbol_outputs,
    collect_symbol_to_workbook,
    collect_to_checkpoint,
    find_repository_root,
    load_collection_config,
    load_raw_csv_gz,
    missing_kline_intervals,
    nonstandard_candle_durations,
    pair_output_path,
    pair_output_paths,
    request_json,
    run_collection,
    validate_klines,
    write_pair_workbook,
)

__all__ = [
    "CollectionConfig",
    "PairOutputPaths",
    "build_metadata",
    "collect_klines",
    "collect_symbol_outputs",
    "collect_symbol_to_workbook",
    "collect_to_checkpoint",
    "find_repository_root",
    "load_collection_config",
    "load_raw_csv_gz",
    "missing_kline_intervals",
    "nonstandard_candle_durations",
    "pair_output_path",
    "pair_output_paths",
    "request_json",
    "run_collection",
    "validate_klines",
    "write_pair_workbook",
]
