"""Coverage, calendar-year volumes and daily trade counts from saved responses."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.collection.schema import KLINE_COLUMNS

COVERAGE_COLUMNS = {
    "1d": "First Daily Kline (1d, UTC)",
    "1s": "First Second Kline (1s, UTC)",
    "1m": "First Minute Kline (1m, UTC)",
    "1h": "First Hour Kline (1h, UTC)",
    "1w": "First Week Kline (1w, UTC)",
    "1M": "First Month Kline (1M, UTC)",
}


def earliest_table(raw: dict) -> pd.DataFrame:
    rows = []
    for item in raw["records"]:
        row = item["row"]
        rows.append(
            {
                "symbol": item["symbol"],
                "interval": item["interval"],
                "open_time_utc": pd.to_datetime(row[0], unit="ms", utc=True),
                "close_time_utc": pd.to_datetime(row[6], unit="ms", utc=True),
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
                "number_of_trades": int(row[8]),
            }
        )
    return pd.DataFrame(rows)


def coverage_table(raw: dict, source_url: str) -> pd.DataFrame:
    rows = []
    for item in raw["records"]:
        pair = dict(item["pair"])
        pair["Status"] = pair.pop("Current Status")
        pair.pop("Spot Trading Currently Allowed", None)
        for interval, row in item["records"].items():
            pair[COVERAGE_COLUMNS[interval]] = pd.to_datetime(
                row[0], unit="ms", utc=True
            )
        rows.append(pair)
    result = pd.DataFrame(rows)
    result["Missing Intervals"] = (
        result[list(COVERAGE_COLUMNS.values())].isna().sum(axis=1)
    )
    result["Source URL"] = source_url
    return result.sort_values(
        ["First Daily Kline (1d, UTC)", "Trading Pair"], na_position="last"
    ).reset_index(drop=True)


def monthly_table(raw: dict, source_url: str) -> pd.DataFrame:
    execution = pd.Timestamp(raw["execution_time"])
    rows = []
    for item in raw["records"]:
        pair = {
            k: v
            for k, v in item["pair"].items()
            if k != "Spot Trading Currently Allowed"
        }
        for row in item["records"]["1M"]:
            date = pd.to_datetime(row[0], unit="ms", utc=True)
            rows.append(
                {
                    **pair,
                    "Month Open (UTC)": date,
                    "Month Type": "Partial month"
                    if (date.year, date.month) == (execution.year, execution.month)
                    else "Closed month",
                    "Base Asset Volume": float(row[5]),
                    "Quote Asset Volume (BTC)": float(row[7]),
                    "Number of Trades": int(row[8]),
                    "Source URL": source_url,
                }
            )
    columns = [
        "Trading Pair",
        "Base Asset",
        "Quote Asset",
        "Current Status",
        "Month Open (UTC)",
        "Month Type",
        "Base Asset Volume",
        "Quote Asset Volume (BTC)",
        "Number of Trades",
        "Source URL",
    ]
    result = pd.DataFrame(rows, columns=columns)
    if result.duplicated(["Trading Pair", "Month Open (UTC)"]).any():
        raise ValueError("Duplicate monthly candles.")
    if (
        (
            result[
                ["Base Asset Volume", "Quote Asset Volume (BTC)", "Number of Trades"]
            ]
            < 0
        )
        .any()
        .any()
    ):
        raise ValueError("Negative monthly activity.")
    return result.sort_values(["Trading Pair", "Month Open (UTC)"]).reset_index(
        drop=True
    )


def annual_volume(
    monthly: pd.DataFrame, *, execution_time: pd.Timestamp, source_url: str
) -> pd.DataFrame:
    values = monthly.assign(Year=monthly["Month Open (UTC)"].dt.year)
    annual = values.groupby(
        ["Trading Pair", "Base Asset", "Quote Asset", "Current Status", "Year"],
        as_index=False,
    ).agg(
        **{
            "Base Asset Volume": ("Base Asset Volume", "sum"),
            "Quote Asset Volume (BTC)": ("Quote Asset Volume (BTC)", "sum"),
            "Number of Trades": ("Number of Trades", "sum"),
            "Observed Months": ("Month Open (UTC)", "nunique"),
            "First Month Open (UTC)": ("Month Open (UTC)", "min"),
            "Last Month Open (UTC)": ("Month Open (UTC)", "max"),
        }
    )
    annual["Period Type"] = annual["Year"].map(
        lambda year: "Year-to-date"
        if year == execution_time.year
        else "Historical year"
    )
    annual["Source URL"] = source_url
    return (
        annual[
            [
                "Trading Pair",
                "Base Asset",
                "Quote Asset",
                "Current Status",
                "Year",
                "Period Type",
                "Base Asset Volume",
                "Quote Asset Volume (BTC)",
                "Number of Trades",
                "Observed Months",
                "First Month Open (UTC)",
                "Last Month Open (UTC)",
                "Source URL",
            ]
        ]
        .sort_values(["Trading Pair", "Year"])
        .reset_index(drop=True)
    )


def annual_validation(monthly: pd.DataFrame, annual: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for field in ("Base Asset Volume", "Quote Asset Volume (BTC)", "Number of Trades"):
        actual, expected = monthly[field].sum(), annual[field].sum()
        tolerance = (
            0 if field == "Number of Trades" else max(1e-8, abs(float(actual)) * 1e-12)
        )
        rows.append(
            {
                "Check": field + " aggregation",
                "Actual": actual,
                "Expected": expected,
                "Difference": abs(actual - expected),
                "Tolerance": tolerance,
                "Status": "OK" if abs(actual - expected) <= tolerance else "FAIL",
            }
        )
    return pd.DataFrame(rows)


def trade_counts(
    raw: dict, *, start_utc: pd.Timestamp, source_url: str
) -> pd.DataFrame:
    rows = []
    for item in raw["records"]:
        frame = pd.DataFrame(item["records"]["1d"], columns=KLINE_COLUMNS)
        if frame.empty:
            first, last, observed, missing, total = pd.NaT, pd.NaT, 0, 0, 0
        else:
            times = pd.to_datetime(frame["open_time_ms"], unit="ms", utc=True)
            counts = pd.to_numeric(frame["number_of_trades"], errors="raise")
            if times.duplicated().any() or (counts < 0).any():
                raise ValueError("Duplicate candles or negative trade counts.")
            first, last = (
                times.min(),
                pd.to_datetime(frame["close_time_ms"].max(), unit="ms", utc=True),
            )
            observed = len(times)
            missing = int((times.max() - times.min()).days + 1 - observed)
            total = int(counts.sum())
        rows.append(
            {
                **item["pair"],
                "Collection Start (UTC)": start_utc,
                "Collection End (UTC)": pd.Timestamp(raw["cutoff"]),
                "First Observed Kline (UTC)": first,
                "Last Observed Kline Close (UTC)": last,
                "Observed Daily Klines": observed,
                "Missing Days Within Observed Span": missing,
                "Total Number of Trades": total,
                "Source URL": source_url,
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(
            ["Total Number of Trades", "Trading Pair"], ascending=[False, True]
        )
        .reset_index(drop=True)
    )


def calculate_market_exploration(
    analysis: str, raw: dict, *, start_utc: pd.Timestamp, source_url: str
) -> dict[str, pd.DataFrame]:
    if analysis == "earliest":
        return {"earliest": earliest_table(raw)}
    if analysis == "coverage":
        return {"coverage": coverage_table(raw, source_url)}
    if analysis == "annual-volume":
        monthly = monthly_table(raw, source_url)
        if monthly.empty:
            raise ValueError("No monthly observations returned.")
        annual = annual_volume(
            monthly,
            execution_time=pd.Timestamp(raw["execution_time"]),
            source_url=source_url,
        )
        return {
            "monthly": monthly,
            "annual": annual,
            "validation": annual_validation(monthly, annual),
        }
    counts = trade_counts(raw, start_utc=start_utc, source_url=source_url)
    checks = [
        ("Duplicate trading pairs", int(counts["Trading Pair"].duplicated().sum())),
        (
            "Negative total trade counts",
            int((counts["Total Number of Trades"] < 0).sum()),
        ),
        (
            "Negative missing-day counts",
            int((counts["Missing Days Within Observed Span"] < 0).sum()),
        ),
        ("Symbols lost during collection", len(raw["records"]) - len(counts)),
    ]
    return {
        "trade_counts": counts,
        "validation": pd.DataFrame(
            [
                {
                    "Check": name,
                    "Actual": count,
                    "Expected": 0,
                    "Status": "OK" if count == 0 else "FAIL",
                }
                for name, count in checks
            ]
        ),
    }
