"""Tests for hourly OHLC price descriptive analysis."""

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

from tcc_crypto.hourly_price_descriptive_analysis import (  # noqa: E402
    DescriptiveAnalysisConfig,
    _write_workbook,
    describe_coverage,
    describe_extremes,
    describe_price_levels,
    load_hourly_prices,
)


class HourlyPriceDescriptiveAnalysisTests(unittest.TestCase):
    """Exercise statistical definitions and source-series validation."""

    def setUp(self) -> None:
        index = pd.date_range("2026-01-01", periods=4, freq="1h", tz="UTC")
        self.prices = pd.DataFrame(
            {
                "open": [1.0, 2.0, 3.0, 4.0],
                "high": [2.0, 3.0, 4.0, 5.0],
                "low": [0.5, 1.5, 2.5, 3.5],
                "close": [1.5, 2.5, 3.5, 4.5],
            },
            index=index,
        )

    def test_price_statistics_use_sample_estimators_and_quartiles(self) -> None:
        summary = describe_price_levels("TESTUSDT", self.prices)
        open_summary = summary.loc[summary["Price field"] == "open"].iloc[0]

        self.assertEqual(open_summary["Observations"], 4)
        self.assertEqual(open_summary["Missing values"], 0)
        self.assertAlmostEqual(open_summary["Mean (USDT)"], 2.5)
        self.assertAlmostEqual(open_summary["Median (USDT)"], 2.5)
        self.assertAlmostEqual(open_summary["Standard deviation (USDT)"], 1.2909944487)
        self.assertAlmostEqual(open_summary["Variance (USDT squared)"], 5 / 3)
        self.assertAlmostEqual(open_summary["Q1 (USDT)"], 1.75)
        self.assertAlmostEqual(open_summary["Q3 (USDT)"], 3.25)
        self.assertAlmostEqual(open_summary["Interquartile range (USDT)"], 1.5)
        self.assertAlmostEqual(open_summary["Skewness"], 0.0)
        self.assertAlmostEqual(open_summary["Excess kurtosis"], -1.2)

    def test_coverage_counts_only_gaps_inside_observed_span(self) -> None:
        prices_with_gap = self.prices.drop(self.prices.index[1])
        coverage = describe_coverage("TESTUSDT", prices_with_gap)

        self.assertEqual(coverage["Observations"], 3)
        self.assertEqual(coverage["Missing hours within observed span"], 1)
        self.assertEqual(str(coverage["First open (UTC)"].tz), "UTC")

    def test_extrema_include_utc_timestamps(self) -> None:
        extrema = describe_extremes("TESTUSDT", self.prices)
        close_row = extrema.loc[extrema["Price field"] == "close"].iloc[0]

        self.assertEqual(close_row["Minimum (USDT)"], 1.5)
        self.assertEqual(close_row["Maximum (USDT)"], 4.5)
        self.assertEqual(close_row["Maximum timestamp (UTC)"], self.prices.index[-1])

    def test_loader_rejects_ohlc_inconsistency(self) -> None:
        frame = pd.DataFrame(
            {
                "open_time_ms": [1_767_225_600_000],
                "open": ["10"],
                "high": ["9"],
                "low": ["8"],
                "close": ["11"],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv.gz"
            frame.to_csv(path, index=False, compression="gzip")
            with self.assertRaisesRegex(ValueError, "OHLC consistency"):
                load_hourly_prices(path, ("open", "high", "low", "close"))

    def test_workbook_preserves_utc_as_iso_text(self) -> None:
        summary = describe_price_levels("TESTUSDT", self.prices)
        coverage = pd.DataFrame([describe_coverage("TESTUSDT", self.prices)])
        extrema = describe_extremes("TESTUSDT", self.prices)
        config = DescriptiveAnalysisConfig(
            analysis_id="test",
            collection_config_path=Path("collection.json"),
            price_fields=("open", "high", "low", "close"),
            chart_fields=("open", "close"),
            quantiles=(0.25, 0.5, 0.75),
            standard_deviation_ddof=1,
            kurtosis_definition="Fisher excess kurtosis",
            output_directory=Path("outputs"),
        )
        with tempfile.TemporaryDirectory() as directory:
            workbook_path = Path(directory) / "analysis.xlsx"
            _write_workbook(workbook_path, summary, coverage, extrema, config)
            excel_coverage = pd.read_excel(workbook_path, sheet_name="Coverage")
            excel_extrema = pd.read_excel(workbook_path, sheet_name="Extrema")

        self.assertEqual(excel_coverage.loc[0, "First open (UTC)"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(excel_extrema.loc[0, "Minimum timestamp (UTC)"], "2026-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
