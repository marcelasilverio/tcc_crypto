"""Modeling: config."""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd

from tcc_crypto.data.config import _parse_utc_day
from tcc_crypto.paths import SVM_GRID_SEARCH_RESULTS_DIR, resolve_path
from tcc_crypto.paths import repository_root as default_root
from tcc_crypto.targets.daily import DAY


@dataclass(frozen=True)
class DailyFeatureSelectionConfig:
    """Validated temporal feature-selection settings."""

    variance_threshold: float
    correlation_threshold: float
    correlation_method: str
    training_window_sizes: tuple[int, ...]
    window_type: str
    refit_frequency: str
    prediction_step_observations: int
    fit_scope: str


@dataclass(frozen=True)
class DailySvmGridSearchConfig:
    """Validated settings for the approved daily temporal SVC search."""

    experiment_id: str
    config_path: Path
    feature_config: Path
    collection_config: Path
    raw_directory: Path
    candidate_symbols: tuple[str, ...]
    excluded_symbols: tuple[str, ...]
    targets: tuple[str, ...]
    training_window_sizes: tuple[int, ...]
    development_start_utc: pd.Timestamp
    development_end_utc: pd.Timestamp
    n_splits: int
    test_size: int
    gap: int
    parameter_grid: tuple[dict[str, tuple[object, ...]], ...]
    candidate_count: int
    primary_metric: str
    tie_tolerance: float
    tie_break_order: tuple[str, ...]
    minimum_complete_rows: int
    output_directory: Path


def _load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def expand_parameter_grid(
    parameter_grid: Sequence[Mapping[str, Sequence[object]]],
) -> tuple[dict[str, object], ...]:
    """Expand conditional parameter blocks in deterministic configured order."""
    candidates: list[dict[str, object]] = []
    for block in parameter_grid:
        keys = tuple(block)
        values = tuple(tuple(block[key]) for key in keys)
        if not keys or any(not choices for choices in values):
            raise ValueError("Every parameter-grid block must contain values.")
        for combination in product(*values):
            candidates.append(dict(zip(keys, combination, strict=True)))
    return tuple(candidates)


