"""Build approved price and technical features from daily Binance klines.

All features at timestamp ``t`` use observations at or before ``t``. The
Parabolic SAR feature provisionally reproduces the zero-valued parameters in
the Silva (2026) reference; those parameters still require later verification.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pandas as pd
import talib

DAY = timedelta(days=1)
PRICE_FIELDS = ("open", "high", "low", "close")
ACTIVE_FEATURES = (
    "r1",
    "r2",
    "r3",
    "r4",
    "r5",
    "r6",
    "r7",
    "r8",
    "r9",
    "r10",
    "r11",
    "r12",
    "r13",
    "r14",
    "r15",
    "momentum_10",
    "rsi_14",
    "parabolic_sar",
    "atr_14",
    "true_range",
    "chaikin_ad",
    "obv",
)


@dataclass(frozen=True)
class DailyFeatureSelectionConfig:
    """Validated temporal feature-selection settings."""

    variance_threshold: float
    correlation_threshold: float
    correlation_method: str
    training_window_sizes: tuple[int, ...]
    window_type: str
    refit_frequency: str
    prediction_step_observations: int
    fit_scope: str


@dataclass(frozen=True)
class DailyFeatureConfig:
    """Validated settings for the approved daily feature set."""

    feature_set_id: str
    collection_config: Path
    interval: str
    time_zone: str
    missing_data_policy: str
    imputation_marker: str
    price_fields: tuple[str, ...]
    volume_field: str
    momentum_period: int
    rsi_period: int
    atr_period: int
    parabolic_sar_acceleration: float
    parabolic_sar_maximum: float
    parabolic_sar_verification_required: bool
    active_features: tuple[str, ...]
    features_requiring_verification: tuple[str, ...]
    feature_output_directory: Path
    analysis_output_directory: Path
    feature_selection: DailyFeatureSelectionConfig


def load_daily_feature_config(path: Path) -> DailyFeatureConfig:
    """Load and validate the daily feature configuration."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)

    if payload["interval"] != "1d":
        raise ValueError("Daily features require the 1d interval.")
    if payload["time_zone"] != "UTC":
        raise ValueError("Daily features require UTC timestamps.")
    missing_data = payload["missing_data"]
    if missing_data["policy"] != "forward_fill_internal":
        raise ValueError("Daily features require forward_fill_internal.")
    if missing_data["imputation_marker"] != "is_imputed":
        raise ValueError("Daily features require the is_imputed audit marker.")
    if missing_data["raw_data_mutation"] is not False:
        raise ValueError("Raw daily data must remain immutable.")
    if missing_data["leading_fill"] is not False:
        raise ValueError("Leading daily gaps must not be filled.")
    if missing_data["trailing_fill"] is not False:
        raise ValueError("Trailing daily gaps must not be filled.")
    if tuple(payload["price_fields"]) != PRICE_FIELDS:
        raise ValueError(f"price_fields must be exactly {PRICE_FIELDS}.")
    if payload["volume_field"] != "quote_asset_volume":
        raise ValueError("Daily features require quote_asset_volume.")
    if int(payload["momentum_period"]) != 10:
        raise ValueError("The approved momentum period is 10 observations.")
    if int(payload["rsi_period"]) != 14:
        raise ValueError("The approved RSI period is 14 observations.")
    if int(payload["atr_period"]) != 14:
        raise ValueError("The approved ATR period is 14 observations.")
    parabolic_sar = payload["parabolic_sar"]
    if parabolic_sar["enabled"] is not True:
        raise ValueError("The provisionally approved Parabolic SAR must be enabled.")
    if float(parabolic_sar["acceleration"]) != 0.0:
        raise ValueError("Parabolic SAR acceleration must provisionally remain zero.")
    if float(parabolic_sar["maximum"]) != 0.0:
        raise ValueError("Parabolic SAR maximum must provisionally remain zero.")
    if parabolic_sar["verification_required"] is not True:
        raise ValueError("Parabolic SAR must remain marked for later verification.")
    if tuple(payload["active_features"]) != ACTIVE_FEATURES:
        raise ValueError("active_features does not match the approved feature order.")
    if tuple(payload["features_requiring_verification"]) != ("parabolic_sar",):
        raise ValueError("parabolic_sar must remain marked for verification.")
    selection = payload["feature_selection"]
    if selection["enabled"] is not True:
        raise ValueError("The approved daily feature selection must be enabled.")
    if float(selection["variance_threshold"]) != 0.01:
        raise ValueError("The approved variance threshold is 0.01.")
    if float(selection["correlation_threshold"]) != 0.8:
        raise ValueError("The approved correlation threshold is 0.8.")
    if selection["correlation_method"] != "pearson":
        raise ValueError("The approved correlation method is Pearson.")
    if tuple(selection["training_window_sizes"]) != (60, 75, 90):
        raise ValueError("The approved training windows are 60, 75, and 90 days.")
    if selection["window_type"] != "rolling":
        raise ValueError("The approved training windows are rolling.")
    if selection["refit_frequency"] != "every_prediction":
        raise ValueError("Feature selection must be refitted for every prediction.")
    if int(selection["prediction_step_observations"]) != 1:
        raise ValueError("The approved prediction step is one observation.")
    if selection["fit_scope"] != "training_only":
        raise ValueError("Feature selection must be fitted on training data only.")

    return DailyFeatureConfig(
        feature_set_id=str(payload["feature_set_id"]),
        collection_config=Path(payload["collection_config"]),
        interval="1d",
        time_zone="UTC",
        missing_data_policy="forward_fill_internal",
        imputation_marker="is_imputed",
        price_fields=PRICE_FIELDS,
        volume_field="quote_asset_volume",
        momentum_period=10,
        rsi_period=14,
        atr_period=14,
        parabolic_sar_acceleration=0.0,
        parabolic_sar_maximum=0.0,
        parabolic_sar_verification_required=True,
        active_features=ACTIVE_FEATURES,
        features_requiring_verification=("parabolic_sar",),
        feature_output_directory=Path(payload["feature_output_directory"]),
        analysis_output_directory=Path(payload["analysis_output_directory"]),
        feature_selection=DailyFeatureSelectionConfig(
            variance_threshold=0.01,
            correlation_threshold=0.8,
            correlation_method="pearson",
            training_window_sizes=(60, 75, 90),
            window_type="rolling",
            refit_frequency="every_prediction",
            prediction_step_observations=1,
            fit_scope="training_only",
        ),
    )


