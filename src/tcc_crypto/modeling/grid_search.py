"""Modeling: grid search."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Sequence

import numpy as np
import pandas as pd
from sklearn.svm import SVC

from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.modeling.config import (
    DailyFeatureSelectionConfig,
    DailySvmGridSearchConfig,
    expand_parameter_grid,
)
from tcc_crypto.modeling.eligibility import assess_symbol_eligibility
from tcc_crypto.modeling.metrics import calculate_classification_metrics
from tcc_crypto.modeling.preprocessing import prepare_window
from tcc_crypto.modeling.ranking import (
    _aggregate_candidate_results,
    _parameter_values,
    rank_candidates,
)
from tcc_crypto.modeling.splits import temporal_splits


@dataclass(frozen=True)
class DailySvmGridSearchResult:
    """Eligibility, fold metrics, candidate summaries, and selected models."""

    eligibility: pd.DataFrame
    fold_results: pd.DataFrame
    candidate_results: pd.DataFrame
    selected_configurations: pd.DataFrame


def run_temporal_grid_search(
    dataset: pd.DataFrame,
    *,
    symbol: str,
    config: DailySvmGridSearchConfig,
    selection_config: DailyFeatureSelectionConfig,
    feature_columns: Sequence[str] = ACTIVE_FEATURES,
) -> DailySvmGridSearchResult:
    """Evaluate all eligible symbol-target-window candidates on temporal folds."""
    feature_columns = tuple(str(value) for value in feature_columns)
    eligibility = assess_symbol_eligibility(
        dataset,
        symbol=symbol,
        config=config,
        feature_columns=feature_columns,
    )
    candidates = expand_parameter_grid(config.parameter_grid)
    fold_rows: list[dict[str, object]] = []

    for eligibility_row in eligibility.itertuples(index=False):
        if eligibility_row.status != "eligible":
            continue
        target = str(eligibility_row.target)
        window_size = int(eligibility_row.window_size)
        complete = dataset.loc[:, [*feature_columns, target]].dropna()
        features = complete.loc[:, feature_columns].astype("float64")
        labels = complete[target].astype("int64")

        for fold_index, (train_positions, validation_positions) in enumerate(
            temporal_splits(len(complete), config, window_size)
        ):
            training_features = features.iloc[train_positions]
            validation_features = features.iloc[validation_positions]
            training_labels = labels.iloc[train_positions]
            validation_labels = labels.iloc[validation_positions]
            prepared = prepare_window(
                training_features, validation_features, selection_config
            )
            selector = prepared.selector
            scaled_training = prepared.training
            scaled_validation = prepared.evaluation

            for candidate_order, parameters in enumerate(candidates):
                row: dict[str, object] = {
                    "symbol": symbol,
                    "target": target,
                    "window_size": window_size,
                    "candidate_order": candidate_order,
                    "fold": fold_index,
                    **_parameter_values(parameters),
                    "training_start_utc": training_features.index[0],
                    "training_end_utc": training_features.index[-1],
                    "validation_start_utc": validation_features.index[0],
                    "validation_end_utc": validation_features.index[-1],
                    "training_negative": int((training_labels == 0).sum()),
                    "training_positive": int((training_labels == 1).sum()),
                    "validation_negative": int((validation_labels == 0).sum()),
                    "validation_positive": int((validation_labels == 1).sum()),
                    "selected_feature_count": len(selector.selected_features_),
                    "selected_features": "|".join(selector.selected_features_),
                }
                row.update(
                    evaluate_candidate(
                        parameters,
                        training_labels,
                        validation_labels,
                        scaled_training,
                        scaled_validation,
                    )
                )
                fold_rows.append(row)

    return summarize_search(eligibility, pd.DataFrame(fold_rows), config.tie_tolerance)


def summarize_search(
    eligibility: pd.DataFrame, fold_results: pd.DataFrame, tolerance: float
) -> DailySvmGridSearchResult:
    """Aggregate and rank candidates after every fold has been evaluated."""
    if fold_results.empty:
        return DailySvmGridSearchResult(
            eligibility=eligibility,
            fold_results=fold_results,
            candidate_results=pd.DataFrame(),
            selected_configurations=pd.DataFrame(),
        )

    aggregate_results = _aggregate_candidate_results(fold_results)
    ranked_groups: list[pd.DataFrame] = []
    selected_rows: list[dict[str, object]] = []
    for _, group in aggregate_results.groupby(
        ["symbol", "target", "window_size"], sort=True
    ):
        ranked = rank_candidates(group, tolerance=tolerance)
        ranked_groups.append(ranked)
        best = ranked.loc[ranked["selection_rank"] == 1].iloc[0]
        selected_rows.append(best.to_dict())
    candidate_results = pd.concat(ranked_groups, ignore_index=True)
    selected = (
        pd.DataFrame(selected_rows)
        .sort_values(["symbol", "target", "window_size"])
        .reset_index(drop=True)
    )
    return DailySvmGridSearchResult(
        eligibility=eligibility,
        fold_results=fold_results,
        candidate_results=candidate_results,
        selected_configurations=selected,
    )


def evaluate_candidate(
    parameters: dict[str, object],
    training_labels: pd.Series,
    validation_labels: pd.Series,
    scaled_training: np.ndarray,
    scaled_validation: np.ndarray,
) -> dict[str, object]:
    """Fit and score one candidate, preserving failed-fit audit records."""
    row: dict[str, object] = {}
    started = perf_counter()
    try:
        estimator = SVC(**parameters)
        estimator.fit(scaled_training, training_labels)
        prediction = estimator.predict(scaled_validation)
        scores = estimator.decision_function(scaled_validation)
        row.update(
            calculate_classification_metrics(
                validation_labels.to_numpy(), prediction, scores
            )
        )
        row["status"] = "ok"
        row["error"] = ""
    except Exception as error:  # persisted for candidate audit
        row.update(
            {
                metric: float("nan")
                for metric in (
                    "accuracy",
                    "precision",
                    "recall",
                    "f1",
                    "balanced_accuracy",
                    "roc_auc",
                    "average_precision",
                )
            }
        )
        row["metric_diagnostic"] = ""
        row["status"] = "fit_error"
        row["error"] = f"{type(error).__name__}: {error}"
    row["fit_seconds"] = perf_counter() - started
    return row
