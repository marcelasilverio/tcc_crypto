"""Tests for fixed-range Binance hourly kline collection."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import openpyxl
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = REPOSITORY_ROOT / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from tcc_crypto.binance_hourly_collection import (  # noqa: E402
    collect_hourly_klines,
    collect_symbol_outputs,
    collect_to_checkpoint,
    load_collection_config,
    load_raw_csv_gz,
    missing_hourly_intervals,
    pair_output_paths,
    validate_hourly_klines,
    write_pair_workbook,
)


def make_kline(
    open_time_ms: int,
    *,
    open_price: str = "10.00000000",
    high: str = "12.00000000",
    low: str = "9.00000000",
    close: str = "11.00000000",
) -> list[object]:
    """Build a minimal valid Binance 1h kline response row."""
    return [
        open_time_ms,
        open_price,
        high,
        low,
        close,
        "100.0",
        open_time_ms + 3_599_999,
        "1050.0",
        25,
        "40.0",
        "420.0",
        "0",
    ]


class BinanceHourlyCollectionTests(unittest.TestCase):
    """Exercise pagination, temporal validation, and immutable export."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.config_path = (
            REPOSITORY_ROOT
            / "configs"
            / "binance_selected_usdt_hourly_collection.json"
        )
        cls.config = load_collection_config(cls.config_path)

    def test_configuration_contains_the_approved_universe(self) -> None:
        expected = (
            "BTCUSDT",
            "FLOKIUSDT",
            "ETHUSDT",
            "BONKUSDT",
            "SOLUSDT",
            "XRPUSDT",
            "SHIBUSDT",
            "DOGEUSDT",
            "BNBUSDT",
            "ADAUSDT",
            "LTCUSDT",
            "PEPEUSDT",
            "SUIUSDT",
            "LINKUSDT",
            "AVAXUSDT",
            "DOTUSDT",
            "TRXUSDT",
            "WIFUSDT",
            "NEARUSDT",
            "NEIROUSDT",
            "AAVEUSDT",
            "WLDUSDT",
            "XLMUSDT",
            "ZECUSDT",
            "FILUSDT",
            "BCHUSDT",
            "LUNAUSDT",
            "UNIUSDT",
            "GALAUSDT",
            "FETUSDT",
        )
        self.assertEqual(self.config.symbols, expected)
        self.assertEqual(self.config.interval, "1h")
        self.assertEqual(
            self.config.end_time_utc,
            pd.Timestamp("2026-09-01T23:59:59.999Z"),
        )

    def test_collection_paginates_without_duplicates(self) -> None:
        start = self.config.start_time_ms
        pages = [
            [make_kline(start), make_kline(start + 3_600_000)],
            [make_kline(start + 7_200_000)],
        ]
        requests: list[dict[str, object]] = []

        def requester(parameters: dict[str, object]) -> object:
            requests.append(dict(parameters))
            return pages[len(requests) - 1]

        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        payload["limit"] = 2
        with tempfile.TemporaryDirectory() as directory:
            temporary_config_path = Path(directory) / "config.json"
            temporary_config_path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_collection_config(temporary_config_path)

        frame = collect_hourly_klines(
            "BTCUSDT",
            config,
            page_requester=requester,
        )

        self.assertEqual(len(frame), 3)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1]["startTime"], start + 3_600_000 + 1)
        self.assertEqual(int(frame["open_time_ms"].duplicated().sum()), 0)
        self.assertEqual(frame.loc[0, "open"], "10.00000000")

    def test_validation_reports_missing_hour_without_failing_raw_data(self) -> None:
        start = self.config.start_time_ms
        rows = [make_kline(start), make_kline(start + 7_200_000)]

        def requester(parameters: dict[str, object]) -> object:
            del parameters
            return rows

        frame = collect_hourly_klines(
            "BTCUSDT",
            self.config,
            page_requester=requester,
        )
        validation = validate_hourly_klines(frame, self.config)
        missing = missing_hourly_intervals(frame)
        missing_check = validation.loc[
            validation["Check"] == "Missing hours within observed span"
        ].iloc[0]

        self.assertEqual(len(missing), 1)
        self.assertEqual(missing_check["Actual"], 1)
        self.assertEqual(missing_check["Status"], "REVIEW")
        self.assertNotIn("FAIL", validation["Status"].tolist())

    def test_validation_rejects_ohlc_inconsistency(self) -> None:
        start = self.config.start_time_ms
        rows = [make_kline(start, high="10.0", close="11.0")]

        def requester(parameters: dict[str, object]) -> object:
            del parameters
            return rows

        frame = collect_hourly_klines(
            "BTCUSDT",
            self.config,
            page_requester=requester,
        )
        validation = validate_hourly_klines(frame, self.config)
        ohlc_check = validation.loc[
            validation["Check"] == "OHLC consistency violations"
        ].iloc[0]
        self.assertEqual(ohlc_check["Status"], "FAIL")

    def test_pair_workbook_has_expected_sheets_and_is_immutable(self) -> None:
        start = self.config.start_time_ms
        rows = [make_kline(start)]

        def requester(parameters: dict[str, object]) -> object:
            del parameters
            return rows

        frame = collect_hourly_klines(
            "BTCUSDT",
            self.config,
            page_requester=requester,
        )
        validation = validate_hourly_klines(frame, self.config)
        metadata = pd.DataFrame(
            [("Trading pair", "BTCUSDT")],
            columns=["Field", "Value"],
        )
        missing = missing_hourly_intervals(frame)

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "BTCUSDT.xlsx"
            write_pair_workbook(
                output_path,
                frame,
                metadata,
                validation,
                missing,
            )
            workbook = openpyxl.load_workbook(output_path, read_only=True)
            self.assertEqual(
                workbook.sheetnames,
                ["Klines", "Metadata", "Validation", "Missing Intervals"],
            )
            workbook.close()
            with self.assertRaises(FileExistsError):
                write_pair_workbook(
                    output_path,
                    frame,
                    metadata,
                    validation,
                    missing,
                )

    def test_checkpoint_resumes_after_the_last_persisted_page(self) -> None:
        start = self.config.start_time_ms
        config = replace(
            self.config,
            end_time_utc=pd.Timestamp(start + 4 * 3_600_000 - 1, unit="ms", tz="UTC"),
            limit=2,
            output_directory=Path("raw"),
        )

        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory)
            paths = pair_output_paths("BTCUSDT", config, repository_root)
            first_attempt_calls = 0

            def interrupted_requester(parameters: dict[str, object]) -> object:
                nonlocal first_attempt_calls
                first_attempt_calls += 1
                if first_attempt_calls == 1:
                    return [make_kline(start), make_kline(start + 3_600_000)]
                raise RuntimeError("simulated interruption")

            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                collect_to_checkpoint(
                    "BTCUSDT",
                    config,
                    paths,
                    page_requester=interrupted_requester,
                )

            resumed_start_times: list[int] = []

            def resumed_requester(parameters: dict[str, object]) -> object:
                resumed_start_times.append(int(parameters["startTime"]))
                if len(resumed_start_times) == 1:
                    return [
                        make_kline(start + 2 * 3_600_000),
                        make_kline(start + 3 * 3_600_000),
                    ]
                return []

            collect_to_checkpoint(
                "BTCUSDT",
                config,
                paths,
                page_requester=resumed_requester,
            )

            self.assertEqual(resumed_start_times[0], start + 3_600_000 + 1)
            partial = pd.read_csv(paths.partial_csv, dtype=str)
            self.assertEqual(len(partial), 4)
            self.assertEqual(partial["open"].tolist(), ["10.00000000"] * 4)

    def test_complete_outputs_are_validated_and_reused_without_network(self) -> None:
        start = pd.Timestamp("2026-09-01T00:00:00Z")
        end = pd.Timestamp("2026-09-01T23:59:59.999Z")
        config = replace(
            self.config,
            start_time_utc=start,
            end_time_utc=end,
            output_directory=Path("raw"),
        )
        rows = [make_kline(config.start_time_ms + hour * 3_600_000) for hour in range(24)]

        def requester(parameters: dict[str, object]) -> object:
            del parameters
            return rows

        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory)
            collected = collect_symbol_outputs(
                "BTCUSDT",
                1,
                config,
                repository_root,
                page_requester=requester,
            )
            paths = pair_output_paths("BTCUSDT", config, repository_root)

            self.assertEqual(collected["Status"], "COLLECTED")
            self.assertTrue(paths.raw_csv_gz.exists())
            self.assertTrue(paths.workbook.exists())
            self.assertTrue(paths.metadata_json.exists())
            self.assertFalse(paths.partial_csv.exists())
            self.assertFalse(paths.checkpoint_json.exists())
            self.assertEqual(paths.directory.name, "BTCUSDT")

            raw_frame = load_raw_csv_gz(paths.raw_csv_gz)
            self.assertEqual(raw_frame.loc[0, "open"], "10.00000000")

            reused = collect_symbol_outputs(
                "BTCUSDT",
                1,
                config,
                repository_root,
                page_requester=lambda parameters: self.fail(
                    f"Network should not be called: {parameters}"
                ),
            )
            self.assertEqual(reused["Status"], "VALIDATED_EXISTING")
            self.assertEqual(reused["Rows"], 24)
            self.assertEqual(reused["Missing Hours"], 0)
            self.assertIsNotNone(reused["Raw CSV SHA-256"])
            self.assertIsNotNone(reused["Workbook SHA-256"])


if __name__ == "__main__":
    unittest.main()
