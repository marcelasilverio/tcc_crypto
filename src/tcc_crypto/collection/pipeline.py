"""Collection: pipeline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

from tcc_crypto.collection.checkpoints import collect_to_checkpoint
from tcc_crypto.collection.client import PageRequester
from tcc_crypto.collection.config import CollectionConfig
from tcc_crypto.collection.metadata import (
    _sha256_file,
    _write_pair_metadata_json,
    build_metadata,
)
from tcc_crypto.collection.schema import _interval_spec
from tcc_crypto.collection.storage import (
    _compress_partial_csv,
    _load_raw_csv,
    load_raw_csv_gz,
)
from tcc_crypto.collection.validation import (
    _assert_collection_complete,
    missing_kline_intervals,
    nonstandard_candle_durations,
    validate_klines,
)
from tcc_crypto.collection.workbooks import (
    _validate_workbook,
    _write_manifest,
    write_pair_workbook,
)
from tcc_crypto.paths import PairOutputPaths, pair_output_paths


def _pair_result(
    symbol: str,
    selection_rank: int,
    status: str,
    frame: pd.DataFrame,
    paths: PairOutputPaths,
    config: CollectionConfig,
) -> dict[str, object]:
    interval_plural = str(_interval_spec(config.interval)["plural"]).title()
    missing = missing_kline_intervals(frame, config)
    shortened = nonstandard_candle_durations(frame, config)
    return {
        "Selection Rank": selection_rank,
        "Trading Pair": symbol,
        "Status": status,
        "Rows": len(frame),
        f"Missing {interval_plural}": len(missing),
        "Shortened Candles": len(shortened),
        "First Open (UTC)": frame["open_time_utc"].min().isoformat(),
        "Last Close (UTC)": frame["close_time_utc"].max().isoformat(),
        "Raw CSV": str(paths.raw_csv_gz),
        "Raw CSV SHA-256": _sha256_file(paths.raw_csv_gz),
        "Workbook": str(paths.workbook),
        "Workbook SHA-256": _sha256_file(paths.workbook),
        "Metadata": str(paths.metadata_json),
        "Error": None,
    }


def collect_symbol_outputs(
    symbol: str,
    selection_rank: int,
    config: CollectionConfig,
    repository_root: Path,
    *,
    page_requester: PageRequester | None = None,
) -> dict[str, object]:
    """Validate existing outputs or collect and create all pair artifacts."""
    paths = pair_output_paths(symbol, config, repository_root)
    paths.directory.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now(timezone.utc)

    if paths.raw_csv_gz.exists():
        frame = load_raw_csv_gz(paths.raw_csv_gz)
        validation = validate_klines(frame, config)
        _assert_collection_complete(symbol, frame, validation, config)
        raw_hash = _sha256_file(paths.raw_csv_gz)
        metadata = build_metadata(
            symbol,
            frame,
            config,
            repository_root,
            collected_at,
            raw_hash,
        )
        missing = missing_kline_intervals(frame, config)
        if paths.workbook.exists():
            _validate_workbook(paths.workbook, len(frame), config)
        else:
            write_pair_workbook(
                paths.workbook,
                frame,
                metadata,
                validation,
                missing,
                config,
            )
        _write_pair_metadata_json(paths, metadata, validation)
        paths.partial_csv.unlink(missing_ok=True)
        paths.checkpoint_json.unlink(missing_ok=True)
        return _pair_result(
            symbol,
            selection_rank,
            "VALIDATED_EXISTING",
            frame,
            paths,
            config,
        )

    if paths.workbook.exists():
        raise ValueError(
            "A derived workbook exists without its canonical raw CSV; refusing "
            f"to infer raw data from Excel: {paths.workbook}"
        )

    collect_to_checkpoint(
        symbol,
        config,
        paths,
        page_requester=page_requester,
    )
    frame = _load_raw_csv(paths.partial_csv, compressed=False)
    validation = validate_klines(frame, config)
    _assert_collection_complete(symbol, frame, validation, config)
    _compress_partial_csv(paths)
    raw_hash = _sha256_file(paths.raw_csv_gz)
    metadata = build_metadata(
        symbol,
        frame,
        config,
        repository_root,
        collected_at,
        raw_hash,
    )
    missing = missing_kline_intervals(frame, config)
    write_pair_workbook(
        paths.workbook,
        frame,
        metadata,
        validation,
        missing,
        config,
    )
    _write_pair_metadata_json(paths, metadata, validation)
    paths.partial_csv.unlink(missing_ok=True)
    paths.checkpoint_json.unlink(missing_ok=True)
    return _pair_result(symbol, selection_rank, "COLLECTED", frame, paths, config)


def run_collection(
    config: CollectionConfig,
    repository_root: Path,
    *,
    symbols: Sequence[str] | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[pd.DataFrame, Path]:
    """Run the full collection or an approved subset and write a manifest."""
    execution_symbols = (
        config.symbols if symbols is None else tuple(str(symbol) for symbol in symbols)
    )
    if not execution_symbols:
        raise ValueError("At least one collection symbol is required.")
    if len(set(execution_symbols)) != len(execution_symbols):
        raise ValueError("The execution symbol list contains duplicates.")
    unknown_symbols = [
        symbol for symbol in execution_symbols if symbol not in config.symbols
    ]
    if unknown_symbols:
        raise ValueError(
            "Execution symbols are not in the approved configuration: "
            + ", ".join(unknown_symbols)
        )

    selection_ranks = {
        symbol: rank for rank, symbol in enumerate(config.symbols, start=1)
    }
    execution_time = datetime.now(timezone.utc)
    results: list[dict[str, object]] = []
    workers = max(1, min(config.max_workers, len(execution_symbols)))
    missing_column = f"Missing {str(_interval_spec(config.interval)['plural']).title()}"

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                collect_symbol_outputs,
                symbol,
                selection_ranks[symbol],
                config,
                repository_root,
            ): (selection_ranks[symbol], symbol)
            for symbol in execution_symbols
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            rank, symbol = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {
                    "Selection Rank": rank,
                    "Trading Pair": symbol,
                    "Status": "FAILED",
                    "Rows": None,
                    missing_column: None,
                    "Shortened Candles": None,
                    "First Open (UTC)": None,
                    "Last Close (UTC)": None,
                    "Raw CSV": None,
                    "Raw CSV SHA-256": None,
                    "Workbook": None,
                    "Workbook SHA-256": None,
                    "Metadata": None,
                    "Error": str(error),
                }
            results.append(result)
            if progress_callback is not None:
                progress_callback(
                    f"Completed {completed}/{len(execution_symbols)}: "
                    f"{symbol} ({result['Status']})"
                )

    results_frame = (
        pd.DataFrame(results).sort_values("Selection Rank").reset_index(drop=True)
    )
    manifest_path = _write_manifest(
        results_frame,
        config,
        repository_root,
        execution_time,
        execution_symbols,
    )
    return results_frame, manifest_path
