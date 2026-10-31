"""Configuration for the approved frozen-parameter final classifier evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tcc_crypto.data.time import _parse_utc_day
from tcc_crypto.paths import FINAL_EVALUATION_CONFIG_PATH, resolve_path


@dataclass(frozen=True)
class FinalEvaluationConfig:
    evaluation_id: str
    grid_search_config: Path
    feature_start_utc: pd.Timestamp
    feature_end_utc: pd.Timestamp
    gap: int = 1
    single_class_training_policy: str = "record_no_prediction"
    comparison_observations: str = "common_successful_dates"


def load_final_evaluation_config(
    root: Path, path: Path = FINAL_EVALUATION_CONFIG_PATH
) -> FinalEvaluationConfig:
    """Read approved final settings without changing the development protocol."""
    payload = json.loads(resolve_path(root, path).read_text())
    if (
        payload["execution_status"] != "approved"
        or payload["single_class_training_policy"] != "record_no_prediction"
        or payload["comparison_observations"] != "common_successful_dates"
    ):
        raise ValueError(
            "Final evaluation must use the approved omission/comparison policy."
        )
    grid_path = resolve_path(root, payload["grid_search_config"])
    grid = json.loads(grid_path.read_text())
    final = grid["final_test"]
    if (
        final["evaluation"] != "one_step_walk_forward"
        or final["hyperparameters"] != "frozen_after_inner_validation"
        or final["prediction_step_observations"] != 1
        or final["gap_observations"] != 1
        or not all(
            final[key] is True
            for key in (
                "required",
                "chronologically_after_development",
                "refit_feature_selection_every_prediction",
                "refit_scaler_every_prediction",
                "refit_estimator_every_prediction",
            )
        )
    ):
        raise ValueError("Final evaluation settings differ from the approved protocol.")
    start = _parse_utc_day(final["feature_start_utc"], "final feature start")
    end = _parse_utc_day(final["feature_end_utc"], "final feature end")
    if start > end or _parse_utc_day(
        final["target_end_utc"], "final target end"
    ) != end + pd.Timedelta(days=1):
        raise ValueError("Inconsistent final feature/target boundaries.")
    expected_baselines = {
        "always_negative": {
            "estimator": "sklearn.dummy.DummyClassifier",
            "parameters": {"strategy": "constant", "constant": 0},
        },
        "training_class_frequency": {
            "estimator": "sklearn.dummy.DummyClassifier",
            "parameters": {"strategy": "prior"},
            "roc_score_source": "predict_proba_positive_class",
        },
        "default_svc": {
            "estimator": "sklearn.svm.SVC",
            "parameters": "defaults",
            "roc_score_source": "decision_function",
        },
        "implementation_status": "approved",
    }
    if grid["comparison_baselines"] != expected_baselines:
        raise ValueError("Final comparisons must use the three approved baselines.")
    return FinalEvaluationConfig(str(payload["evaluation_id"]), grid_path, start, end)
