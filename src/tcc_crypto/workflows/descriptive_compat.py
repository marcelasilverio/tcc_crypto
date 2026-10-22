"""Compatibility entrypoints backed by the independently executable workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from tcc_crypto.reporting.workbooks import write_workbook
from tcc_crypto.visualization.exploratory import hourly_symbol_figures
from tcc_crypto.workflows import exploration as workflow


@dataclass(frozen=True)
class AnalysisArtifacts:
    """Paths and in-memory tables produced by the analysis."""

    summary: pd.DataFrame
    coverage: pd.DataFrame
    extremes: pd.DataFrame
    summary_csv: Path
    coverage_csv: Path
    extremes_csv: Path
    workbook: Path
    overview_figure: Path
    individual_figure_directory: Path


@dataclass(frozen=True)
class MarketActivityArtifacts:
    """Paths and in-memory tables produced by the activity analysis."""

    summary: pd.DataFrame
    coverage: pd.DataFrame
    extremes: pd.DataFrame
    summary_csv: Path
    coverage_csv: Path
    extremes_csv: Path
    quote_volume_overview: Path
    trade_count_overview: Path
    individual_figure_directory: Path


@dataclass(frozen=True)
class DailySmallMultipleArtifacts:
    """Paths to the two cross-pair daily small-multiple figures."""

    natural_log_open_close_figure: Path
    quote_volume_figure: Path


def run_descriptive_analysis(
    config_path: Path, *, repository_root: Path
) -> AnalysisArtifacts:
    context = workflow.open_exploration(
        "hourly-prices", config_path=config_path, root=repository_root
    )
    result = workflow.run(context)
    return AnalysisArtifacts(
        result.tables["statistics"],
        result.tables["coverage"],
        result.tables["extrema"],
        context.paths.table("statistics"),
        context.paths.table("coverage"),
        context.paths.table("extrema"),
        context.paths.workbooks / "analysis.xlsx",
        context.paths.outputs / "figures/prices.png",
        context.paths.outputs / "figures/by_symbol",
    )


def run_market_activity_analysis(
    config_path: Path, *, repository_root: Path
) -> MarketActivityArtifacts:
    context = workflow.open_exploration(
        "hourly-activity", config_path=config_path, root=repository_root
    )
    result = workflow.run(context)
    return MarketActivityArtifacts(
        result.tables["statistics"],
        result.tables["coverage"],
        result.tables["extrema"],
        context.paths.table("statistics"),
        context.paths.table("coverage"),
        context.paths.table("extrema"),
        context.paths.outputs / "figures/quote_asset_volume.png",
        context.paths.outputs / "figures/number_of_trades.png",
        context.paths.outputs / "figures/by_symbol",
    )


def create_daily_small_multiple_figures(
    config_path: Path, *, repository_root: Path
) -> DailySmallMultipleArtifacts:
    context = workflow.open_exploration(
        "daily-descriptive", config_path=config_path, root=repository_root
    )
    inputs = workflow.load_inputs(context)
    figures = workflow.build_figures(context, inputs, workflow.ExplorationResult({}))
    from tcc_crypto.visualization.exploratory import save_figures

    paths = save_figures(figures, context.paths.outputs / "figures")
    for figure in figures.values():
        plt.close(figure)
    return DailySmallMultipleArtifacts(
        paths["daily_ln_open_close"], paths["daily_quote_volume"]
    )


def plot_symbol_open_close(
    symbol: str, prices: pd.DataFrame, output_path: Path
) -> None:
    figure = hourly_symbol_figures({symbol: prices}, activity=False)[symbol]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path)
    plt.close(figure)


def plot_symbol_activity(
    symbol: str, activity: pd.DataFrame, output_path: Path
) -> None:
    figure = hourly_symbol_figures({symbol: activity}, activity=True)[symbol]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path)
    plt.close(figure)


def _write_workbook(path, summary, coverage, extremes, config):
    write_workbook(
        path,
        {
            "Price Statistics": summary,
            "Coverage": coverage,
            "Extrema": extremes,
            "Definitions": pd.DataFrame({"Definition": [config.kurtosis_definition]}),
        },
    )