def _validate_daily_values(
    values: pd.DataFrame, *, require_complete_calendar: bool = True
) -> None:
    required = {*PRICE_FIELDS, "quote_asset_volume"}
    missing = required.difference(values.columns)
    if missing:
        raise ValueError(f"Daily feature input is missing columns: {sorted(missing)}.")
    if values.empty:
        raise ValueError("Daily feature input contains no observations.")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError("Daily feature input must use a DatetimeIndex.")
    if values.index.tz is None:
        raise ValueError("Daily feature timestamps must include timezone information.")
    if str(values.index.tz) != "UTC":
        raise ValueError("Daily feature timestamps must use UTC.")
    if values.index.has_duplicates:
        raise ValueError("Daily feature input contains duplicate timestamps.")
    if not values.index.is_monotonic_increasing:
        raise ValueError("Daily feature input must be chronologically ordered.")
    if (values.index != values.index.normalize()).any():
        raise ValueError("Daily feature timestamps must be aligned to UTC midnight.")
    if (
        require_complete_calendar
        and len(values.index) > 1
        and not (values.index.to_series().diff().iloc[1:] == DAY).all()
    ):
        raise ValueError(
            "Daily feature input contains missing UTC days; align internal gaps "
            "before feature construction."
        )

    numeric = values.loc[:, [*PRICE_FIELDS, "quote_asset_volume"]]
    if numeric.isna().any().any():
        raise ValueError("Daily feature input contains missing values.")
    if not numeric.map(math.isfinite).all().all():
        raise ValueError("Daily feature input contains non-finite values.")
    if not (numeric.loc[:, PRICE_FIELDS] > 0).all().all():
        raise ValueError("Daily feature prices must be strictly positive.")
    if (numeric["quote_asset_volume"] < 0).any():
        raise ValueError("Daily quote-asset volume must be non-negative.")

    inconsistent = (
        (numeric["high"] < numeric[["open", "close"]].max(axis=1))
        | (numeric["low"] > numeric[["open", "close"]].min(axis=1))
        | (numeric["high"] < numeric["low"])
    )
    if inconsistent.any():
        raise ValueError("Daily feature input contains OHLC consistency violations.")


