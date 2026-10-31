"""Tests for leakage-safe daily feature selection."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.features.warmup import remove_leading_feature_warmup
from tcc_crypto.modeling.config import DailyFeatureSelectionConfig
from tcc_crypto.modeling.selection import (
    DailyFeatureSelector,
    iter_rolling_feature_selection,
    summarize_rolling_feature_selection,
)


def _selection_config(
    window_sizes: tuple[int, ...] = (3,),
) -> DailyFeatureSelectionConfig:
    return DailyFeatureSelectionConfig(
        variance_threshold=0.01,
        correlation_threshold=0.8,
        correlation_method="pearson",
        training_window_sizes=window_sizes,
        window_type="rolling",
        refit_frequency="every_prediction",
        prediction_step_observations=1,
        fit_scope="training_only",
    )


def _feature_frame(periods: int = 8) -> pd.DataFrame:
    position = pd.Series(range(periods), dtype="float64")
    return pd.DataFrame(
        {
            "signal": position.to_numpy(),
            "signal_duplicate": (position * 2.0).to_numpy(),
            "independent": ((position % 2) * 3.0).to_numpy(),
            "constant": [1.0] * periods,
        },
        index=pd.date_range("2026-01-01", periods=periods, freq="D", tz="UTC"),
    )


def test_removes_only_leading_indicator_warmup() -> None:
    features = _feature_frame()
    features.iloc[:2, 0] = float("nan")

    complete = remove_leading_feature_warmup(features)

    assert complete.index[0] == pd.Timestamp("2026-01-03", tz="UTC")
    assert len(complete) == 6


def test_variance_and_correlation_filters_are_fitted_on_training_data() -> None:
    features = _feature_frame()
    selector = DailyFeatureSelector(
        variance_threshold=0.01,
        correlation_threshold=0.8,
    )

    selected = selector.fit_transform(features)

    assert "constant" not in selected.columns
    assert "signal" in selected.columns
    assert "signal_duplicate" not in selected.columns
    assert tuple(selected.columns) == selector.selected_features_


def test_transform_reuses_fitted_columns_for_future_observation() -> None:
    features = _feature_frame()
    selector = DailyFeatureSelector().fit(features.iloc[:6])

    prediction = selector.transform(features.iloc[6:7])

    assert tuple(prediction.columns) == selector.selected_features_
    assert prediction.index.tolist() == [features.index[6]]


def test_falls_back_to_highest_variance_when_threshold_removes_everything() -> None:
    features = pd.DataFrame(
        {
            "lower_variance": [0.0, 0.001, 0.0, 0.001],
            "higher_variance": [0.0, 0.002, 0.0, 0.002],
        },
        index=pd.date_range("2026-01-01", periods=4, freq="D", tz="UTC"),
    )

    selected = DailyFeatureSelector(variance_threshold=0.01).fit_transform(features)

    assert selected.columns.tolist() == ["higher_variance"]


def test_rolling_windows_train_on_previous_rows_and_predict_next_row() -> None:
    features = _feature_frame(periods=6)

    steps = list(iter_rolling_feature_selection(features, _selection_config()))

    assert len(steps) == 3
    assert steps[0].training_start_utc == features.index[0]
    assert steps[0].training_end_utc == features.index[2]
    assert steps[0].prediction_time_utc == features.index[3]
    assert steps[1].training_start_utc == features.index[1]
    assert steps[1].prediction_time_utc == features.index[4]
    assert steps[0].prediction_time_utc not in steps[0].training_features.index


def test_future_change_does_not_affect_earlier_feature_selection() -> None:
    baseline = _feature_frame(periods=7)
    changed = baseline.copy()
    changed.iloc[-1] = [10_000.0, -500.0, 900.0, 70.0]

    baseline_steps = list(iter_rolling_feature_selection(baseline, _selection_config()))
    changed_steps = list(iter_rolling_feature_selection(changed, _selection_config()))

    for original, recalculated in zip(baseline_steps[:-1], changed_steps[:-1]):
        assert original.selected_features == recalculated.selected_features
        pd.testing.assert_frame_equal(
            original.training_features,
            recalculated.training_features,
        )
        pd.testing.assert_frame_equal(
            original.prediction_features,
            recalculated.prediction_features,
        )


def test_summarizes_selection_history_and_feature_frequency() -> None:
    features = _feature_frame(periods=6)

    summary = summarize_rolling_feature_selection(features, _selection_config())

    assert len(summary.history) == 3
    assert summary.window_summary.iloc[0]["prediction_count"] == 3
    constant = summary.feature_frequency.loc[
        summary.feature_frequency["feature"] == "constant"
    ].iloc[0]
    assert constant["selection_count"] == 0
    assert constant["selection_rate"] == 0.0
