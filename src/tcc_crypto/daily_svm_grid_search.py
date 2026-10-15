"""Run the approved leakage-safe temporal SVC hyperparameter search."""

from __future__ import annotations

import json
import subprocess
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from itertools import product
from pathlib import Path
from time import perf_counter
from typing import Mapping, Sequence

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
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from tcc_crypto.daily_feature_selection import (
    DailyFeatureSelector,
    remove_leading_feature_warmup,
)
from tcc_crypto.daily_features import (
    ACTIVE_FEATURES,
    DailyFeatureSelectionConfig,
    calculate_daily_features,
    load_daily_feature_input,
)
from tcc_crypto.daily_future_high_returns import find_symbol_csv
from tcc_crypto.daily_modeling_dataset import build_next_day_d0_targets

DAY = pd.Timedelta(days=1)
PARAMETER_COLUMNS = ("kernel", "C", "gamma", "degree", "coef0", "class_weight")


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


@dataclass(frozen=True)
class SymbolDevelopmentDataset:
    """One symbol's development-only modeling data and source evidence."""

    symbol: str
    dataset: pd.DataFrame
    raw_path: Path
    raw_sha256: str
    first_observed_utc: pd.Timestamp
    last_observed_utc: pd.Timestamp


@dataclass(frozen=True)
class DailySvmGridSearchResult:
    """Eligibility, fold metrics, candidate summaries, and selected models."""

    eligibility: pd.DataFrame
    fold_results: pd.DataFrame
    candidate_results: pd.DataFrame
    selected_configurations: pd.DataFrame


def _parse_utc_day(value: object, field_name: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"{field_name} must include an explicit UTC offset.")
    timestamp = timestamp.tz_convert("UTC")
    if timestamp != timestamp.normalize():
        raise ValueError(f"{field_name} must be aligned to a UTC day.")
    return timestamp


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


def load_daily_svm_grid_search_config(path: Path) -> DailySvmGridSearchConfig:
    """Load and strictly validate the approved grid-search configuration."""
    payload = _load_json(path)
    feature_config = Path(str(payload["base_feature_config"]))
    feature_payload = _load_json(feature_config)
    collection_config = Path(str(feature_payload["collection_config"]))
    collection_payload = _load_json(collection_config)

    targets = tuple(str(value) for value in payload["targets"])
    if targets != ("target_2pct", "target_3pct", "target_4pct"):
        raise ValueError("Approved targets are target_2pct, target_3pct, and target_4pct.")
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
        {str(key): tuple(values) for key, values in block.items()}
        for block in raw_grid
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
        raise ValueError("Candidate-universe size does not match its collection config.")
    excluded_symbols = tuple(str(value) for value in eligibility["excluded_symbols"])
    if excluded_symbols != ("LUNAUSDT",):
        raise ValueError("The approved explicit exclusion is LUNAUSDT.")
    minimum_rows = int(eligibility["minimum_complete_labeled_rows_before_search"])
    expected_minimum = max(windows) + gap + n_splits * test_size
    if minimum_rows != expected_minimum or minimum_rows != 271:
        raise ValueError("The approved common eligibility minimum is 271 rows.")

    final_test = payload["final_test"]
    if _parse_utc_day(final_test["boundary_gap_date_utc"], "boundary_gap_date_utc") != end + DAY:
        raise ValueError("The final-test boundary gap must immediately follow development.")
    if _parse_utc_day(final_test["feature_start_utc"], "final feature start") != end + 2 * DAY:
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
        output_directory=Path(str(payload["output_directory"])),
    )


