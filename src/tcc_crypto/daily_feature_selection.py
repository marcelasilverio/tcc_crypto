"""Select daily features inside leakage-safe rolling training windows."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator

import pandas as pd
from feature_engine.selection import DropCorrelatedFeatures
from sklearn.feature_selection import VarianceThreshold

from tcc_crypto.daily_features import DailyFeatureSelectionConfig


def _validate_numeric_feature_frame(features: pd.DataFrame) -> None:
    if features.empty:
        raise ValueError("Feature data contains no observations.")
    if features.columns.has_duplicates:
        raise ValueError("Feature data contains duplicate columns.")
    if not isinstance(features.index, pd.DatetimeIndex):
        raise TypeError("Feature data must use a DatetimeIndex.")
    if features.index.tz is None or str(features.index.tz) != "UTC":
        raise ValueError("Feature timestamps must use UTC.")
    if features.index.has_duplicates:
        raise ValueError("Feature data contains duplicate timestamps.")
    if not features.index.is_monotonic_increasing:
        raise ValueError("Feature data must be chronologically ordered.")
    if features.isna().any().any():
        raise ValueError("Feature selection requires complete feature rows.")
    try:
        finite = features.map(math.isfinite)
    except TypeError as error:
        raise TypeError("All feature values must be numeric.") from error
    if not finite.all().all():
        raise ValueError("Feature data contains non-finite values.")


def remove_leading_feature_warmup(features: pd.DataFrame) -> pd.DataFrame:
    """Remove only the leading incomplete rows produced by indicator warm-up.

    Missing values after the first complete row are rejected because they do
    not represent normal indicator warm-up and require separate treatment.
    """
    if features.empty:
        raise ValueError("Feature data contains no observations.")
    complete_rows = features.notna().all(axis=1)
    if not complete_rows.any():
        raise ValueError("Feature data has no complete observation.")
    first_complete_position = int(complete_rows.to_numpy().argmax())
    if not complete_rows.iloc[first_complete_position:].all():
        raise ValueError("Feature data contains missing values after warm-up.")
    complete = features.iloc[first_complete_position:].copy()
    _validate_numeric_feature_frame(complete)
    return complete


class DailyFeatureSelector:
    """Fit variance and correlation filters on one training window."""

    def __init__(
        self,
        *,
        variance_threshold: float = 0.01,
        correlation_threshold: float = 0.8,
    ) -> None:
        if variance_threshold < 0.0:
            raise ValueError("variance_threshold must be non-negative.")
        if not 0.0 < correlation_threshold <= 1.0:
            raise ValueError("correlation_threshold must be in (0, 1].")
        self.variance_threshold = float(variance_threshold)
        self.correlation_threshold = float(correlation_threshold)

    def fit(self, features: pd.DataFrame) -> DailyFeatureSelector:
        """Fit both filters using training observations only."""
        _validate_numeric_feature_frame(features)
        self.input_features_ = tuple(str(column) for column in features.columns)
        self.variance_selector_ = VarianceThreshold(
            threshold=self.variance_threshold
        )
        self.variance_fallback_feature_: str | None = None

        try:
            variance_values = self.variance_selector_.fit_transform(features)
            variance_features = tuple(
                features.columns[self.variance_selector_.get_support()].astype(str)
            )
            after_variance = pd.DataFrame(
                variance_values,
                columns=variance_features,
                index=features.index,
            )
        except ValueError as error:
            if "No feature in X meets the variance threshold" not in str(error):
                raise
            variances = features.var(numeric_only=True)
            if variances.empty or variances.isna().all():
                raise ValueError("No feature has a valid training variance.") from error
            self.variance_fallback_feature_ = str(variances.idxmax())
            variance_features = (self.variance_fallback_feature_,)
            after_variance = features.loc[:, list(variance_features)].copy()

        self.variance_features_ = variance_features
        self.correlation_selector_: DropCorrelatedFeatures | None = None
        if len(variance_features) >= 2:
            self.correlation_selector_ = DropCorrelatedFeatures(
                threshold=self.correlation_threshold,
                method="pearson",
                missing_values="ignore",
            )
            selected = self.correlation_selector_.fit_transform(after_variance)
        else:
            selected = after_variance
        self.selected_features_ = tuple(str(column) for column in selected.columns)
        return self

    def transform(self, features: pd.DataFrame) -> pd.DataFrame:
        """Apply the already fitted training filters to later observations."""
        if not hasattr(self, "selected_features_"):
            raise RuntimeError("DailyFeatureSelector must be fitted before transform.")
        _validate_numeric_feature_frame(features)
        missing = set(self.input_features_).difference(features.columns)
        if missing:
            raise ValueError(f"Feature data is missing fitted columns: {sorted(missing)}.")
        ordered = features.loc[:, list(self.input_features_)]

        if self.variance_fallback_feature_ is not None:
            after_variance = ordered.loc[:, [self.variance_fallback_feature_]].copy()
        else:
            values = self.variance_selector_.transform(ordered)
            after_variance = pd.DataFrame(
                values,
                columns=self.variance_features_,
                index=ordered.index,
            )

        if self.correlation_selector_ is None:
            return after_variance
        return self.correlation_selector_.transform(after_variance)

    def fit_transform(self, features: pd.DataFrame) -> pd.DataFrame:
        """Fit on and transform one training window."""
        return self.fit(features).transform(features)


@dataclass(frozen=True)
class RollingFeatureSelectionStep:
    """One fitted training window and its transformed next observation."""

    window_size: int
    training_start_utc: pd.Timestamp
    training_end_utc: pd.Timestamp
    prediction_time_utc: pd.Timestamp
    selected_features: tuple[str, ...]
    training_features: pd.DataFrame
    prediction_features: pd.DataFrame


@dataclass(frozen=True)
class RollingFeatureSelectionSummary:
    """Compact tables describing feature selection across rolling steps."""

    history: pd.DataFrame
    feature_frequency: pd.DataFrame
    window_summary: pd.DataFrame


def iter_rolling_feature_selection(
    features: pd.DataFrame,
    config: DailyFeatureSelectionConfig,
) -> Iterator[RollingFeatureSelectionStep]:
    """Refit feature selection for every rolling one-step prediction.

    The prediction row is never passed to ``fit``. A fresh selector is fitted
    to each trailing training window and then applied unchanged to the next
    observation.
    """
    _validate_numeric_feature_frame(features)
    if config.correlation_method != "pearson":
        raise ValueError("Only Pearson correlation is implemented.")
    if config.window_type != "rolling":
        raise ValueError("Only rolling training windows are implemented.")
    if config.refit_frequency != "every_prediction":
        raise ValueError("Feature selection must be refitted for every prediction.")
    if config.prediction_step_observations != 1:
        raise ValueError("Only one-observation prediction steps are implemented.")
    if config.fit_scope != "training_only":
        raise ValueError("Feature selection must use training data only.")

    for window_size in config.training_window_sizes:
        if window_size < 2:
            raise ValueError("Training window sizes must be at least two.")
        for prediction_position in range(window_size, len(features)):
            training = features.iloc[
                prediction_position - window_size : prediction_position
            ]
            prediction = features.iloc[prediction_position : prediction_position + 1]
            selector = DailyFeatureSelector(
                variance_threshold=config.variance_threshold,
                correlation_threshold=config.correlation_threshold,
            )
            selected_training = selector.fit_transform(training)
            selected_prediction = selector.transform(prediction)
            yield RollingFeatureSelectionStep(
                window_size=window_size,
                training_start_utc=training.index[0],
                training_end_utc=training.index[-1],
                prediction_time_utc=prediction.index[0],
                selected_features=selector.selected_features_,
                training_features=selected_training,
                prediction_features=selected_prediction,
            )


def summarize_rolling_feature_selection(
    features: pd.DataFrame,
    config: DailyFeatureSelectionConfig,
) -> RollingFeatureSelectionSummary:
    """Summarize selected features without retaining fitted training matrices."""
    history_rows: list[dict[str, object]] = []
    selection_counts = {
        window_size: {str(column): 0 for column in features.columns}
        for window_size in config.training_window_sizes
    }

    for step in iter_rolling_feature_selection(features, config):
        history_rows.append(
            {
                "window_size": step.window_size,
                "training_start_utc": step.training_start_utc,
                "training_end_utc": step.training_end_utc,
                "prediction_time_utc": step.prediction_time_utc,
                "selected_feature_count": len(step.selected_features),
                "selected_features": "|".join(step.selected_features),
            }
        )
        for feature in step.selected_features:
            selection_counts[step.window_size][feature] += 1

    history = pd.DataFrame(history_rows)
    if history.empty:
        raise ValueError("Not enough complete observations for any training window.")

    frequency_rows: list[dict[str, object]] = []
    for window_size, feature_counts in selection_counts.items():
        prediction_count = int((history["window_size"] == window_size).sum())
        if prediction_count == 0:
            continue
        for feature, count in feature_counts.items():
            frequency_rows.append(
                {
                    "window_size": window_size,
                    "feature": feature,
                    "selection_count": count,
                    "prediction_count": prediction_count,
                    "selection_rate": count / prediction_count,
                }
            )
    feature_frequency = pd.DataFrame(frequency_rows)
    window_summary = (
        history.groupby("window_size", as_index=False)["selected_feature_count"]
        .agg(
            prediction_count="count",
            minimum_selected="min",
            mean_selected="mean",
            maximum_selected="max",
        )
        .sort_values("window_size")
        .reset_index(drop=True)
    )
    return RollingFeatureSelectionSummary(
        history=history,
        feature_frequency=feature_frequency,
        window_summary=window_summary,
    )
