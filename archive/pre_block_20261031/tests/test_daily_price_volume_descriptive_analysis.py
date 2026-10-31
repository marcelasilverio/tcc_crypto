"""Tests for daily OHLC price and USDT-volume descriptive analysis."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = REPOSITORY_ROOT / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from tcc_crypto.analysis.daily_descriptive import (
    daily_quote_volume_billions,
    describe_coverage,
    describe_semesters,
    describe_statistics,
    filter_analysis_window,
    natural_log_open_close,
    semester_label,
)
from tcc_crypto.data.exploratory import load_daily_price_volume


class DailyPriceVolumeDescriptiveAnalysisTests(unittest.TestCase):
    """Exercise statistical definitions, boundaries, and source validation."""

    def setUp(self) -> None:
        index = pd.date_range("2019-06-30", periods=5, freq="1D", tz="UTC")
        self.values = pd.DataFrame(
            {
                "open": [1.0, 2.0, 3.0, 4.0, 5.0],
                "high": [2.0, 3.0, 4.0, 5.0, 6.0],
                "low": [0.5, 1.5, 2.5, 3.5, 4.5],
                "close": [1.5, 2.5, 3.5, 4.5, 5.5],
                "quote_asset_volume": [0.0, 10.0, 20.0, 30.0, 40.0],
            },
            index=index,
        )

    def test_statistics_use_sample_estimators_linear_quartiles_and_volume_rules(
        self,
    ) -> None:
        statistics = describe_statistics(self.values)
        open_row = statistics.loc[statistics["Field"] == "open"].iloc[0]
        volume_row = statistics.loc[statistics["Field"] == "quote_asset_volume"].iloc[0]

        self.assertEqual(open_row["Observations"], 5)
        self.assertAlmostEqual(open_row["Mean"], 3.0)
        self.assertAlmostEqual(open_row["Sample variance"], 2.5)
        self.assertAlmostEqual(open_row["Q1"], 2.0)
        self.assertAlmostEqual(open_row["Q3"], 4.0)
        self.assertAlmostEqual(
            open_row["Coefficient of variation"],
            self.values["open"].std(ddof=1) / 3.0,
        )
        self.assertAlmostEqual(open_row["Skewness"], 0.0)
        self.assertAlmostEqual(open_row["Excess kurtosis"], -1.2)
        self.assertEqual(volume_row["Zero observations"], 1)
        self.assertAlmostEqual(volume_row["Zero share"], 0.2)
        self.assertEqual(volume_row["Total"], 100.0)

    def test_analysis_window_is_inclusive_and_excludes_2019_h1(self) -> None:
        filtered = filter_analysis_window(
            self.values,
            pd.Timestamp("2019-07-01", tz="UTC"),
            pd.Timestamp("2019-07-03", tz="UTC"),
        )
        self.assertEqual(filtered.index[0], pd.Timestamp("2019-07-01", tz="UTC"))
        self.assertEqual(filtered.index[-1], pd.Timestamp("2019-07-03", tz="UTC"))
        self.assertEqual(len(filtered), 3)

    def test_semester_boundaries_and_partial_status(self) -> None:
        self.assertEqual(
            semester_label(pd.Timestamp("2020-06-30", tz="UTC")), "2020-H1"
        )
        self.assertEqual(
            semester_label(pd.Timestamp("2020-07-01", tz="UTC")), "2020-H2"
        )
        values = self.values.loc["2019-07-01":]
        semesters = describe_semesters(
            values,
            analysis_start_utc=pd.Timestamp("2019-07-01", tz="UTC"),
            analysis_end_utc=pd.Timestamp("2019-12-31", tz="UTC"),
        )
        self.assertEqual(set(semesters["Semester"]), {"2019-H2"})
        self.assertEqual(set(semesters["Status"]), {"Partial"})

        final_partial = self.values.copy()
        final_partial.index = pd.date_range(
            "2026-07-01", periods=len(final_partial), freq="1D", tz="UTC"
        )
        final_semester = describe_semesters(
            final_partial,
            analysis_start_utc=pd.Timestamp("2019-07-01", tz="UTC"),
            analysis_end_utc=pd.Timestamp("2026-09-01", tz="UTC"),
        )
        self.assertEqual(set(final_semester["Semester"]), {"2026-H2"})
        self.assertEqual(set(final_semester["Status"]), {"Partial"})

    def test_coverage_counts_missing_days_inside_observed_span(self) -> None:
        values_with_gap = self.values.drop(self.values.index[2])
        coverage = describe_coverage("TESTUSDT", values_with_gap)
        self.assertEqual(coverage["Missing daily openings within observed span"], 1)

    def test_loader_rejects_non_midnight_timestamp_and_invalid_ohlc(self) -> None:
        frame = pd.DataFrame(
            {
                "open_time_ms": [
                    pd.Timestamp("2026-01-01T01:00:00Z").value // 1_000_000
                ],
                "open": ["10"],
                "high": ["9"],
                "low": ["8"],
                "close": ["11"],
                "quote_asset_volume": ["100"],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv.gz"
            frame.to_csv(path, index=False, compression="gzip")
            with self.assertRaisesRegex(ValueError, "daily boundaries"):
                load_daily_price_volume(path)

    def test_loader_rejects_negative_quote_volume(self) -> None:
        frame = pd.DataFrame(
            {
                "open_time_ms": [
                    pd.Timestamp("2026-01-01T00:00:00Z").value // 1_000_000
                ],
                "open": ["10"],
                "high": ["12"],
                "low": ["8"],
                "close": ["11"],
                "quote_asset_volume": ["-1"],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.csv.gz"
            frame.to_csv(path, index=False, compression="gzip")
            with self.assertRaisesRegex(ValueError, "negative quote-asset volume"):
                load_daily_price_volume(path)

    def test_plot_transformations_use_natural_log_and_preserve_gaps(self) -> None:
        values = self.values.drop(self.values.index[2])

        logged_prices = natural_log_open_close(values)
        volume_billions = daily_quote_volume_billions(values)

        self.assertAlmostEqual(logged_prices.iloc[0]["open"], 0.0)
        self.assertAlmostEqual(logged_prices.iloc[1]["close"], float(np.log(2.5)))
        self.assertTrue(logged_prices.iloc[2].isna().all())
        self.assertTrue(pd.isna(volume_billions.iloc[2]))
        self.assertAlmostEqual(volume_billions.iloc[-1], 40.0 / 1_000_000_000)


if __name__ == "__main__":
    unittest.main()