def load_daily_svm_grid_search_config(
    path: Path, *, repository_root: Path | None = None
) -> DailySvmGridSearchConfig:
    """Load and strictly validate the approved grid-search configuration."""
    root = default_root(repository_root)
    path = resolve_path(root, path)
    payload = _load_json(path)
    feature_config = Path(str(payload["base_feature_config"]))
    feature_payload = _load_json(resolve_path(root, feature_config))
    collection_config = Path(str(feature_payload["collection_config"]))
    collection_payload = _load_json(resolve_path(root, collection_config))

    targets = tuple(str(value) for value in payload["targets"])
    if targets != ("target_2pct", "target_3pct", "target_4pct"):
        raise ValueError(
            "Approved targets are target_2pct, target_3pct, and target_4pct."
        )
    windows = tuple(int(value) for value in payload["training_window_sizes"])
    if windows != (60, 75, 90):
        raise ValueError("Approved training windows are 60, 75, and 90 days.")

    search_scope = payload["search_scope"]
    if not all(
        search_scope[key]
        for key in (
            "separate_by_symbol",
            "separate_by_target",
            "separate_by_training_window",
            "reuse_across_final_test_dates",
        )
    ):
        raise ValueError("The approved search scope must remain fully separated.")

    development = payload["development_period"]
    start = _parse_utc_day(development["feature_start_utc"], "feature_start_utc")
    end = _parse_utc_day(development["feature_end_utc"], "feature_end_utc")
    if (start, end) != (
        pd.Timestamp("2019-07-01", tz="UTC"),
        pd.Timestamp("2024-12-30", tz="UTC"),
    ):
        raise ValueError("Development boundaries differ from the approved period.")

    validation = payload["inner_validation"]
    if validation["splitter"] != "sklearn.model_selection.TimeSeriesSplit":
        raise ValueError("The approved splitter is TimeSeriesSplit.")
    if validation["shuffle"] is not False:
        raise ValueError("Temporal validation must not shuffle observations.")
    if validation["max_train_size_source"] != "training_window_size":
        raise ValueError("max_train_size must come from the training window.")
    n_splits = int(validation["n_splits"])
    test_size = int(validation["test_size"])
    gap = int(validation["gap_observations"])
    if (n_splits, test_size, gap) != (3, 60, 1):
        raise ValueError("Approved temporal validation uses 3 splits, 60 rows, gap 1.")

    raw_grid = payload["parameter_grid"]
    parameter_grid = tuple(
        {str(key): tuple(values) for key, values in block.items()} for block in raw_grid
    )
    candidates = expand_parameter_grid(parameter_grid)
    candidate_count = int(payload["candidate_count_per_target_window"])
    if len(candidates) != candidate_count or candidate_count != 186:
        raise ValueError("The approved conditional grid must contain 186 candidates.")

    selection = payload["selection"]
    tie_break_order = tuple(str(value) for value in selection["tie_break_order"])
    approved_tie_break = (
        "mean_precision_descending",
        "f1_standard_deviation_ascending",
        "mean_roc_auc_descending",
        "kernel_simplicity_linear_rbf_poly",
        "C_ascending",
        "parameter_grid_order",
    )
    if selection["primary_metric"] != "f1" or tie_break_order != approved_tie_break:
        raise ValueError("Grid-search ranking differs from the approved rule.")

    eligibility = payload["asset_eligibility"]
    symbols = tuple(str(value) for value in collection_payload["symbols"])
    if len(symbols) != int(eligibility["candidate_universe_size"]):
        raise ValueError(
            "Candidate-universe size does not match its collection config."
        )
    excluded_symbols = tuple(str(value) for value in eligibility["excluded_symbols"])
    if excluded_symbols != ("LUNAUSDT",):
        raise ValueError("The approved explicit exclusion is LUNAUSDT.")
    minimum_rows = int(eligibility["minimum_complete_labeled_rows_before_search"])
    expected_minimum = max(windows) + gap + n_splits * test_size
    if minimum_rows != expected_minimum or minimum_rows != 271:
        raise ValueError("The approved common eligibility minimum is 271 rows.")

    final_test = payload["final_test"]
    if (
        _parse_utc_day(final_test["boundary_gap_date_utc"], "boundary_gap_date_utc")
        != end + DAY
    ):
        raise ValueError(
            "The final-test boundary gap must immediately follow development."
        )
    if (
        _parse_utc_day(final_test["feature_start_utc"], "final feature start")
        != end + 2 * DAY
    ):
        raise ValueError("The final test must start after the approved boundary gap.")
    if payload["execution_status"] != "approved_for_implementation":
        raise ValueError("The grid search is not approved for implementation.")

    return DailySvmGridSearchConfig(
        experiment_id=str(payload["experiment_id"]),
        config_path=path,
        feature_config=feature_config,
        collection_config=collection_config,
        raw_directory=Path(str(collection_payload["output_directory"])),
        candidate_symbols=symbols,
        excluded_symbols=excluded_symbols,
        targets=targets,
        training_window_sizes=windows,
        development_start_utc=start,
        development_end_utc=end,
        n_splits=n_splits,
        test_size=test_size,
        gap=gap,
        parameter_grid=parameter_grid,
        candidate_count=candidate_count,
        primary_metric="f1",
        tie_tolerance=float(selection["floating_point_tolerance"]),
        tie_break_order=tie_break_order,
        minimum_complete_rows=minimum_rows,
        output_directory=Path(
            str(
                payload.get(
                    "output_directory",
                    SVM_GRID_SEARCH_RESULTS_DIR / str(payload["experiment_id"]),
                )
            )
        ),
    )
