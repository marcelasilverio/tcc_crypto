"""Features: warmup."""

from __future__ import annotations

import math

import pandas as pd


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
