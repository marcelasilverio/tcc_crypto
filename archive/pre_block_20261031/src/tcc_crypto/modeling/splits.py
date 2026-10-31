"""Modeling: splits."""

from __future__ import annotations

from sklearn.model_selection import TimeSeriesSplit

from tcc_crypto.modeling.config import DailySvmGridSearchConfig


def temporal_splits(
    row_count: int, config: DailySvmGridSearchConfig, window_size: int
) -> tuple[tuple[list[int], list[int]], ...]:
    """Return the approved fixed-window chronological split positions."""
    if window_size not in config.training_window_sizes:
        raise ValueError(f"Unsupported training window: {window_size}.")
    splitter = TimeSeriesSplit(
        n_splits=config.n_splits,
        max_train_size=window_size,
        test_size=config.test_size,
        gap=config.gap,
    )
    try:
        return tuple(
            (train.tolist(), validation.tolist())
            for train, validation in splitter.split(range(row_count))
        )
    except ValueError as error:
        raise ValueError(
            f"{row_count} rows cannot support the approved temporal splits."
        ) from error
