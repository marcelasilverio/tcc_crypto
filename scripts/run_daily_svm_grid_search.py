"""Run the approved development-only temporal SVC grid search."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from tcc_crypto.daily_features import load_daily_feature_config
from tcc_crypto.daily_svm_grid_search import (
    assess_symbol_eligibility,
    build_symbol_development_dataset,
    load_daily_svm_grid_search_config,
    run_temporal_grid_search,
    write_grid_search_outputs,
)

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/binance_daily_svm_grid_search.json"),
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--symbols",
        nargs="+",
        default=("BTCUSDT",),
        help="Symbols to execute; defaults to the approved operational BTCUSDT validation.",
    )
    scope.add_argument(
        "--all-symbols",
        action="store_true",
        help="Execute every configured candidate symbol, including explicit exclusions in the manifest.",
    )
    parser.add_argument(
        "--eligibility-only",
        action="store_true",
        help="Build data and eligibility evidence without fitting SVC candidates.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    config = load_daily_svm_grid_search_config(args.config)
    feature_config = load_daily_feature_config(config.feature_config)
    symbols = config.candidate_symbols if args.all_symbols else tuple(args.symbols)
    eligibility_frames: list[pd.DataFrame] = []

    for symbol in symbols:
        LOGGER.info("Building development-only dataset for %s", symbol)
        source = build_symbol_development_dataset(config, symbol)
        if args.eligibility_only:
            eligibility = assess_symbol_eligibility(
                source.dataset, symbol=symbol, config=config
            )
            eligibility_frames.append(eligibility)
            output_directory = config.output_directory / symbol
            output_directory.mkdir(parents=True, exist_ok=True)
            path = output_directory / "asset_eligibility.csv"
            eligibility.to_csv(
                path, index=False, date_format="%Y-%m-%dT%H:%M:%S%z"
            )
            LOGGER.info(
                "%s: %d of %d searches eligible; wrote %s",
                symbol,
                int((eligibility["status"] == "eligible").sum()),
                len(eligibility),
                path,
            )
            continue

        LOGGER.info("Running the temporal SVC grid for %s", symbol)
        result = run_temporal_grid_search(
            source.dataset,
            symbol=symbol,
            config=config,
            selection_config=feature_config.feature_selection,
        )
        eligibility_frames.append(result.eligibility)
        paths = write_grid_search_outputs(config, source, result)
        eligible = int((result.eligibility["status"] == "eligible").sum())
        LOGGER.info(
            "%s: %d eligible searches, %d candidate-fold fits, %d selections",
            symbol,
            eligible,
            len(result.fold_results),
            len(result.selected_configurations),
        )
        for path in paths:
            print(path)

    if args.all_symbols:
        manifest = pd.concat(eligibility_frames, ignore_index=True)
        manifest_path = config.output_directory / "asset_eligibility_manifest.csv"
        config.output_directory.mkdir(parents=True, exist_ok=True)
        manifest.to_csv(
            manifest_path, index=False, date_format="%Y-%m-%dT%H:%M:%S%z"
        )
        LOGGER.info("Wrote consolidated eligibility manifest: %s", manifest_path)
        print(manifest_path)


if __name__ == "__main__":
    main()
