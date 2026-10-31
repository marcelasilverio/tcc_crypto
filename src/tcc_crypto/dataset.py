"""Feature formulas and next-day targets; no persistence or model fitting."""

import math
from dataclasses import dataclass

import pandas as pd
import talib

from tcc_crypto.preparation import validate_calendar


def _natural_log_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator).map(
        lambda value: math.log(value) if pd.notna(value) else float("nan")
    )


def calculate_price_features(source: pd.DataFrame) -> pd.DataFrame:
    """Calculate r1-r15 exactly as approved; all lags refer to UTC days."""
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

    return features


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
        average = (average * (period - 1) + float(true_range.iloc[position])) / period
        result.iloc[position] = average
    return result


def _chaikin_ad(values: pd.DataFrame) -> pd.Series:
    price_range = values["high"] - values["low"]
    multiplier = pd.Series(0.0, index=values.index, dtype="float64")
    nonzero_range = price_range != 0.0
    multiplier.loc[nonzero_range] = (
        (values.loc[nonzero_range, "close"] - values.loc[nonzero_range, "low"])
        - (values.loc[nonzero_range, "high"] - values.loc[nonzero_range, "close"])
    ) / price_range.loc[nonzero_range]
    return multiplier.mul(values["quote_asset_volume"]).cumsum()


def _on_balance_volume(values: pd.DataFrame) -> pd.Series:
    direction = (
        values["close"]
        .diff()
        .map(lambda change: 1.0 if change > 0 else (-1.0 if change < 0 else 0.0))
    )
    direction.iloc[0] = 1.0
    return direction.mul(values["quote_asset_volume"]).cumsum()


def momentum(close: pd.Series, period: int = 10) -> pd.Series:
    """Current close minus the close `period` daily observations earlier."""
    return close - close.shift(period)


def parabolic_sar(
    values: pd.DataFrame, acceleration: float = 0.0, maximum: float = 0.0
) -> pd.Series:
    """Provisional Silva SAR: acceleration=maximum=0; verification pending."""
    return pd.Series(
        talib.SAR(
            values["high"].to_numpy(),
            values["low"].to_numpy(),
            acceleration=acceleration,
            maximum=maximum,
        ),
        index=values.index,
    )


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


@dataclass
class DatasetTables:
    features: pd.DataFrame
    targets: pd.DataFrame
    dataset: pd.DataFrame


def target_name(threshold: float) -> str:
    return f"target_{threshold * 100:g}pct"


def calculate_features(values: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    """Preserve existing Wilder formulas and volume convention."""
    validate_calendar(values.index)
    source = values.copy()
    source["quote_asset_volume"] = source[parameters["volume_field"]].astype(float)
    for column in ("open", "high", "low", "close"):
        source[column] = source[column].astype(float)
    features = calculate_price_features(source)
    features["momentum_10"] = momentum(source.close, parameters["momentum_period"])
    features["rsi_14"] = _wilder_rsi(source.close, parameters["rsi_period"])
    sar = parameters["parabolic_sar"]
    features["parabolic_sar"] = parabolic_sar(
        source, sar["acceleration"], sar["maximum"]
    )
    features["true_range"] = _true_range(source)
    features["atr_14"] = _wilder_atr(features.true_range, parameters["atr_period"])
    features["chaikin_ad"] = _chaikin_ad(source)
    features["obv"] = _on_balance_volume(source)
    return features.loc[:, parameters["active_features"]]


def build_dataset(treated: pd.DataFrame, config: dict) -> DatasetTables:
    if treated.empty:
        raise ValueError("No valid treated candles; inspect preparation diagnostics.")
    values = treated.set_index("date_utc")
    validate_calendar(values.index)
    features = calculate_features(values, config["features"])
    features.index.name = "feature_time_utc"
    targets = pd.DataFrame(index=features.index)
    targets["target_time_utc"] = targets.index + pd.Timedelta(days=1)
    returns = (values.high / values.open - 1).shift(-1)
    targets["next_day_open"] = values.open.shift(-1)
    targets["next_day_high"] = values.high.shift(-1)
    targets["next_day_d0"] = returns
    for q in config["targets"]:
        targets[target_name(q)] = returns.ge(q).astype("Int64").mask(returns.isna())
    targets["target_is_imputed"] = values.is_imputed.shift(-1).astype("boolean")
    targets["target_available_at_utc"] = pd.Series(
        pd.to_datetime(values.close_time_ms, unit="ms", utc=True).array,
        index=values.index,
    ).shift(-1)
    combined = features.join(targets)
    combined["feature_is_imputed"] = values.is_imputed.astype("boolean")
    combined["feature_available_at_utc"] = pd.to_datetime(
        values.close_time_ms, unit="ms", utc=True
    )
    combined = combined.loc[config["study"]["start"] : config["study"]["end"]]
    columns = [
        *config["features"]["active_features"],
        *[target_name(q) for q in config["targets"]],
    ]
    complete = combined[columns].notna().all(axis=1)
    if complete.any():
        usable = combined.loc[
            complete[complete].index[0] : complete[complete].index[-1]
        ]
        if usable[columns].isna().any().any():
            raise ValueError(
                "Internal missing features/targets; do not compress the calendar."
            )
        validate_calendar(usable.index)
    combined["is_usable"] = complete
    combined.attrs = {
        "required_history_days": max(
            4,
            config["features"]["momentum_period"],
            config["features"]["rsi_period"],
            config["features"]["atr_period"],
        ),
        "usable_start_utc": str(combined.index[complete][0])
        if complete.any()
        else None,
        "usable_end_utc": str(combined.index[complete][-1]) if complete.any() else None,
        "warmup_rows": int(
            (features.index < pd.Timestamp(config["study"]["start"], tz="UTC")).sum()
        ),
        "unusable_rows": int((~complete).sum()),
    }
    return DatasetTables(
        features.reset_index(), targets.reset_index(), combined.reset_index()
    )
