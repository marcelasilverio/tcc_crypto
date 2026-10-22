"""Modeling: metrics."""

from __future__ import annotations

import warnings
from typing import Sequence

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _binary_metrics(y_true: Sequence[int], y_pred: Sequence[int]) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }


def calculate_classification_metrics(
    y_true: Sequence[int], y_pred: Sequence[int], decision_scores: Sequence[float]
) -> dict[str, object]:
    """Calculate approved fold metrics and mark undefined ranking metrics."""
    true = pd.Series(y_true, dtype="int64")
    predicted = pd.Series(y_pred, dtype="int64")
    scores = pd.Series(decision_scores, dtype="float64")
    if true.empty or len(true) != len(predicted) or len(true) != len(scores):
        raise ValueError("Metric inputs must be non-empty and equally sized.")
    diagnostics: list[str] = []
    if true.nunique() < 2:
        roc_auc = float("nan")
        average_precision = float("nan")
        diagnostics.append("single_class_validation")
    else:
        roc_auc = float(roc_auc_score(true, scores))
        average_precision = float(average_precision_score(true, scores))
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message="A single label was found", category=UserWarning
        )
        balanced_accuracy = float(balanced_accuracy_score(true, predicted))
    return {
        **_binary_metrics(true, predicted),
        "balanced_accuracy": balanced_accuracy,
        "roc_auc": roc_auc,
        "average_precision": average_precision,
        "metric_diagnostic": "|".join(diagnostics),
    }
