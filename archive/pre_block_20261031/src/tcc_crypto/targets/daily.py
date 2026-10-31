"""Targets: daily."""

from __future__ import annotations

import pandas as pd

DAY = pd.Timedelta(1, unit="D")


def build_next_day_d0_targets(
    daily_values: pd.DataFrame,
    feature_index: pd.DatetimeIndex,
    *,
    thresholds: tuple[float, ...] = (0.02, 0.03, 0.04),
) -> pd.DataFrame:
    """Align each feature date with the following day's same-day D0 outcome."""
    required = {"open", "high"}
    if not required.issubset(daily_values.columns):
        raise ValueError("daily_values must contain open and high columns.")
    if not isinstance(daily_values.index, pd.DatetimeIndex):
        raise TypeError("daily_values must use a DatetimeIndex.")
    if daily_values.index.tz is None or str(daily_values.index.tz) != "UTC":
        raise ValueError("daily_values timestamps must use UTC.")
    if not isinstance(feature_index, pd.DatetimeIndex):
        raise TypeError("feature_index must be a DatetimeIndex.")
    if feature_index.tz is None or str(feature_index.tz) != "UTC":
        raise ValueError("feature_index timestamps must use UTC.")
    if tuple(float(value) for value in thresholds) != (0.02, 0.03, 0.04):
        raise ValueError("Approved target thresholds are 0.02, 0.03, and 0.04.")

    target_dates = feature_index + DAY
    next_day_open = daily_values["open"].reindex(target_dates)
    next_day_high = daily_values["high"].reindex(target_dates)
    next_day_d0 = next_day_high.div(next_day_open).sub(1.0)
    next_day_d0.index = feature_index

    result = pd.DataFrame(index=feature_index)
    result.index.name = "feature_date_utc"
    result["target_date_utc"] = target_dates
    result["next_day_open"] = next_day_open.to_numpy()
    result["next_day_high"] = next_day_high.to_numpy()
    result["next_day_d0"] = next_day_d0

    if "is_imputed" in daily_values.columns:
        target_imputed = daily_values["is_imputed"].reindex(target_dates)
        target_imputed.index = feature_index
        result["target_is_imputed"] = target_imputed.astype("boolean")
    else:
        result["target_is_imputed"] = pd.Series(
            False, index=feature_index, dtype="boolean"
        )

    for threshold in thresholds:
        label = next_day_d0.ge(threshold).astype("Int8")
        label[next_day_d0.isna()] = pd.NA
        result[f"target_{int(round(threshold * 100))}pct"] = label
    return result
