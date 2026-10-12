"""Run the approved BTCUSDT 2019H2 default-SVC pilot."""

from __future__ import annotations

import argparse
from pathlib import Path

from tcc_crypto.daily_features import load_daily_feature_config
from tcc_crypto.daily_modeling_dataset import (
    build_daily_modeling_dataset,
    load_daily_modeling_dataset_config,
    write_daily_modeling_dataset,
)
from tcc_crypto.daily_svm_pilot import (
    run_default_svc_rolling_pilot,
    write_daily_svm_pilot_results,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/binance_daily_svm_pilot_dataset.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_daily_modeling_dataset_config(args.config)
    feature_config = load_daily_feature_config(config.feature_config)
    dataset = build_daily_modeling_dataset(config)
    dataset_paths = write_daily_modeling_dataset(config, dataset)
    result = run_default_svc_rolling_pilot(
        dataset,
        selection_config=feature_config.feature_selection,
    )
    result_paths = write_daily_svm_pilot_results(config, result)
    for path in (*dataset_paths, *result_paths):
        print(path)


if __name__ == "__main__":
    main()
