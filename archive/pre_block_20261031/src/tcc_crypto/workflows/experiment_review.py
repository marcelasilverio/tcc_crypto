"""Read-only notebook views and explicit reconstruction of selected training fits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd

from tcc_crypto.analysis.experiment_results import (
    asset_overview,
    development_vs_final,
    selected_folds,
)
from tcc_crypto.analysis.experiment_results import (
    phase_definitions as phase_definitions,
)
from tcc_crypto.modeling.training_review import reconstruct_training_metrics
from tcc_crypto.paths import (
    FINAL_EVALUATION_CONFIG_PATH,
    SVM_WORKBOOK_NAME,
    metadata_path,
)
from tcc_crypto.reporting.tables import read_table, write_table
from tcc_crypto.workflows.context import load_context
from tcc_crypto.workflows.daily_data import read_stage
from tcc_crypto.workflows.final_evaluation import _inputs
from tcc_crypto.workflows.svm import result_table_paths


@dataclass(frozen=True)
class ExperimentReview:
    overview: pd.DataFrame
    comparison: pd.DataFrame
    eligibility: pd.DataFrame
    metrics: pd.DataFrame
    selected: pd.DataFrame
    artifacts: pd.DataFrame
    training: pd.DataFrame
    root: Path
    run_id: str | None = None


def _symbols(context, symbols: Sequence[str] | None) -> tuple[str, ...]:
    chosen = tuple(context.model.candidate_symbols if symbols is None else symbols)
    if (
        not chosen
        or len(chosen) != len(set(chosen))
        or set(chosen) - set(context.model.candidate_symbols)
    ):
        raise ValueError("Select unique configured symbols.")
    return chosen


def load_results(
    *,
    root: Path | None = None,
    symbols: Sequence[str] | None = None,
    run_id: str | None = None,
) -> ExperimentReview:
    """Validate saved tables and upstream checksums for every configured asset."""
    context = load_context("development", root=root, run_id=run_id)
    eligibility, metrics, selected, artifacts, training = [], [], [], [], []
    for symbol in _symbols(context, symbols):
        current = load_context(
            "development", root=context.root, symbol=symbol, run_id=run_id
        )
        _, paths, _, signature = _inputs(current, FINAL_EVALUATION_CONFIG_PATH)
        tables = paths.tables()
        for name, destination in (
            ("eligibility", eligibility),
            ("metrics", metrics),
            ("selected_configurations", selected),
        ):
            destination.append(
                read_table(tables[name], context=signature, stage="final-test")
            )
        training_path = paths.training_metrics
        if training_path.exists():
            training.append(
                read_table(
                    training_path, context=current.signature(), stage="training-review"
                )
            )
        grid = result_table_paths(current)
        artifacts.append(
            {
                "symbol": symbol,
                "grid_workbook": str(grid["eligibility"].parent / SVM_WORKBOOK_NAME),
                "final_workbook": str(paths.directory / SVM_WORKBOOK_NAME),
                "dated_predictions": str(tables["predictions"]),
                "final_metrics": str(tables["metrics"]),
            }
        )
    all_eligibility = pd.concat(eligibility, ignore_index=True)
    all_metrics = pd.concat(metrics, ignore_index=True)
    all_selected = pd.concat(selected, ignore_index=True)
    all_training = (
        pd.concat(training, ignore_index=True) if training else pd.DataFrame()
    )
    return ExperimentReview(
        asset_overview(all_eligibility, all_metrics),
        development_vs_final(all_selected, all_metrics, all_training),
        all_eligibility,
        all_metrics,
        all_selected,
        pd.DataFrame(artifacts),
        all_training,
        context.root,
        run_id,
    )


def _asset(report: ExperimentReview, symbol: str, table: str) -> pd.DataFrame:
    if symbol not in set(report.overview.symbol):
        raise ValueError(f"Unknown configured symbol: {symbol}")
    frame = getattr(report, table)
    if frame.empty:
        return frame.copy()
    return frame.loc[frame.symbol.eq(symbol)].reset_index(drop=True).copy()


def asset_comparison(report: ExperimentReview, symbol: str) -> pd.DataFrame:
    return _asset(report, symbol, "comparison")


def asset_metrics(report: ExperimentReview, symbol: str) -> pd.DataFrame:
    return _asset(report, symbol, "metrics")


def asset_eligibility(report: ExperimentReview, symbol: str) -> pd.DataFrame:
    return _asset(report, symbol, "eligibility")


def asset_parameters(report: ExperimentReview, symbol: str) -> pd.DataFrame:
    return _asset(report, symbol, "selected").reindex(
        columns=[
            "target",
            "window_size",
            "candidate_order",
            "kernel",
            "C",
            "gamma",
            "degree",
            "coef0",
            "class_weight",
            "successful_fold_count",
            "failed_fold_count",
            "frozen_parameters",
        ]
    )


def asset_folds(report: ExperimentReview, symbol: str) -> pd.DataFrame:
    context = load_context(
        "development", root=report.root, symbol=symbol, run_id=report.run_id
    )
    folds = read_table(
        result_table_paths(context)["fold_results"],
        context=context.signature(),
        stage="grid-search",
    )
    return selected_folds(folds, _asset(report, symbol, "selected"))


def asset_curves(report: ExperimentReview, symbol: str) -> dict[str, pd.DataFrame]:
    _asset(report, symbol, "overview")
    context = load_context(
        "development", root=report.root, symbol=symbol, run_id=report.run_id
    )
    _, paths, _, signature = _inputs(context, FINAL_EVALUATION_CONFIG_PATH)
    return {
        name: read_table(paths.tables()[name], context=signature, stage="final-test")
        for name in ("roc", "precision_recall")
    }


def reconstruct_in_sample(
    *,
    root: Path | None = None,
    symbols: Sequence[str] | None = None,
    run_id: str | None = None,
    overwrite: bool = False,
) -> pd.DataFrame:
    """Explicit one-time fitting operation; notebook reloads never call this.

    Existing compatible training artifacts are reused. Incompatible artifacts
    fail instead of being overwritten; original model outputs are immutable.
    """
    context = load_context("development", root=root, run_id=run_id)
    results = []
    for symbol in _symbols(context, symbols):
        current = load_context(
            "development", root=context.root, symbol=symbol, run_id=run_id
        )
        _, paths, _, signature = _inputs(current, FINAL_EVALUATION_CONFIG_PATH)
        selected_path = paths.tables()["selected_configurations"]
        selected = read_table(selected_path, context=signature, stage="final-test")
        if selected.empty:
            continue
        destination = paths.training_metrics
        if destination.exists() and not overwrite:
            results.append(
                read_table(
                    destination, context=current.signature(), stage="training-review"
                )
            )
            continue
        dataset = read_stage(current, "dataset")
        folds_path = result_table_paths(current)["fold_results"]
        folds = read_table(folds_path, context=current.signature(), stage="grid-search")
        calculated = reconstruct_training_metrics(
            dataset,
            selected,
            folds,
            config=current.model,
            selection_config=current.features.feature_selection,
        )
        sources = [
            selected_path,
            folds_path,
            current.paths.table("dataset"),
            *current.configuration_files,
        ]
        sources += [metadata_path(path) for path in sources[:3]]
        write_table(
            calculated,
            destination,
            root=current.root,
            context=current.signature(),
            sources=sources,
            overwrite=overwrite,
        )
        results.append(calculated)
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def asset_training(report: ExperimentReview, symbol: str) -> pd.DataFrame:
    return _asset(report, symbol, "training")
