"""Shared distribution estimators; callers retain their domain units and conventions."""

from __future__ import annotations

import pandas as pd


def distribution_statistics(series: pd.Series, *, ddof: int = 1) -> dict[str, float]:
    """Observed values only, linear quartiles, sample skewness and Fisher excess kurtosis."""
    q1, median, q3 = series.quantile([0.25, 0.5, 0.75]).tolist()
    return {
        "q1": q1,
        "median": median,
        "q3": q3,
        "mean": series.mean(),
        "std": series.std(ddof=ddof),
        "variance": series.var(ddof=ddof),
        "minimum": series.min(),
        "maximum": series.max(),
        "skewness": series.skew(),
        "excess_kurtosis": series.kurt(),
    }
