"""Explicit calculations over previously loaded inputs; no output I/O."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tcc_crypto.analysis.correlation import calculate_correlations
from tcc_crypto.analysis.descriptive import calculate_descriptive
from tcc_crypto.analysis.feature_selection import (
    calculate_feature_tables,
    calculate_selection,
)
from tcc_crypto.analysis.future_high import analyze_future_high
from tcc_crypto.analysis.market_exploration import calculate_market_exploration
from tcc_crypto.data.request_records import SavedRecords
from tcc_crypto.workflows.exploration_context import API_ANALYSES, ExplorationContext
from tcc_crypto.workflows.exploration_inputs import ExplorationInputs


@dataclass
class ExplorationResult:
    tables: dict[str, pd.DataFrame]


def calculate(
    context: ExplorationContext, inputs: ExplorationInputs
) -> ExplorationResult:
    """Build tables only. Feature selection has an additional inspectable intermediate API."""
    name = context.analysis
    config = context.settings
    if name in API_ANALYSES:
        return ExplorationResult(
            calculate_market_exploration(
                name,
                {**inputs.raw, "records": SavedRecords(inputs.raw["records"])},
                start_utc=config.start_utc,
                source_url=config.base_url + "/api/v3/klines",
            )
        )
    if name in ("open-correlation", "return-correlation"):
        return ExplorationResult(
            {
                "source_summary": inputs.values["source_summary"],
                **calculate_correlations(
                    inputs.values["series"], config.reference_symbol
                ),
            }
        )
    if name == "feature-selection":
        tables = calculate_feature_tables(inputs.values, inputs.diagnostics)
        return ExplorationResult(calculate_selection(tables, config))
    if name == "future-high":
        return ExplorationResult(analyze_future_high(inputs.values, config))
    return ExplorationResult(calculate_descriptive(name, inputs.values, config))


def inspect_features(inputs: ExplorationInputs) -> ExplorationResult:
    """Calculate full-history features before the expensive rolling-selection stage."""
    return ExplorationResult(
        calculate_feature_tables(inputs.values, inputs.diagnostics)
    )


def select_features(
    context: ExplorationContext, features: ExplorationResult
) -> ExplorationResult:
    return ExplorationResult(calculate_selection(features.tables, context.settings))
