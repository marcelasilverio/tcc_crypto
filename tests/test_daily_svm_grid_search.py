"""Tests for the approved temporal SVC grid-search implementation."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from tcc_crypto.daily_features import DailyFeatureSelectionConfig
from tcc_crypto.daily_svm_grid_search import (
    assess_symbol_eligibility,
    calculate_classification_metrics,
    expand_parameter_grid,
    load_daily_svm_grid_search_config,
    run_temporal_grid_search,
    select_best_candidate,
    temporal_splits,
)


def _approved_config():
    return load_daily_svm_grid_search_config(
        Path("configs/binance_daily_svm_grid_search.json")
    )


def _small_config():
    return replace(
        _approved_config(),
        targets=("target_2pct",),
        training_window_sizes=(4,),
        n_splits=2,
        test_size=3,
        gap=1,
        parameter_grid=(
            {
                "kernel": ("linear",),
                "C": (0.1, 1.0),
                "class_weight": (None,),
            },
        ),
        candidate_count=2,
        minimum_complete_rows=11,
    )


def _selection_config() -> DailyFeatureSelectionConfig:
    return DailyFeatureSelectionConfig(
        variance_threshold=0.0,
        correlation_threshold=0.99,
        correlation_method="pearson",
        training_window_sizes=(4,),
        window_type="rolling",
        refit_frequency="every_prediction",
        prediction_step_observations=1,
        fit_scope="training_only",
    )


def _dataset(periods: int = 12) -> pd.DataFrame:
    positions = list(range(periods))
    return pd.DataFrame(
        {
            "signal": [float(position % 5) for position in positions],
            "secondary": [float((position * position) % 7) for position in positions],
            "target_2pct": [position % 2 for position in positions],
            "feature_is_imputed": [False] * periods,
            "target_is_imputed": [False] * periods,
        },
        index=pd.date_range("2020-01-01", periods=periods, freq="D", tz="UTC"),
    )


def test_loads_approved_grid_and_expands_only_compatible_candidates() -> None:
    config = _approved_config()

    candidates = expand_parameter_grid(config.parameter_grid)

    assert len(candidates) == 186
    assert sum(candidate["kernel"] == "linear" for candidate in candidates) == 6
    assert sum(candidate["kernel"] == "rbf" for candidate in candidates) == 18
    assert sum(candidate["kernel"] == "poly" for candidate in candidates) == 162
    assert all("gamma" not in candidate for candidate in candidates[:6])
    assert config.minimum_complete_rows == 271


def test_temporal_splits_apply_gap_and_never_train_on_validation_or_future() -> None:
    config = _approved_config()

    splits = temporal_splits(271, config, 90)

    assert len(splits) == 3
    first_train, first_validation = splits[0]
    assert len(first_train) == 90
    assert len(first_validation) == 60
    assert first_train[-1] == 89
    assert first_validation[0] == 91
    for train, validation in splits:
        assert max(train) + config.gap < min(validation)
        assert set(train).isdisjoint(validation)


def test_eligibility_records_class_counts_and_rejects_single_class_training() -> None:
    config = _small_config()
    dataset = _dataset()

    eligible = assess_symbol_eligibility(
        dataset,
        symbol="BTCUSDT",
        config=config,
        feature_columns=("signal", "secondary"),
    )
    single_class = dataset.copy()
    single_class["target_2pct"] = 0
    ineligible = assess_symbol_eligibility(
        single_class,
        symbol="BTCUSDT",
        config=config,
        feature_columns=("signal", "secondary"),
    )

    assert eligible.iloc[0]["status"] == "eligible"
    assert eligible.iloc[0]["complete_labeled_rows"] == 12
    assert ineligible.iloc[0]["status"] == "ineligible"
    assert "single_class_training_fold_0" in ineligible.iloc[0]["reason"]


def test_explicit_luna_exclusion_overrides_sufficient_history() -> None:
    config = _small_config()

    eligibility = assess_symbol_eligibility(
        _dataset(),
        symbol="LUNAUSDT",
        config=config,
        feature_columns=("signal", "secondary"),
    )

    assert eligibility.iloc[0]["status"] == "ineligible"
    assert "explicit_symbol_exclusion" in eligibility.iloc[0]["reason"]


def test_grid_search_runs_each_candidate_on_each_fold_and_records_boundaries() -> None:
    config = _small_config()
    dataset = _dataset()

    result = run_temporal_grid_search(
        dataset,
        symbol="BTCUSDT",
        config=config,
        selection_config=_selection_config(),
        feature_columns=("signal", "secondary"),
    )

    assert len(result.fold_results) == 4
    assert set(result.fold_results["status"]) == {"ok"}
    assert len(result.candidate_results) == 2
    assert sorted(result.candidate_results["selection_rank"]) == [1, 2]
    assert len(result.selected_configurations) == 1
    assert result.selected_configurations.iloc[0]["selection_rank"] == 1
    first = result.fold_results.iloc[0]
    assert first["training_end_utc"] < first["validation_start_utc"]
    assert (
        first["validation_start_utc"] - first["training_end_utc"]
        == pd.Timedelta(days=2)
    )


def test_future_feature_change_does_not_change_an_earlier_fold() -> None:
    config = _small_config()
    baseline = _dataset()
    changed = baseline.copy()
    changed.iloc[-1, changed.columns.get_loc("signal")] = 1_000_000.0
    changed.iloc[-1, changed.columns.get_loc("secondary")] = -1_000_000.0

    baseline_result = run_temporal_grid_search(
        baseline,
        symbol="BTCUSDT",
        config=config,
        selection_config=_selection_config(),
        feature_columns=("signal", "secondary"),
    )
    changed_result = run_temporal_grid_search(
        changed,
        symbol="BTCUSDT",
        config=config,
        selection_config=_selection_config(),
        feature_columns=("signal", "secondary"),
    )

    comparison_columns = [
        "candidate_order",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
    ]
    pd.testing.assert_frame_equal(
        baseline_result.fold_results.loc[
            baseline_result.fold_results["fold"] == 0, comparison_columns
        ].reset_index(drop=True),
        changed_result.fold_results.loc[
            changed_result.fold_results["fold"] == 0, comparison_columns
        ].reset_index(drop=True),
    )


def test_tie_break_prefers_precision_then_simpler_kernel_and_lower_c() -> None:
    candidates = pd.DataFrame(
        [
            {
                "mean_f1": 0.8,
                "mean_precision": 0.7,
                "f1_standard_deviation": 0.1,
                "mean_roc_auc": 0.9,
                "kernel": "rbf",
                "C": 0.1,
                "candidate_order": 0,
                "failed_fold_count": 0,
            },
            {
                "mean_f1": 0.8,
                "mean_precision": 0.8,
                "f1_standard_deviation": 0.1,
                "mean_roc_auc": 0.8,
                "kernel": "poly",
                "C": 10.0,
                "candidate_order": 1,
                "failed_fold_count": 0,
            },
            {
                "mean_f1": 0.8,
                "mean_precision": 0.8,
                "f1_standard_deviation": 0.1,
                "mean_roc_auc": 0.8,
                "kernel": "linear",
                "C": 1.0,
                "candidate_order": 2,
                "failed_fold_count": 0,
            },
        ]
    )

    selected = select_best_candidate(candidates, tolerance=1e-12)

    assert selected["candidate_order"] == 2


def test_single_class_validation_marks_ranking_metrics_undefined() -> None:
    metrics = calculate_classification_metrics(
        [0, 0, 0], [0, 0, 0], [-1.0, -0.5, -0.1]
    )

    assert pd.isna(metrics["roc_auc"])
    assert pd.isna(metrics["average_precision"])
    assert metrics["metric_diagnostic"] == "single_class_validation"