def build_symbol_development_dataset(
    config: DailySvmGridSearchConfig, symbol: str
) -> SymbolDevelopmentDataset:
    """Build features and targets without loading final-test observations.

    June 2019 is retained as indicator warm-up. The day immediately after the
    development feature period is loaded only to construct the final next-day
    development target; no feature row from that boundary day is retained.
    """
    if symbol not in config.candidate_symbols:
        raise ValueError(f"{symbol} is not in the configured candidate universe.")
    raw_path = find_symbol_csv(config.raw_directory, symbol)
    aligned = load_daily_feature_input(raw_path, fill_internal_gaps=True)
    first_observed = aligned.index[0]
    last_observed = aligned.index[-1]
    warmup_start = config.development_start_utc - pd.Timedelta(days=30)
    required_end = config.development_end_utc + DAY
    calculation_values = aligned.loc[
        (aligned.index >= warmup_start) & (aligned.index <= required_end)
    ].copy()
    if calculation_values.empty:
        raise ValueError(f"{symbol} has no observations in the development range.")

    features = calculate_daily_features(calculation_values)
    complete_features = remove_leading_feature_warmup(features)
    development_features = complete_features.loc[
        (complete_features.index >= config.development_start_utc)
        & (complete_features.index <= config.development_end_utc)
    ].copy()
    if development_features.empty:
        raise ValueError(f"{symbol} has no complete development feature rows.")
    if development_features.index.max() > config.development_end_utc:
        raise AssertionError("Final-test features entered the development dataset.")

    targets = build_next_day_d0_targets(
        calculation_values, development_features.index
    )
    dataset = development_features.join(targets)
    dataset.insert(0, "symbol", symbol)
    dataset.insert(
        1,
        "feature_is_imputed",
        calculation_values["is_imputed"].reindex(dataset.index).astype("boolean"),
    )
    dataset.attrs["first_observed_utc"] = first_observed
    dataset.attrs["last_observed_utc"] = last_observed
    dataset.attrs["raw_path"] = str(raw_path)
    return SymbolDevelopmentDataset(
        symbol=symbol,
        dataset=dataset,
        raw_path=raw_path,
        raw_sha256=sha256(raw_path.read_bytes()).hexdigest(),
        first_observed_utc=first_observed,
        last_observed_utc=last_observed,
    )


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


def assess_symbol_eligibility(
    dataset: pd.DataFrame,
    *,
    symbol: str,
    config: DailySvmGridSearchConfig,
    feature_columns: Sequence[str] = ACTIVE_FEATURES,
) -> pd.DataFrame:
    """Return one auditable eligibility row per symbol-target-window search."""
    rows: list[dict[str, object]] = []
    excluded = symbol in config.excluded_symbols
    for target in config.targets:
        for window_size in config.training_window_sizes:
            required = [*feature_columns, target]
            missing_columns = sorted(set(required).difference(dataset.columns))
            complete = (
                dataset.iloc[0:0]
                if missing_columns
                else dataset.loc[:, required].dropna()
            )
            reasons: list[str] = []
            fold_counts: list[dict[str, int]] = []
            if excluded:
                reasons.append("explicit_symbol_exclusion")
            if missing_columns:
                reasons.append("missing_required_columns")
            if len(complete) < config.minimum_complete_rows:
                reasons.append("insufficient_complete_labeled_rows")
            if not missing_columns and len(complete) >= config.minimum_complete_rows:
                for fold_index, (train, _) in enumerate(
                    temporal_splits(len(complete), config, window_size)
                ):
                    labels = complete[target].iloc[train].astype("int64")
                    negative = int((labels == 0).sum())
                    positive = int((labels == 1).sum())
                    fold_counts.append(
                        {
                            "fold": fold_index,
                            "negative": negative,
                            "positive": positive,
                        }
                    )
                    if labels.nunique() < 2:
                        reasons.append(f"single_class_training_fold_{fold_index}")
            reasons = list(dict.fromkeys(reasons))
            rows.append(
                {
                    "symbol": symbol,
                    "target": target,
                    "window_size": window_size,
                    "status": "eligible" if not reasons else "ineligible",
                    "reason": "|".join(reasons),
                    "complete_labeled_rows": len(complete),
                    "negative_count": int((complete[target] == 0).sum())
                    if target in complete
                    else 0,
                    "positive_count": int((complete[target] == 1).sum())
                    if target in complete
                    else 0,
                    "first_feature_time_utc": complete.index.min()
                    if not complete.empty
                    else pd.NaT,
                    "last_feature_time_utc": complete.index.max()
                    if not complete.empty
                        else pd.NaT,
                    "first_observed_utc": dataset.attrs.get(
                        "first_observed_utc", pd.NaT
                    ),
                    "last_observed_utc": dataset.attrs.get(
                        "last_observed_utc", pd.NaT
                    ),
                    "observed_feature_rows": int(
                        len(dataset)
                        - dataset.get(
                            "feature_is_imputed",
                            pd.Series(False, index=dataset.index),
                        ).fillna(False).sum()
                    ),
                    "feature_imputed_rows": int(
                        dataset.get(
                            "feature_is_imputed",
                            pd.Series(False, index=dataset.index),
                        ).fillna(False).sum()
                    ),
                    "target_imputed_rows": int(
                        dataset.get(
                            "target_is_imputed",
                            pd.Series(False, index=dataset.index),
                        ).fillna(False).sum()
                    ),
                    "training_fold_class_counts": json.dumps(
                        fold_counts, separators=(",", ":")
                    ),
                    "final_test_eligibility_status": "not_evaluated_development_only",
                    "first_permitted_final_test_feature_utc": pd.NaT,
                    "last_permitted_final_test_feature_utc": pd.NaT,
                }
            )
    return pd.DataFrame(rows)


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
        "accuracy": float(accuracy_score(true, predicted)),
        "precision": float(precision_score(true, predicted, zero_division=0)),
        "recall": float(recall_score(true, predicted, zero_division=0)),
        "f1": float(f1_score(true, predicted, zero_division=0)),
        "balanced_accuracy": balanced_accuracy,
        "roc_auc": roc_auc,
        "average_precision": average_precision,
        "metric_diagnostic": "|".join(diagnostics),
    }


