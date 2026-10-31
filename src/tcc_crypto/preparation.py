"""Validate raw daily candles, audit availability and fill bounded internal gaps."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

KLINE_COLUMNS = [
    "open_time_ms",
    "open",
    "high",
    "low",
    "close",
    "base_asset_volume",
    "close_time_ms",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
]
PRICE_FIELDS = ["open", "high", "low", "close"]
VOLUME_FIELDS = [
    "base_asset_volume",
    "quote_asset_volume",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
]
DAY_MS = 86_400_000


@dataclass
class PreparedData:
    treated: pd.DataFrame
    availability: pd.DataFrame
    treatment: pd.DataFrame
    diagnostics: pd.DataFrame


def validate_calendar(index: pd.DatetimeIndex) -> None:
    if (
        str(index.tz) != "UTC"
        or index.has_duplicates
        or not index.is_monotonic_increasing
    ):
        raise ValueError("Calendar must be unique, ordered and UTC.")
    if (index != index.normalize()).any() or (
        len(index) > 1
        and not (index.to_series().diff().iloc[1:] == pd.Timedelta(days=1)).all()
    ):
        raise ValueError("Calendar must have consecutive UTC days.")


def prepare_symbol(raw: pd.DataFrame, symbol: str, study: dict) -> PreparedData:
    """Reject ambiguous dates; invalid identifiable candles become missing days."""
    frame = raw.reindex(columns=KLINE_COLUMNS).copy()
    if "open_time_ms" not in raw:
        raise ValueError(f"{symbol}: missing timestamp column; cannot assign dates.")
    times = pd.to_numeric(frame["open_time_ms"], errors="coerce")
    if (
        times.isna().any()
        or not np.isfinite(times).all()
        or (times % DAY_MS != 0).any()
    ):
        raise ValueError(f"{symbol}: invalid or off-calendar timestamps.")
    index = pd.DatetimeIndex(
        pd.to_datetime(times, unit="ms", utc=True), name="date_utc"
    )
    if index.has_duplicates:
        raise ValueError(f"{symbol}: duplicate dates; source is ambiguous.")
    if not index.is_monotonic_increasing:
        raise ValueError(f"{symbol}: raw dates are not chronological.")
    frame.index = index
    numeric = frame.apply(pd.to_numeric, errors="coerce")
    reasons = pd.Series("", index=index, dtype="string")

    def mark(mask, reason):
        reasons.loc[mask] += reason + "|"

    mark(numeric.isna().any(axis=1), "incomplete_or_nonnumeric")
    mark(~np.isfinite(numeric).all(axis=1), "nonfinite")
    mark((numeric[PRICE_FIELDS] <= 0).any(axis=1), "nonpositive_price")
    mark((numeric[VOLUME_FIELDS] < 0).any(axis=1), "negative_volume")
    mark(
        (numeric["number_of_trades"] < 0) | (numeric["number_of_trades"] % 1 != 0),
        "invalid_trade_count",
    )
    mark(
        (numeric.high < numeric[["open", "close", "low"]].max(axis=1))
        | (numeric.low > numeric[["open", "close", "high"]].min(axis=1)),
        "inconsistent_ohlc",
    )
    duration = numeric.close_time_ms - numeric.open_time_ms + 1
    mark(
        (duration <= 0) | (duration > DAY_MS) | (numeric.close_time_ms % 1 != 0),
        "invalid_duration",
    )
    valid = reasons.eq("")
    calendar = pd.date_range(study["start"], study["end"], tz="UTC", name="date_utc")
    availability = pd.DataFrame(
        {
            "date_utc": calendar,
            "symbol": symbol,
            "available": calendar.isin(index[valid]).astype(int),
        }
    )
    diagnostics = pd.DataFrame(
        {
            "date_utc": index,
            "symbol": symbol,
            "valid": valid.to_numpy(),
            "reason": reasons.str.rstrip("|").to_numpy(),
            "shortened_candle": ((duration > 0) & (duration < DAY_MS)).to_numpy(),
        }
    )
    good = numeric.loc[valid].copy()
    good = good.loc[study["warmup_start"] : study["end"]]
    if good.empty:
        return PreparedData(
            pd.DataFrame(
                columns=[*KLINE_COLUMNS, "is_imputed", "source_date_utc", "date_utc"]
            ),
            availability,
            diagnostics.assign(status="no_valid_candles"),
            diagnostics,
        )
    span = pd.date_range(good.index[0], good.index[-1], tz="UTC", name="date_utc")
    treated = good.reindex(span).ffill()
    treated["is_imputed"] = ~span.isin(good.index)
    treated["source_date_utc"] = (
        pd.Series(good.index, index=good.index).reindex(span).ffill()
    )
    # Calendar timestamps describe the synthetic day; source_date_utc retains provenance.
    imputed = treated.is_imputed
    treated.loc[imputed, "open_time_ms"] = span[imputed].asi8 // 1_000_000
    treated.loc[imputed, "close_time_ms"] = (
        treated.loc[imputed, "open_time_ms"] + DAY_MS - 1
    )
    validate_calendar(treated.index)
    treatment = pd.DataFrame(
        {
            "date_utc": span,
            "symbol": symbol,
            "source_date_utc": treated.source_date_utc.to_numpy(),
            "is_imputed": imputed.to_numpy(),
            "reason": reasons.reindex(span)
            .fillna("missing_candle")
            .str.rstrip("|")
            .to_numpy(),
        }
    )
    treatment["status"] = np.where(treatment.is_imputed, "filled", "observed")
    # Include invalid edge observations without inventing leading/trailing data.
    edge = diagnostics.loc[~diagnostics.valid & ~diagnostics.date_utc.isin(span)].copy()
    if not edge.empty:
        edge["status"] = "outside_valid_span"
        edge["is_imputed"] = False
        edge["source_date_utc"] = pd.NaT
        treatment = pd.concat([treatment, edge[treatment.columns]], ignore_index=True)
    return PreparedData(
        treated.reset_index(),
        availability,
        treatment.sort_values("date_utc").reset_index(drop=True),
        diagnostics,
    )
