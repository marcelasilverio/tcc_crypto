"""Public step-by-step exploratory workflow used by commands and notebooks."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.paths import ANALYSIS_INPUTS_NAME, ANALYSIS_RESULTS_NAME
from tcc_crypto.reporting.exploration import export_workbooks
from tcc_crypto.reporting.tables import ensure_writable
from tcc_crypto.workflows.exploration_calculations import ExplorationResult, calculate
from tcc_crypto.workflows.exploration_calculations import (
    inspect_features as inspect_features,
)
from tcc_crypto.workflows.exploration_calculations import (
    select_features as select_features,
)
from tcc_crypto.workflows.exploration_context import API_ANALYSES, ExplorationContext
from tcc_crypto.workflows.exploration_context import (
    open_exploration as open_exploration,
)
from tcc_crypto.workflows.exploration_figures import build_figures as build_figures
from tcc_crypto.workflows.exploration_figures import plot_saved
from tcc_crypto.workflows.exploration_inputs import (
    ExplorationInputs,
    collect_inputs,
    load_inputs,
)
from tcc_crypto.workflows.exploration_storage import load_results as load_results
from tcc_crypto.workflows.exploration_storage import (
    load_saved_inputs as load_saved_inputs,
)
from tcc_crypto.workflows.exploration_storage import save_inputs, save_results


def paths_table(context: ExplorationContext) -> pd.DataFrame:
    return (
        pd.Series(context.paths.inventory(), name="Resolved path")
        .rename_axis("Artifact")
        .to_frame()
    )


def input_diagnostics(inputs: ExplorationInputs) -> pd.DataFrame:
    if not inputs.diagnostics.empty:
        return inputs.diagnostics
    return pd.DataFrame(
        [
            {
                "Input": key,
                "Rows": len(frame),
                "First timestamp": str(frame.index.min()),
                "Last timestamp": str(frame.index.max()),
            }
            for key, frame in inputs.values.items()
        ]
    )


def table_preview(
    result: ExplorationResult, name: str, *, rows: int = 10
) -> pd.DataFrame:
    return result.tables[name].head(rows)


def figure_preview(figures: dict, name: str | None = None):
    return figures[name] if name else next(iter(figures.values()), None)


def run(
    context: ExplorationContext,
    *,
    overwrite: bool = False,
    requester=None,
    execution_time=None,
) -> ExplorationResult:
    if not overwrite:
        existing = [
            path
            for directory in (
                context.paths.tables,
                context.paths.workbooks,
                context.paths.outputs,
            )
            if directory.exists()
            for path in directory.rglob("*")
            if path.is_file()
        ]
        ensure_writable(existing, overwrite=False)
    ensure_writable(
        [
            context.paths.outputs / ANALYSIS_INPUTS_NAME,
            context.paths.outputs / ANALYSIS_RESULTS_NAME,
        ],
        overwrite=overwrite,
    )
    inputs = (
        collect_inputs(context, requester=requester, execution_time=execution_time)
        if context.analysis in API_ANALYSES
        else load_inputs(context)
    )
    save_inputs(context, inputs, overwrite=overwrite)
    result = calculate(context, inputs)
    save_results(context, result, overwrite=overwrite)
    plot_saved(context, inputs, result, overwrite=overwrite)
    export_workbooks(context, inputs, result, overwrite=overwrite)
    return result
