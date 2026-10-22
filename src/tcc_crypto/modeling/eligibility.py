"""Modeling: eligibility."""

from __future__ import annotations

import json
from typing import Sequence

import pandas as pd

from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.modeling.config import DailySvmGridSearchConfig
from tcc_crypto.modeling.splits import temporal_splits


def assess_symbol_eligibility(
    dataset: pd.DataFrame,
    *,
    symbol: str,
    config: DailySvmGridSearchConfig,
    feature_columns: Sequence[str] = ACTIVE_FEATURES,
) -> pd.DataFrame:
    """Return one auditable eligibility row per symbol-target-window search."""
    rows: list[dict[str, object]] = []
    excluded = symbol in config.excluded_symbols
    for target in config.targets:
        for window_size in config.training_window_sizes:
            required = [*feature_columns, target]
            missing_columns = sorted(set(required).difference(dataset.columns))
            complete = (
                dataset.iloc[0:0]
                if missing_columns
                else dataset.loc[:, required].dropna()
            )
            reasons: list[str] = []
            fold_counts: list[dict[str, int]] = []
            if excluded:
                reasons.append("explicit_symbol_exclusion")
            if missing_columns:
                reasons.append("missing_required_columns")
            if len(complete) < config.minimum_complete_rows:
                reasons.append("insufficient_complete_labeled_rows")
            if not missing_columns and len(complete) >= config.minimum_complete_rows:
                for fold_index, (train, _) in enumerate(
                    temporal_splits(len(complete), config, window_size)
                ):
                    labels = complete[target].iloc[train].astype("int64")
                    negative = int((labels == 0).sum())
                    positive = int((labels == 1).sum())
                    fold_counts.append(
                        {
                            "fold": fold_index,
                            "negative": negative,
                            "positive": positive,
                        }
                    )
                    if labels.nunique() < 2:
                        reasons.append(f"single_class_training_fold_{fold_index}")
            reasons = list(dict.fromkeys(reasons))
            rows.append(
                {
                    "symbol": symbol,
                    "target": target,
                    "window_size": window_size,
                    "status": "eligible" if not reasons else "ineligible",
                    "reason": "|".join(reasons),
                    "complete_labeled_rows": len(complete),
                    "negative_count": int((complete[target] == 0).sum())
                    if target in complete
                    else 0,
                    "positive_count": int((complete[target] == 1).sum())
                    if target in complete
                    else 0,
                    "first_feature_time_utc": complete.index.min()
                    if not complete.empty
                    else pd.NaT,
                    "last_feature_time_utc": complete.index.max()
                    if not complete.empty
                    else pd.NaT,
                    "first_observed_utc": dataset.attrs.get(
                        "first_observed_utc", pd.NaT
                    ),
                    "last_observed_utc": dataset.attrs.get("last_observed_utc", pd.NaT),
                    "observed_feature_rows": int(
                        len(dataset)
                        - dataset.get(
                            "feature_is_imputed",
                            pd.Series(False, index=dataset.index),
                        )
                        .fillna(False)
                        .sum()
                    ),
                    "feature_imputed_rows": int(
                        dataset.get(
                            "feature_is_imputed",
                            pd.Series(False, index=dataset.index),
                        )
                        .fillna(False)
                        .sum()
                    ),
                    "target_imputed_rows": int(
                        dataset.get(
                            "target_is_imputed",
                            pd.Series(False, index=dataset.index),
                        )
                        .fillna(False)
                        .sum()
                    ),
                    "training_fold_class_counts": json.dumps(
                        fold_counts, separators=(",", ":")
                    ),
                    "final_test_eligibility_status": "not_evaluated_development_only",
                    "first_permitted_final_test_feature_utc": pd.NaT,
                    "last_permitted_final_test_feature_utc": pd.NaT,
                }
            )
    return pd.DataFrame(rows)
