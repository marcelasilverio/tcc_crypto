"""Dispatch figure construction separately from calculation and persistence."""

from __future__ import annotations

import matplotlib.pyplot as plt

from tcc_crypto.visualization.daily_descriptive import daily_small_multiples
from tcc_crypto.visualization.exploratory import (
    correlation_heatmap,
    feature_frequency_heatmap,
    hourly_overviews,
    hourly_symbol_figures,
    save_figures,
)
from tcc_crypto.workflows.exploration_calculations import ExplorationResult
from tcc_crypto.workflows.exploration_context import ExplorationContext
from tcc_crypto.workflows.exploration_inputs import ExplorationInputs

PLOTTABLE = (
    "hourly-prices",
    "hourly-activity",
    "daily-descriptive",
    "open-correlation",
    "return-correlation",
    "feature-selection",
)


def build_figures(
    context: ExplorationContext,
    inputs: ExplorationInputs,
    result: ExplorationResult,
    *,
    individual: bool = False,
) -> dict[str, plt.Figure]:
    if context.analysis == "daily-descriptive":
        return daily_small_multiples(inputs.values, context.settings)
    if context.analysis in ("hourly-prices", "hourly-activity"):
        function = hourly_symbol_figures if individual else hourly_overviews
        return function(inputs.values, activity=context.analysis == "hourly-activity")
    if context.analysis in ("open-correlation", "return-correlation"):
        label = (
            "opening-price levels"
            if context.analysis == "open-correlation"
            else "high-to-open appreciation"
        )
        return {
            "correlation": correlation_heatmap(
                result.tables["correlations"],
                title=f"Hourly {label}: pairwise Pearson correlation\nThrough {context.settings.end_utc.isoformat()}",
            )
        }
    if (
        context.analysis == "feature-selection"
        and not result.tables["selection_frequency"].empty
    ):
        return {
            "selection_frequency": feature_frequency_heatmap(
                result.tables["selection_frequency"]
            )
        }
    return {}


def plot_saved(
    context: ExplorationContext,
    inputs: ExplorationInputs,
    result: ExplorationResult,
    *,
    overwrite: bool = False,
) -> dict:
    figures = build_figures(context, inputs, result)
    paths = save_figures(
        figures, context.paths.outputs / "figures", overwrite=overwrite
    )
    for figure in figures.values():
        plt.close(figure)
    if context.analysis in ("hourly-prices", "hourly-activity"):
        figures = build_figures(context, inputs, result, individual=True)
        paths.update(
            save_figures(
                figures,
                context.paths.outputs / "figures" / "by_symbol",
                overwrite=overwrite,
            )
        )
        for figure in figures.values():
            plt.close(figure)
    return paths
