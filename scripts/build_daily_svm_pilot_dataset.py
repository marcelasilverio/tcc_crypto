"""Build the approved BTCUSDT 2019H2 pilot modeling dataset."""

from __future__ import annotations

import argparse
from pathlib import Path

from tcc_crypto.daily_modeling_dataset import (
    build_daily_modeling_dataset,
    load_daily_modeling_dataset_config,
    write_daily_modeling_dataset,
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
    dataset = build_daily_modeling_dataset(config)
    csv_path, metadata_path = write_daily_modeling_dataset(config, dataset)
    print(csv_path)
    print(metadata_path)


if __name__ == "__main__":
    main()
