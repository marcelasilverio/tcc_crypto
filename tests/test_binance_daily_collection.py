"""Tests for fixed-range Binance daily kline collection."""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = REPOSITORY_ROOT / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from tcc_crypto.collection.config import load_collection_config
from tcc_crypto.collection.pagination import collect_klines
from tcc_crypto.collection.validation import missing_kline_intervals, validate_klines
from tcc_crypto.paths import pair_output_paths

DAY_MS = 24 * 60 * 60 * 1000


def make_daily_kline(
    open_time_ms: int,
    *,
    duration_ms: int = DAY_MS,
) -> list[object]:
    """Build a minimal valid Binance 1d kline response row."""
    return [
        open_time_ms,
        "10.00000000",
        "12.00000000",
        "9.00000000",
        "11.00000000",
        "100.0",
        open_time_ms + duration_ms - 1,
        "1050.0",
        25,
        "40.0",
        "420.0",
        "0",
    ]


class BinanceDailyCollectionTests(unittest.TestCase):
    """Exercise daily configuration, pagination, and temporal validation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.config_path = (
            REPOSITORY_ROOT / "configs" / "binance_selected_usdt_daily_collection.json"
        )
        cls.config = load_collection_config(cls.config_path)

    def test_daily_configuration_preserves_hourly_universe_and_period(self) -> None:
        hourly_config = load_collection_config(
            REPOSITORY_ROOT / "configs" / "binance_selected_usdt_hourly_collection.json"
        )

        self.assertEqual(self.config.symbols, hourly_config.symbols)
        self.assertEqual(len(self.config.symbols), 40)
        self.assertEqual(self.config.interval, "1d")
        self.assertEqual(self.config.start_time_utc, hourly_config.start_time_utc)
        self.assertEqual(self.config.end_time_utc, hourly_config.end_time_utc)
        self.assertEqual(
            self.config.output_directory,
            Path("data/raw/binance/spot/1d"),
        )

    def test_daily_collection_uses_daily_interval_and_paginates(self) -> None:
        start = self.config.start_time_ms
        pages = [
            [make_daily_kline(start), make_daily_kline(start + DAY_MS)],
            [make_daily_kline(start + 2 * DAY_MS)],
        ]
        requests: list[dict[str, object]] = []

        def requester(parameters: dict[str, object]) -> object:
            requests.append(dict(parameters))
            return pages[len(requests) - 1]

        config = replace(self.config, limit=2)
        frame = collect_klines("BTCUSDT", config, page_requester=requester)

        self.assertEqual(len(frame), 3)
        self.assertEqual(requests[0]["interval"], "1d")
        self.assertEqual(requests[1]["startTime"], start + DAY_MS + 1)

    def test_daily_validation_reports_missing_day(self) -> None:
        start = self.config.start_time_ms
        frame = collect_klines(
            "BTCUSDT",
            self.config,
            page_requester=lambda parameters: [
                make_daily_kline(start),
                make_daily_kline(start + 2 * DAY_MS),
            ],
        )

        missing = missing_kline_intervals(frame, self.config)
        validation = validate_klines(frame, self.config)
        missing_check = validation.loc[
            validation["Check"] == "Missing days within observed span"
        ].iloc[0]

        self.assertEqual(missing, pd.DatetimeIndex(["2017-01-02"], tz="UTC"))
        self.assertEqual(missing_check["Actual"], 1)
        self.assertEqual(missing_check["Status"], "REVIEW")
        self.assertNotIn("FAIL", validation["Status"].tolist())

    def test_daily_validation_uses_24_hour_nominal_duration(self) -> None:
        start = self.config.start_time_ms
        frame = collect_klines(
            "BTCUSDT",
            self.config,
            page_requester=lambda parameters: [
                make_daily_kline(start, duration_ms=DAY_MS - 1)
            ],
        )
        validation = validate_klines(frame, self.config)

        shortened = validation.loc[
            validation["Check"] == "Shortened candle durations"
        ].iloc[0]
        outside = validation.loc[
            validation["Check"] == "Close times outside the nominal candle window"
        ].iloc[0]
        self.assertEqual(shortened["Status"], "REVIEW")
        self.assertEqual(outside["Status"], "OK")

    def test_daily_output_paths_are_separate_from_hourly_artifacts(self) -> None:
        paths = pair_output_paths("BTCUSDT", self.config, REPOSITORY_ROOT)

        self.assertIn("/spot/1d/BTCUSDT/", str(paths.raw_csv_gz))
        self.assertIn("BTCUSDT_1d_2017-01-01_2026-09-01", paths.raw_csv_gz.name)


if __name__ == "__main__":
    unittest.main()
