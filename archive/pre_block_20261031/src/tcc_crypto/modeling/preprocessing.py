"""Fit selection and scaling on one training window, never on later rows."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from tcc_crypto.modeling.config import DailyFeatureSelectionConfig
from tcc_crypto.modeling.selection import DailyFeatureSelector


@dataclass(frozen=True)
class PreparedWindow:
    training: np.ndarray
    evaluation: np.ndarray
    selector: DailyFeatureSelector
    scaler: StandardScaler


def prepare_window(
    training: pd.DataFrame,
    evaluation: pd.DataFrame,
    config: DailyFeatureSelectionConfig,
) -> PreparedWindow:
    """Fit fresh preprocessing objects once per training window/fold."""
    if training.index.max() >= evaluation.index.min():
        raise ValueError("Training must precede every evaluation observation.")
    selector = DailyFeatureSelector(
        variance_threshold=config.variance_threshold,
        correlation_threshold=config.correlation_threshold,
    )
    selected_training = selector.fit_transform(training)
    selected_evaluation = selector.transform(evaluation)
    scaler = StandardScaler()
    return PreparedWindow(
        scaler.fit_transform(selected_training),
        scaler.transform(selected_evaluation),
        selector,
        scaler,
    )
