"""Notebook-facing inspection functions sharing the official daily implementation."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from tcc_crypto.data.exploratory import load_daily_price_volume
from tcc_crypto.features.catalog import ACTIVE_FEATURES, feature_definitions
from tcc_crypto.modeling.config import expand_parameter_grid
from tcc_crypto.modeling.eligibility import assess_symbol_eligibility
from tcc_crypto.modeling.grid_search import (
    DailySvmGridSearchResult,
    evaluate_candidate,
    run_temporal_grid_search,
)
from tcc_crypto.modeling.pilot import (
    DailySvmPilotResult,
    fit_prediction,
    run_default_svc_rolling_pilot,
)
from tcc_crypto.modeling.preprocessing import PreparedWindow, prepare_window
from tcc_crypto.modeling.splits import temporal_splits
from tcc_crypto.reporting.tables import read_table
from tcc_crypto.reporting.workbooks import configuration_table
from tcc_crypto.visualization.modeling import target_balance
from tcc_crypto.workflows import daily_data, svm
from tcc_crypto.workflows.context import DailyContext
from tcc_crypto.workflows.context import load_context as load_context


def configuration(context: DailyContext) -> pd.DataFrame:
    return configuration_table(asdict(context.model))


def paths(context: DailyContext) -> pd.DataFrame:
    return configuration_table(context.paths.inventory(context.kind))


def definitions() -> pd.DataFrame:
    return pd.DataFrame(feature_definitions())


def raw_observations(context: DailyContext) -> pd.DataFrame:
    return load_daily_price_volume(daily_data.raw_source(context))


def prepare_stage(
    context: DailyContext, stage: str, *, overwrite: bool = False
) -> pd.DataFrame:
    {
        "aligned": daily_data.align,
        "features": daily_data.features,
        "targets": daily_data.targets,
        "dataset": daily_data.dataset,
    }[stage](context, overwrite=overwrite)
    return daily_data.read_stage(context, stage)


def stage_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return configuration_table(
        {
            "Rows": len(frame),
            "Columns": len(frame.columns),
            "First timestamp UTC": frame.index.min(),
            "Last timestamp UTC": frame.index.max(),
            "Missing cells": int(frame.isna().sum().sum()),
            "Imputed rows": int(frame["is_imputed"].sum())
            if "is_imputed" in frame
            else None,
        }
    )


def preview(frame: pd.DataFrame, *, rows: int = 10) -> pd.DataFrame:
    return frame.head(rows)


def balance(context: DailyContext) -> pd.DataFrame:
    return target_balance(daily_data.read_stage(context, "dataset"))


def eligibility(context: DailyContext) -> pd.DataFrame:
    return assess_symbol_eligibility(
        daily_data.read_stage(context, "dataset"),
        symbol=context.data.symbol,
        config=context.model,
    )


def candidates(context: DailyContext) -> pd.DataFrame:
    return pd.DataFrame(expand_parameter_grid(context.model.parameter_grid))


def split_boundaries(
    context: DailyContext,
    *,
    target: str = "target_2pct",
    window_size: int | None = None,
) -> pd.DataFrame:
    window_size = (
        window_size or context.features.feature_selection.training_window_sizes[0]
    )
    data = (
        daily_data.read_stage(context, "dataset")
        .loc[:, [*ACTIVE_FEATURES, target]]
        .dropna()
    )
    rows = []
    for fold, (train, validation) in enumerate(
        temporal_splits(len(data), context.model, window_size)
    ):
        rows.append(
            {
                "fold": fold,
                "training_start_utc": data.index[train[0]],
                "training_end_utc": data.index[train[-1]],
                "training_rows": len(train),
                "validation_start_utc": data.index[validation[0]],
                "validation_end_utc": data.index[validation[-1]],
                "validation_rows": len(validation),
            }
        )
    return pd.DataFrame(rows)


@dataclass
class WindowInspection:
    prepared: PreparedWindow
    training_labels: pd.Series
    evaluation_labels: pd.Series
    summary: pd.DataFrame
    scaling: pd.DataFrame


def inspect_window(
    context: DailyContext,
    *,
    target: str = "target_2pct",
    window_size: int | None = None,
) -> WindowInspection:
    window_size = (
        window_size or context.features.feature_selection.training_window_sizes[0]
    )
    data = (
        daily_data.read_stage(context, "dataset")
        .loc[:, [*ACTIVE_FEATURES, target]]
        .dropna()
    )
    if context.profile == "pilot":
        train = list(range(window_size))
        evaluation = [window_size]
        if len(data) <= window_size:
            raise ValueError("Dataset is too short for this pilot window.")
    else:
        train, evaluation = temporal_splits(len(data), context.model, window_size)[0]
    training = data.iloc[train]
    future = data.iloc[evaluation]
    prepared = prepare_window(
        training.loc[:, ACTIVE_FEATURES],
        future.loc[:, ACTIVE_FEATURES],
        context.features.feature_selection,
    )
    scaled = pd.DataFrame(
        prepared.training, columns=prepared.selector.selected_features_
    )
    summary = configuration_table(
        {
            "Target": target,
            "Training start UTC": training.index[0],
            "Training end UTC": training.index[-1],
            "Evaluation start UTC": future.index[0],
            "Evaluation end UTC": future.index[-1],
            "Training rows": len(training),
            "Evaluation rows": len(future),
            "Selected features": prepared.selector.selected_features_,
        }
    )
    scaling = pd.DataFrame(
        {
            "training_mean_after_scaling": scaled.mean(),
            "training_std_after_scaling": scaled.std(ddof=0),
        }
    )
    return WindowInspection(
        prepared,
        training[target].astype("int64"),
        future[target].astype("int64"),
        summary,
        scaling,
    )


def inspect_prediction(window: WindowInspection) -> pd.DataFrame:
    if len(window.evaluation_labels) != 1:
        raise ValueError("A pilot prediction requires one future observation.")
    return configuration_table(
        {
            **fit_prediction(
                window.training_labels,
                window.prepared.training,
                window.prepared.evaluation,
            ),
            "actual": int(window.evaluation_labels.iloc[0]),
        }
    )


def compare_kernel_candidates(
    context: DailyContext, window: WindowInspection
) -> pd.DataFrame:
    rows = []
    seen = set()
    for parameters in expand_parameter_grid(context.model.parameter_grid):
        if parameters["kernel"] in seen:
            continue
        seen.add(parameters["kernel"])
        rows.append(
            {
                **parameters,
                **evaluate_candidate(
                    parameters,
                    window.training_labels,
                    window.evaluation_labels,
                    window.prepared.training,
                    window.prepared.evaluation,
                ),
            }
        )
    return pd.DataFrame(rows)


def calculate_model(context: DailyContext):
    data = daily_data.read_stage(context, "dataset")
    if context.profile == "pilot":
        return run_default_svc_rolling_pilot(
            data, selection_config=context.features.feature_selection
        )
    return run_temporal_grid_search(
        data,
        symbol=context.data.symbol,
        config=context.model,
        selection_config=context.features.feature_selection,
    )


def load_model(context: DailyContext):
    for stage in daily_data.STAGES:
        daily_data.read_stage(context, stage)
    tables = {
        name: read_table(path, context=context.signature(), stage=context.kind)
        for name, path in svm.result_table_paths(context).items()
    }
    return (
        DailySvmPilotResult(**tables)
        if context.profile == "pilot"
        else DailySvmGridSearchResult(**tables)
    )


def result_table(result, name: str, *, rows: int | None = None) -> pd.DataFrame:
    table = getattr(result, name)
    return table if rows is None else table.head(rows)


def top_candidates(result: DailySvmGridSearchResult, *, count: int = 3) -> pd.DataFrame:
    if result.candidate_results.empty:
        return result.candidate_results
    return (
        result.candidate_results.sort_values(
            ["target", "window_size", "selection_rank"]
        )
        .groupby(["target", "window_size"])
        .head(count)
    )
