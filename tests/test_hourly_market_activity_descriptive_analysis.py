"""Tests for hourly market-activity descriptive analysis."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = REPOSITORY_ROOT / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from tcc_crypto.hourly_market_activity_descriptive_analysis import (  # noqa: E402
    ACTIVITY_FIELDS,
    activity_unit,
    describe_activity_extremes,
    describe_market_activity,
    load_hourly_market_activity,
)


class HourlyMarketActivityDescriptiveAnalysisTests(unittest.TestCase):
    """Exercise activity statistics, units, and source validation."""

    def setUp(self) -> None:
        index = pd.date_range("2026-01-01", periods=4, freq="1h", tz="UTC")
        self.activity = pd.DataFrame(
            {
                "base_asset_volume": [0.0, 2.0, 4.0, 6.0],
                "quote_asset_volume": [0.0, 20.0, 40.0, 60.0],
                "number_of_trades": [0.0, 2.0, 4.0, 6.0],
                "taker_buy_base_asset_volume": [0.0, 1.0, 2.0, 3.0],
                "taker_buy_quote_asset_volume": [0.0, 10.0, 20.0, 30.0],
            },
            index=index,
        )

    def test_statistics_include_totals_zeros_and_sample_dispersion(self) -> None:
        summary = describe_market_activity("TESTUSDT", self.activity)
        base = summary.loc[summary["Activity field"] == "base_asset_volume"].iloc[0]

        self.assertEqual(base["Unit"], "TEST")
        self.assertEqual(base["Observations"], 4)
        self.assertEqual(base["Zero observations"], 1)
        self.assertEqual(base["Zero share (%)"], 25.0)
        self.assertEqual(base["Total"], 12.0)
        self.assertEqual(base["Mean per hour"], 3.0)
        self.assertAlmostEqual(base["Standard deviation per hour"], 2.5819888975)
        self.assertEqual(base["Q1 per hour"], 1.5)
        self.assertEqual(base["Q3 per hour"], 4.5)

    def test_units_distinguish_base_quote_and_trade_counts(self) -> None:
        self.assertEqual(activity_unit("BTCUSDT", "base_asset_volume"), "BTC")
        self.assertEqual(activity_unit("BTCUSDT", "quote_asset_volume"), "USDT")
        self.assertEqual(activity_unit("BTCUSDT", "number_of_trades"), "trades")

    def test_extrema_include_utc_timestamps(self) -> None:
        extrema = describe_activity_extremes("TESTUSDT", self.activity)
        trades = extrema.loc[extrema["Activity field"] == "number_of_trades"].iloc[0]

        self.assertEqual(trades["Maximum per hour"], 6.0)
        self.assertEqual(trades["Maximum timestamp (UTC)"], self.activity.index[-1])

    def test_loader_rejects_taker_volume_above_total_volume(self) -> None:
        frame = pd.DataFrame(
            {
                "open_time_ms": [1_767_225_600_000],
                "base_asset_volume": ["10"],
                "quote_asset_volume": ["100"],
                "number_of_trades": ["2"],
                "taker_buy_base_asset_volume": ["11"],
                "taker_buy_quote_asset_volume": ["50"],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv.gz"
            frame.to_csv(path, index=False, compression="gzip")
            with self.assertRaisesRegex(ValueError, "above total volume"):
                load_hourly_market_activity(path, ACTIVITY_FIELDS)

    def test_loader_rejects_non_integer_trade_counts(self) -> None:
        frame = pd.DataFrame(
            {
                "open_time_ms": [1_767_225_600_000],
                "base_asset_volume": ["10"],
                "quote_asset_volume": ["100"],
                "number_of_trades": ["2.5"],
                "taker_buy_base_asset_volume": ["5"],
                "taker_buy_quote_asset_volume": ["50"],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv.gz"
            frame.to_csv(path, index=False, compression="gzip")
            with self.assertRaisesRegex(ValueError, "non-integer trade counts"):
                load_hourly_market_activity(path, ACTIVITY_FIELDS)


if __name__ == "__main__":
    unittest.main()
