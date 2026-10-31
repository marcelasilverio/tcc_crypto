"""Tests for the rolling default-SVC pilot."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.modeling.config import DailyFeatureSelectionConfig
from tcc_crypto.modeling.pilot import run_default_svc_rolling_pilot


def _selection_config(window_size: int = 4) -> DailyFeatureSelectionConfig:
    return DailyFeatureSelectionConfig(
        variance_threshold=0.0,
        correlation_threshold=0.99,
        correlation_method="pearson",
        training_window_sizes=(window_size,),
        window_type="rolling",
        refit_frequency="every_prediction",
        prediction_step_observations=1,
        fit_scope="training_only",
    )


def _pilot_dataset(periods: int = 12) -> pd.DataFrame:
    positions = list(range(periods))
    return pd.DataFrame(
        {
            "signal": [float(position % 5) for position in positions],
            "secondary": [float((position * position) % 7) for position in positions],
            "target_2pct": [position % 2 for position in positions],
        },
        index=pd.date_range("2019-07-01", periods=periods, freq="D", tz="UTC"),
    )


def test_rolls_training_then_scales_and_predicts_next_row() -> None:
    dataset = _pilot_dataset()

    result = run_default_svc_rolling_pilot(
        dataset,
        selection_config=_selection_config(),
        feature_columns=("signal", "secondary"),
        target_columns=("target_2pct",),
    )

    assert len(result.predictions) == 8
    first = result.predictions.iloc[0]
    assert first["training_start_utc"] == dataset.index[0]
    assert first["training_end_utc"] == dataset.index[3]
    assert first["prediction_time_utc"] == dataset.index[4]
    assert first["status"] == "ok"
    assert len(result.summary) == 1
    assert result.summary.iloc[0]["successful_prediction_count"] == 8


def test_future_feature_change_does_not_change_earlier_predictions() -> None:
    baseline = _pilot_dataset()
    changed = baseline.copy()
    changed.iloc[-1, changed.columns.get_loc("signal")] = 1_000_000.0
    changed.iloc[-1, changed.columns.get_loc("secondary")] = -1_000_000.0

    baseline_result = run_default_svc_rolling_pilot(
        baseline,
        selection_config=_selection_config(),
        feature_columns=("signal", "secondary"),
        target_columns=("target_2pct",),
    )
    changed_result = run_default_svc_rolling_pilot(
        changed,
        selection_config=_selection_config(),
        feature_columns=("signal", "secondary"),
        target_columns=("target_2pct",),
    )

    columns = ["prediction", "decision_score"]
    pd.testing.assert_frame_equal(
        baseline_result.predictions.iloc[:-1][columns].reset_index(drop=True),
        changed_result.predictions.iloc[:-1][columns].reset_index(drop=True),
    )


def test_records_single_class_training_without_inventing_prediction() -> None:
    dataset = _pilot_dataset()
    dataset["target_2pct"] = 0

    result = run_default_svc_rolling_pilot(
        dataset,
        selection_config=_selection_config(),
        feature_columns=("signal", "secondary"),
        target_columns=("target_2pct",),
    )

    assert set(result.predictions["status"]) == {"single_class_training"}
    assert result.predictions["prediction"].isna().all()
    assert result.summary.iloc[0]["successful_prediction_count"] == 0