def fill_internal_daily_gaps(values: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill missing UTC days bounded by observed daily candles.

    The input frame is not mutated. The returned ``is_imputed`` column records
    which rows were synthesized. Because the calendar spans only the first
    through last observed timestamps, this function never backfills pre-listing
    dates or extends an asset beyond its final observation.
    """
    _validate_daily_values(values, require_complete_calendar=False)
    complete_index = pd.date_range(
        start=values.index[0],
        end=values.index[-1],
        freq="D",
        tz="UTC",
        name=values.index.name,
    )
    imputed = ~complete_index.isin(values.index)
    aligned = values.reindex(complete_index).copy()
    aligned.loc[:, [*PRICE_FIELDS, "quote_asset_volume"]] = aligned.loc[
        :, [*PRICE_FIELDS, "quote_asset_volume"]
    ].ffill()
    aligned["is_imputed"] = imputed
    _validate_daily_values(aligned)
    return aligned


def load_daily_feature_input(
    path: Path, *, fill_internal_gaps: bool = False
) -> pd.DataFrame:
    """Load OHLC and USDT quote volume from one immutable raw CSV.

    When ``fill_internal_gaps`` is true, the returned frame follows the
    approved forward-fill policy and includes an ``is_imputed`` audit column.
    """
    columns = ["open_time_ms", *PRICE_FIELDS, "quote_asset_volume"]
    frame = pd.read_csv(path, usecols=columns)
    timestamps = pd.to_datetime(frame.pop("open_time_ms"), unit="ms", utc=True)
    values = frame.apply(pd.to_numeric, errors="raise").astype("float64")
    values.index = pd.DatetimeIndex(timestamps, name="open_time_utc")
    if fill_internal_gaps:
        return fill_internal_daily_gaps(values)
    _validate_daily_values(values)
    return values


def _natural_log_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator).map(
        lambda value: math.log(value) if pd.notna(value) else float("nan")
    )


def _wilder_rsi(close: pd.Series, period: int) -> pd.Series:
    result = pd.Series(float("nan"), index=close.index, dtype="float64")
    if len(close) <= period:
        return result

    differences = close.diff()
    gains = differences.clip(lower=0.0)
    losses = -differences.clip(upper=0.0)
    average_gain = float(gains.iloc[1 : period + 1].mean())
    average_loss = float(losses.iloc[1 : period + 1].mean())

    def rsi_value(gain: float, loss: float) -> float:
        if loss == 0.0:
            return 100.0 if gain > 0.0 else 0.0
        return 100.0 - (100.0 / (1.0 + gain / loss))

    result.iloc[period] = rsi_value(average_gain, average_loss)
    for position in range(period + 1, len(close)):
        average_gain = (
            average_gain * (period - 1) + float(gains.iloc[position])
        ) / period
        average_loss = (
            average_loss * (period - 1) + float(losses.iloc[position])
        ) / period
        result.iloc[position] = rsi_value(average_gain, average_loss)
    return result


def _true_range(values: pd.DataFrame) -> pd.Series:
    previous_close = values["close"].shift(1)
    components = pd.concat(
        [
            values["high"] - values["low"],
            (values["high"] - previous_close).abs(),
            (values["low"] - previous_close).abs(),
        ],
        axis=1,
    )
    result = components.max(axis=1)
    result.iloc[0] = float("nan")
    return result.astype("float64")


def _wilder_atr(true_range: pd.Series, period: int) -> pd.Series:
    result = pd.Series(float("nan"), index=true_range.index, dtype="float64")
    if len(true_range) <= period:
        return result

    average = float(true_range.iloc[1 : period + 1].mean())
    result.iloc[period] = average
    for position in range(period + 1, len(true_range)):
        average = (
            average * (period - 1) + float(true_range.iloc[position])
        ) / period
        result.iloc[position] = average
    return result


def _chaikin_ad(values: pd.DataFrame) -> pd.Series:
    price_range = values["high"] - values["low"]
    multiplier = pd.Series(0.0, index=values.index, dtype="float64")
    nonzero_range = price_range != 0.0
    multiplier.loc[nonzero_range] = (
        (
            (values.loc[nonzero_range, "close"] - values.loc[nonzero_range, "low"])
            - (values.loc[nonzero_range, "high"] - values.loc[nonzero_range, "close"])
        )
        / price_range.loc[nonzero_range]
    )
    return multiplier.mul(values["quote_asset_volume"]).cumsum()


def _on_balance_volume(values: pd.DataFrame) -> pd.Series:
    direction = values["close"].diff().map(
        lambda change: 1.0 if change > 0 else (-1.0 if change < 0 else 0.0)
    )
    direction.iloc[0] = 1.0
    return direction.mul(values["quote_asset_volume"]).cumsum()


def calculate_daily_features(values: pd.DataFrame) -> pd.DataFrame:
    """Return the 22 active daily features without mutating ``values``.

    Warm-up observations remain missing. Callers must preserve them until a
    later, explicitly approved dataset-alignment step decides which rows are
    eligible for modeling.
    """
    _validate_daily_values(values)
    source = values.loc[:, [*PRICE_FIELDS, "quote_asset_volume"]].astype("float64")
    features = pd.DataFrame(index=source.index)

    features["r1"] = _natural_log_ratio(source["close"], source["close"].shift(1))
    features["r2"] = _natural_log_ratio(
        source["close"].shift(1), source["close"].shift(2)
    )
    features["r3"] = _natural_log_ratio(
        source["close"].shift(2), source["close"].shift(3)
    )
    features["r4"] = _natural_log_ratio(
        source["close"].shift(3), source["close"].shift(4)
    )
    features["r5"] = _natural_log_ratio(source["high"], source["open"])
    features["r6"] = _natural_log_ratio(source["high"], source["open"].shift(1))
    features["r7"] = _natural_log_ratio(source["high"], source["open"].shift(2))
    features["r8"] = _natural_log_ratio(source["high"], source["open"].shift(3))
    features["r9"] = _natural_log_ratio(
        source["high"].shift(1), source["open"].shift(1)
    )
    features["r10"] = _natural_log_ratio(
        source["high"].shift(2), source["open"].shift(2)
    )
    features["r11"] = _natural_log_ratio(
        source["high"].shift(3), source["open"].shift(3)
    )
    features["r12"] = _natural_log_ratio(source["low"], source["open"])
    features["r13"] = _natural_log_ratio(
        source["low"].shift(1), source["open"].shift(1)
    )
    features["r14"] = _natural_log_ratio(
        source["low"].shift(2), source["open"].shift(2)
    )
    features["r15"] = _natural_log_ratio(
        source["low"].shift(3), source["open"].shift(3)
    )

    features["momentum_10"] = source["close"] - source["close"].shift(10)
    features["rsi_14"] = _wilder_rsi(source["close"], period=14)
    features["parabolic_sar"] = talib.SAR(
        source["high"].to_numpy(),
        source["low"].to_numpy(),
        acceleration=0.0,
        maximum=0.0,
    )
    features["true_range"] = _true_range(source)
    features["atr_14"] = _wilder_atr(features["true_range"], period=14)
    features["chaikin_ad"] = _chaikin_ad(source)
    features["obv"] = _on_balance_volume(source)

    return features.loc[:, ACTIVE_FEATURES]
