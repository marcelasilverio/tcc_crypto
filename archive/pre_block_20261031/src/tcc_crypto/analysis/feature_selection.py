"""Full-history descriptive feature selection, separate from modeling datasets."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.features.config import DailyFeatureConfig
from tcc_crypto.features.daily import calculate_daily_features
from tcc_crypto.features.warmup import remove_leading_feature_warmup
from tcc_crypto.modeling.selection import summarize_rolling_feature_selection


def calculate_feature_tables(
    values: dict[str, pd.DataFrame], diagnostics: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    tables = {}
    rows = diagnostics.to_dict("records")
    for symbol, frame in values.items():
        try:
            calculated = calculate_daily_features(frame)
            complete = remove_leading_feature_warmup(calculated)
            tables["features__" + symbol] = complete
            rows.append(
                {
                    "symbol": symbol,
                    "status": "READY",
                    "raw_rows": len(frame),
                    "warmup_rows_removed": len(calculated) - len(complete),
                    "complete_feature_rows": len(complete),
                    "first_feature_time_utc": complete.index.min(),
                    "last_feature_time_utc": complete.index.max(),
                    "missing_utc_days": 0,
                    "diagnostic": "",
                }
            )
        except (ValueError, TypeError) as error:
            rows.append(
                {
                    "symbol": symbol,
                    "status": "BLOCKED",
                    "diagnostic": f"{type(error).__name__}: {error}",
                }
            )
    manifest = pd.DataFrame(rows)
    for column in ("first_feature_time_utc", "last_feature_time_utc"):
        if column in manifest:
            manifest[column] = pd.to_datetime(manifest[column], utc=True)
    tables["manifest"] = manifest
    return tables


def calculate_selection(
    tables: dict[str, pd.DataFrame], config: DailyFeatureConfig
) -> dict[str, pd.DataFrame]:
    histories, frequencies, windows = [], [], []
    for name, features in tables.items():
        if not name.startswith("features__"):
            continue
        symbol = name.removeprefix("features__")
        summary = summarize_rolling_feature_selection(
            features, config.feature_selection
        )
        histories.append(summary.history.assign(symbol=symbol))
        frequencies.append(summary.feature_frequency.assign(symbol=symbol))
        windows.append(summary.window_summary.assign(symbol=symbol))
    result = dict(tables)
    for name, frames in [
        ("selection_history", histories),
        ("selection_frequency", frequencies),
        ("window_summary", windows),
    ]:
        result[name] = (
            pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        )
    return result