def _parameter_values(parameters: Mapping[str, object]) -> dict[str, object]:
    return {column: parameters.get(column, pd.NA) for column in PARAMETER_COLUMNS}


def _aggregate_candidate_results(fold_results: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_columns = ["symbol", "target", "window_size", "candidate_order"]
    for keys, group in fold_results.groupby(group_columns, sort=False, dropna=False):
        symbol, target, window_size, candidate_order = keys
        first = group.iloc[0]
        row: dict[str, object] = {
            "symbol": symbol,
            "target": target,
            "window_size": int(window_size),
            "candidate_order": int(candidate_order),
            **{column: first[column] for column in PARAMETER_COLUMNS},
            "successful_fold_count": int((group["status"] == "ok").sum()),
            "failed_fold_count": int((group["status"] != "ok").sum()),
        }
        for metric in (
            "accuracy",
            "precision",
            "recall",
            "f1",
            "balanced_accuracy",
            "roc_auc",
            "average_precision",
        ):
            row[f"mean_{metric}"] = float(group[metric].mean())
        row["f1_standard_deviation"] = float(group["f1"].std(ddof=0))
        row["mean_fit_seconds"] = float(group["fit_seconds"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def select_best_candidate(
    candidates: pd.DataFrame, *, tolerance: float
) -> pd.Series:
    """Select one candidate using the approved deterministic tie-break rule."""
    ranked = rank_candidates(candidates, tolerance=tolerance)
    return ranked.loc[ranked["selection_rank"] == 1].iloc[0]


def rank_candidates(candidates: pd.DataFrame, *, tolerance: float) -> pd.DataFrame:
    """Rank candidates with F1 tolerance and the approved secondary ordering."""
    required = {
        "mean_f1",
        "mean_precision",
        "f1_standard_deviation",
        "mean_roc_auc",
        "kernel",
        "C",
        "candidate_order",
        "failed_fold_count",
    }
    missing = required.difference(candidates.columns)
    if missing:
        raise ValueError(f"Candidate table is missing columns: {sorted(missing)}.")
    valid = candidates.loc[
        (candidates["failed_fold_count"] == 0) & candidates["mean_f1"].notna()
    ].copy()
    if valid.empty:
        raise ValueError("No candidate completed every temporal fold.")
    kernel_order = {"linear": 0, "rbf": 1, "poly": 2}
    ranked_indexes: list[object] = []
    remaining = valid.copy()
    while not remaining.empty:
        best_f1 = float(remaining["mean_f1"].max())
        tied = remaining.loc[remaining["mean_f1"] >= best_f1 - tolerance].copy()
        tied["_precision"] = tied["mean_precision"].fillna(float("-inf"))
        tied["_f1_std"] = tied["f1_standard_deviation"].fillna(float("inf"))
        tied["_roc_auc"] = tied["mean_roc_auc"].fillna(float("-inf"))
        tied["_kernel"] = tied["kernel"].map(kernel_order).fillna(len(kernel_order))
        tied = tied.sort_values(
            [
                "_precision",
                "_f1_std",
                "_roc_auc",
                "_kernel",
                "C",
                "candidate_order",
            ],
            ascending=[False, True, False, True, True, True],
            kind="stable",
        )
        ranked_indexes.extend(tied.index)
        remaining = remaining.drop(index=tied.index)

    invalid = candidates.drop(index=valid.index).sort_values(
        "candidate_order", kind="stable"
    )
    ranked_indexes.extend(invalid.index)
    ranked = candidates.loc[ranked_indexes].copy()
    ranked.insert(4, "selection_rank", range(1, len(ranked) + 1))
    return ranked


def run_temporal_grid_search(
    dataset: pd.DataFrame,
    *,
    symbol: str,
    config: DailySvmGridSearchConfig,
    selection_config: DailyFeatureSelectionConfig,
    feature_columns: Sequence[str] = ACTIVE_FEATURES,
) -> DailySvmGridSearchResult:
    """Evaluate all eligible symbol-target-window candidates on temporal folds."""
    feature_columns = tuple(str(value) for value in feature_columns)
    eligibility = assess_symbol_eligibility(
        dataset,
        symbol=symbol,
        config=config,
        feature_columns=feature_columns,
    )
    candidates = expand_parameter_grid(config.parameter_grid)
    fold_rows: list[dict[str, object]] = []

    for eligibility_row in eligibility.itertuples(index=False):
        if eligibility_row.status != "eligible":
            continue
        target = str(eligibility_row.target)
        window_size = int(eligibility_row.window_size)
        complete = dataset.loc[:, [*feature_columns, target]].dropna()
        features = complete.loc[:, feature_columns].astype("float64")
        labels = complete[target].astype("int64")

        for fold_index, (train_positions, validation_positions) in enumerate(
            temporal_splits(len(complete), config, window_size)
        ):
            training_features = features.iloc[train_positions]
            validation_features = features.iloc[validation_positions]
            training_labels = labels.iloc[train_positions]
            validation_labels = labels.iloc[validation_positions]
            selector = DailyFeatureSelector(
                variance_threshold=selection_config.variance_threshold,
                correlation_threshold=selection_config.correlation_threshold,
            )
            selected_training = selector.fit_transform(training_features)
            selected_validation = selector.transform(validation_features)
            scaler = StandardScaler()
            scaled_training = scaler.fit_transform(selected_training)
            scaled_validation = scaler.transform(selected_validation)

            for candidate_order, parameters in enumerate(candidates):
                row: dict[str, object] = {
                    "symbol": symbol,
                    "target": target,
                    "window_size": window_size,
                    "candidate_order": candidate_order,
                    "fold": fold_index,
                    **_parameter_values(parameters),
                    "training_start_utc": training_features.index[0],
                    "training_end_utc": training_features.index[-1],
                    "validation_start_utc": validation_features.index[0],
                    "validation_end_utc": validation_features.index[-1],
                    "training_negative": int((training_labels == 0).sum()),
                    "training_positive": int((training_labels == 1).sum()),
                    "validation_negative": int((validation_labels == 0).sum()),
                    "validation_positive": int((validation_labels == 1).sum()),
                    "selected_feature_count": len(selector.selected_features_),
                    "selected_features": "|".join(selector.selected_features_),
                }
                started = perf_counter()
                try:
                    estimator = SVC(**parameters)
                    estimator.fit(scaled_training, training_labels)
                    prediction = estimator.predict(scaled_validation)
                    scores = estimator.decision_function(scaled_validation)
                    row.update(
                        calculate_classification_metrics(
                            validation_labels.to_numpy(), prediction, scores
                        )
                    )
                    row["status"] = "ok"
                    row["error"] = ""
                except Exception as error:  # persisted for candidate audit
                    row.update(
                        {
                            metric: float("nan")
                            for metric in (
                                "accuracy",
                                "precision",
                                "recall",
                                "f1",
                                "balanced_accuracy",
                                "roc_auc",
                                "average_precision",
                            )
                        }
                    )
                    row["metric_diagnostic"] = ""
                    row["status"] = "fit_error"
                    row["error"] = f"{type(error).__name__}: {error}"
                row["fit_seconds"] = perf_counter() - started
                fold_rows.append(row)

    fold_results = pd.DataFrame(fold_rows)
    if fold_results.empty:
        return DailySvmGridSearchResult(
            eligibility=eligibility,
            fold_results=fold_results,
            candidate_results=pd.DataFrame(),
            selected_configurations=pd.DataFrame(),
        )

    aggregate_results = _aggregate_candidate_results(fold_results)
    ranked_groups: list[pd.DataFrame] = []
    selected_rows: list[dict[str, object]] = []
    for _, group in aggregate_results.groupby(
        ["symbol", "target", "window_size"], sort=True
    ):
        ranked = rank_candidates(group, tolerance=config.tie_tolerance)
        ranked_groups.append(ranked)
        best = ranked.loc[ranked["selection_rank"] == 1].iloc[0]
        selected_rows.append(best.to_dict())
    candidate_results = pd.concat(ranked_groups, ignore_index=True)
    selected = pd.DataFrame(selected_rows).sort_values(
        ["symbol", "target", "window_size"]
    ).reset_index(drop=True)
    return DailySvmGridSearchResult(
        eligibility=eligibility,
        fold_results=fold_results,
        candidate_results=candidate_results,
        selected_configurations=selected,
    )


def _git_value(arguments: Sequence[str]) -> str | None:
    completed = subprocess.run(
        ["git", *arguments], check=False, capture_output=True, text=True
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _package_version(distribution: str) -> str | None:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


def _write_csv(frame: pd.DataFrame, path: Path) -> str:
    frame.to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%S%z")
    return sha256(path.read_bytes()).hexdigest()


def write_grid_search_outputs(
    config: DailySvmGridSearchConfig,
    source: SymbolDevelopmentDataset,
    result: DailySvmGridSearchResult,
) -> tuple[Path, ...]:
    """Persist grid evidence and a reproducibility manifest outside Git."""
    output_directory = config.output_directory / source.symbol
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "eligibility": output_directory / "asset_eligibility.csv",
        "fold_results": output_directory / "fold_results.csv.gz",
        "candidate_results": output_directory / "candidate_results.csv.gz",
        "selected_configurations": output_directory / "selected_configurations.csv",
    }
    checksums = {
        name: _write_csv(getattr(result, name), path)
        for name, path in paths.items()
    }
    snapshot_path = output_directory / "configuration_snapshot.json"
    snapshot_path.write_text(
        json.dumps(_load_json(config.config_path), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksums["configuration_snapshot"] = sha256(snapshot_path.read_bytes()).hexdigest()
    metadata_path = output_directory / "run_metadata.json"
    metadata = {
        "experiment_id": config.experiment_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "code_revision": _git_value(("rev-parse", "HEAD")),
        "working_tree_dirty": bool(_git_value(("status", "--porcelain"))),
        "configuration": str(config.config_path),
        "configuration_sha256": sha256(config.config_path.read_bytes()).hexdigest(),
        "symbol": source.symbol,
        "raw_data_path": str(source.raw_path),
        "raw_data_sha256": source.raw_sha256,
        "development_start_utc": config.development_start_utc.isoformat(),
        "development_end_utc": config.development_end_utc.isoformat(),
        "latest_source_observation_used_utc": (
            config.development_end_utc + DAY
        ).isoformat(),
        "final_test_feature_rows_used": False,
        "random_behavior": False,
        "random_seed": None,
        "candidate_count_per_search": config.candidate_count,
        "eligible_search_count": int(
            (result.eligibility["status"] == "eligible").sum()
        ),
        "fold_result_count": len(result.fold_results),
        "selected_configuration_count": len(result.selected_configurations),
        "input_features": list(ACTIVE_FEATURES),
        "scaler_parameters": StandardScaler().get_params(deep=False),
        "svc_default_parameters": SVC().get_params(deep=False),
        "artifact_sha256": checksums,
        "package_versions": {
            distribution: _package_version(distribution)
            for distribution in (
                "pandas",
                "numpy",
                "scikit-learn",
                "feature-engine",
                "TA-Lib",
            )
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return (*paths.values(), snapshot_path, metadata_path)
