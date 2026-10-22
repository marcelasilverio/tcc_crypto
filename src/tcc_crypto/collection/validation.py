"""Collection: validation."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.collection.config import CollectionConfig
from tcc_crypto.collection.schema import DECIMAL_TEXT_COLUMNS, _interval_spec


def missing_kline_intervals(
    frame: pd.DataFrame,
    config: CollectionConfig,
) -> pd.DatetimeIndex:
    """Return missing kline openings inside the observed interval-specific span."""
    if frame.empty:
        return pd.DatetimeIndex([], tz="UTC")
    observed = pd.DatetimeIndex(frame["open_time_utc"])
    expected = pd.date_range(
        observed.min(),
        observed.max(),
        freq=str(_interval_spec(config.interval)["frequency"]),
    )
    return expected.difference(observed)


def missing_hourly_intervals(frame: pd.DataFrame) -> pd.DatetimeIndex:
    """Return missing hourly openings for backward-compatible callers."""
    if frame.empty:
        return pd.DatetimeIndex([], tz="UTC")
    observed = pd.DatetimeIndex(frame["open_time_utc"])
    expected = pd.date_range(observed.min(), observed.max(), freq="1h")
    return expected.difference(observed)


def nonstandard_candle_durations(
    frame: pd.DataFrame,
    config: CollectionConfig | None = None,
) -> pd.DataFrame:
    """Return shortened candles whose close remains in the nominal window."""
    interval = "1h" if config is None else config.interval
    nominal_duration_ms = int(_interval_spec(interval)["duration_ms"])
    open_times = pd.to_numeric(frame["open_time_ms"], errors="raise")
    close_times = pd.to_numeric(frame["close_time_ms"], errors="raise")
    duration_ms = close_times - open_times + 1
    shortened = (duration_ms > 0) & (duration_ms < nominal_duration_ms)
    diagnostics = frame.loc[
        shortened,
        ["open_time_utc", "close_time_utc", "open_time_ms", "close_time_ms"],
    ].copy()
    diagnostics["duration_ms"] = duration_ms.loc[shortened].astype("int64")
    diagnostics["nominal_duration_ms"] = nominal_duration_ms
    diagnostics["shortfall_ms"] = nominal_duration_ms - diagnostics["duration_ms"]
    return diagnostics.reset_index(drop=True)


def validate_klines(
    frame: pd.DataFrame,
    config: CollectionConfig,
) -> pd.DataFrame:
    """Validate temporal boundaries, schema values, and OHLC consistency."""
    interval_spec = _interval_spec(config.interval)
    nominal_duration_ms = int(interval_spec["duration_ms"])
    interval_singular = str(interval_spec["singular"])
    interval_plural = str(interval_spec["plural"])
    missing = missing_kline_intervals(frame, config)
    open_times = pd.to_numeric(frame["open_time_ms"], errors="raise")
    close_times = pd.to_numeric(frame["close_time_ms"], errors="raise")
    number_of_trades = pd.to_numeric(frame["number_of_trades"], errors="raise")
    decimals = frame[DECIMAL_TEXT_COLUMNS].apply(pd.to_numeric, errors="raise")
    time_differences = open_times.diff().dropna()

    high = decimals["high"]
    low = decimals["low"]
    open_price = decimals["open"]
    close_price = decimals["close"]
    invalid_ohlc = (
        (high < low)
        | (high < open_price)
        | (high < close_price)
        | (low > open_price)
        | (low > close_price)
    )
    volume_columns = [
        "base_asset_volume",
        "quote_asset_volume",
        "taker_buy_base_asset_volume",
        "taker_buy_quote_asset_volume",
    ]
    negative_volume = (decimals[volume_columns] < 0).any(axis=1)
    non_positive_ohlc = (decimals[["open", "high", "low", "close"]] <= 0).any(axis=1)
    duration_ms = close_times - open_times + 1
    close_outside_nominal_window = (duration_ms <= 0) | (
        duration_ms > nominal_duration_ms
    )
    shortened_durations = (duration_ms > 0) & (duration_ms < nominal_duration_ms)

    checks = [
        ("Rows returned", len(frame), ">= 1", "OK" if len(frame) else "FAIL"),
        (
            "Duplicate open timestamps",
            int(open_times.duplicated().sum()),
            0,
            "OK" if not open_times.duplicated().any() else "FAIL",
        ),
        (
            "Non-increasing timestamp transitions",
            int((time_differences <= 0).sum()),
            0,
            "OK" if not (time_differences <= 0).any() else "FAIL",
        ),
        (
            f"Open timestamps off the UTC {interval_singular}",
            int((open_times % nominal_duration_ms != 0).sum()),
            0,
            "OK" if not (open_times % nominal_duration_ms != 0).any() else "FAIL",
        ),
        (
            "Close times outside the nominal candle window",
            int(close_outside_nominal_window.sum()),
            0,
            "OK" if not close_outside_nominal_window.any() else "FAIL",
        ),
        (
            "Shortened candle durations",
            int(shortened_durations.sum()),
            0,
            "OK" if not shortened_durations.any() else "REVIEW",
        ),
        (
            "Rows before requested start",
            int((open_times < config.start_time_ms).sum()),
            0,
            "OK" if not (open_times < config.start_time_ms).any() else "FAIL",
        ),
        (
            "Rows after requested end",
            int((close_times > config.end_time_ms).sum()),
            0,
            "OK" if not (close_times > config.end_time_ms).any() else "FAIL",
        ),
        (
            "Non-positive OHLC prices",
            int(non_positive_ohlc.sum()),
            0,
            "OK" if not non_positive_ohlc.any() else "FAIL",
        ),
        (
            "OHLC consistency violations",
            int(invalid_ohlc.sum()),
            0,
            "OK" if not invalid_ohlc.any() else "FAIL",
        ),
        (
            "Rows with negative volume",
            int(negative_volume.sum()),
            0,
            "OK" if not negative_volume.any() else "FAIL",
        ),
        (
            "Rows with negative trade count",
            int((number_of_trades < 0).sum()),
            0,
            "OK" if not (number_of_trades < 0).any() else "FAIL",
        ),
        (
            f"Missing {interval_plural} within observed span",
            len(missing),
            0,
            "OK" if not len(missing) else "REVIEW",
        ),
    ]
    return pd.DataFrame(checks, columns=["Check", "Actual", "Expected", "Status"])


def validate_hourly_klines(
    frame: pd.DataFrame,
    config: CollectionConfig,
) -> pd.DataFrame:
    """Backward-compatible alias for :func:`validate_klines`."""
    return validate_klines(frame, config)


def _assert_collection_complete(
    symbol: str,
    frame: pd.DataFrame,
    validation: pd.DataFrame,
    config: CollectionConfig,
) -> None:
    fatal_checks = validation.loc[validation["Status"] == "FAIL"]
    if not fatal_checks.empty:
        failed_names = ", ".join(fatal_checks["Check"].astype(str))
        raise ValueError(f"Fatal validation checks failed for {symbol}: {failed_names}")
    last_close_ms = int(pd.to_numeric(frame["close_time_ms"]).max())
    if last_close_ms != config.end_time_ms:
        last_close = pd.to_datetime(last_close_ms, unit="ms", utc=True).isoformat()
        raise ValueError(
            f"{symbol} does not reach the requested end; last close is {last_close}."
        )
