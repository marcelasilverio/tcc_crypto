"""Reconstruct only selected development fits to record missing training scores."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.svm import SVC

from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.modeling.config import (
    DailyFeatureSelectionConfig,
    DailySvmGridSearchConfig,
)
from tcc_crypto.modeling.metrics import calculate_classification_metrics
from tcc_crypto.modeling.preprocessing import prepare_window
from tcc_crypto.modeling.splits import temporal_splits


def reconstruct_training_metrics(
    dataset: pd.DataFrame,
    selected: pd.DataFrame,
    folds: pd.DataFrame,
    *,
    config: DailySvmGridSearchConfig,
    selection_config: DailyFeatureSelectionConfig,
) -> pd.DataFrame:
    """Score fitted rows, reproducing saved validation scores before accepting them.

    Each selected candidate is refit on its original three development folds.
    No final-test observations or metrics participate. Training scores describe
    resubstitution on overlapping windows, not independent predictions.
    """
    if dataset.index.max() > config.development_end_utc:
        raise ValueError("Training review requires development data only.")
    rows = []
    for chosen in selected.itertuples(index=False):
        complete = dataset.loc[:, [*ACTIVE_FEATURES, chosen.target]].dropna()
        splits = temporal_splits(len(complete), config, chosen.window_size)
        for fold, (train, validation) in enumerate(splits):
            saved = folds.loc[
                folds.target.eq(chosen.target)
                & folds.window_size.eq(chosen.window_size)
                & folds.candidate_order.eq(chosen.candidate_order)
                & folds.fold.eq(fold)
            ]
            if len(saved) != 1 or saved.iloc[0].status != "ok":
                raise ValueError("Missing unique successful selected-candidate fold.")
            reference = saved.iloc[0]
            training, future = complete.iloc[train], complete.iloc[validation]
            boundaries = {
                "training_start_utc": training.index[0],
                "training_end_utc": training.index[-1],
                "validation_start_utc": future.index[0],
                "validation_end_utc": future.index[-1],
            }
            if any(reference[name] != value for name, value in boundaries.items()):
                raise ValueError(
                    "Reconstructed fold boundaries differ from saved evidence."
                )
            prepared = prepare_window(
                training.loc[:, ACTIVE_FEATURES].astype("float64"),
                future.loc[:, ACTIVE_FEATURES].astype("float64"),
                selection_config,
            )
            feature_names = "|".join(prepared.selector.selected_features_)
            if feature_names != reference.selected_features:
                raise ValueError(
                    "Reconstructed selected features differ from saved evidence."
                )
            estimator = SVC(**json.loads(chosen.frozen_parameters))
            estimator.fit(prepared.training, training[chosen.target].astype("int64"))
            validation_metrics = calculate_classification_metrics(
                future[chosen.target],
                estimator.predict(prepared.evaluation),
                estimator.decision_function(prepared.evaluation),
            )
            for metric, value in validation_metrics.items():
                if metric != "metric_diagnostic" and not np.isclose(
                    value,
                    reference[metric],
                    rtol=1e-10,
                    atol=1e-12,
                    equal_nan=True,
                ):
                    raise ValueError(
                        f"Reconstructed validation {metric} differs from saved evidence."
                    )
            training_metrics = calculate_classification_metrics(
                training[chosen.target],
                estimator.predict(prepared.training),
                estimator.decision_function(prepared.training),
            )
            rows.append(
                {
                    "symbol": chosen.symbol,
                    "target": chosen.target,
                    "window_size": chosen.window_size,
                    "candidate_order": chosen.candidate_order,
                    "fold": fold,
                    **boundaries,
                    "training_rows": len(training),
                    "training_positive": int(training[chosen.target].eq(1).sum()),
                    "selected_features": feature_names,
                    "validation_reproduced": True,
                    **{
                        f"in_sample_{name}": value
                        for name, value in training_metrics.items()
                    },
                }
            )
    return pd.DataFrame(rows)
