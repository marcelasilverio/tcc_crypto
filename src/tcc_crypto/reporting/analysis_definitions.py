"""Human-readable analysis conventions exported alongside exact Python tables."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from tcc_crypto.reporting.workbooks import configuration_table
from tcc_crypto.workflows.exploration_context import ExplorationContext
from tcc_crypto.workflows.exploration_inputs import ExplorationInputs


def analysis_definitions(
    context: ExplorationContext, inputs: ExplorationInputs
) -> pd.DataFrame:
    values = {
        "Analysis": context.paths.analysis_id,
        "Run": context.paths.run_id,
        "Timezone": "UTC",
        "Missing observations": "No interpolation, forward fill, backfill or pre-listing synthesis",
        "Interpretation": "Descriptive evidence only; not historical investability, causal evidence or realized portfolio returns",
    }
    if context.analysis in ("hourly-prices", "hourly-activity"):
        values.update(
            {
                "Standard deviation and variance": "Sample estimators with ddof=1",
                "Quartiles": "Linear interpolation at 25%, 50% and 75%",
                "Skewness and kurtosis": "Pandas sample skewness and Fisher excess kurtosis",
                "Coefficient of variation": "Hourly reports express standard deviation / mean as percent; field labels carry units",
            }
        )
    if context.analysis == "future-high":
        values["Outcome formula"] = (
            "D[h](t) = high[t+h] / open[t] - 1 on exact calendar dates; not available as a base-time feature"
        )
    if context.analysis in ("open-correlation", "return-correlation"):
        values["Correlation"] = (
            "Pairwise-complete Pearson correlation; paired-observation counts are reported"
        )
        values["Candidate universe"] = (
            "The approved initial 30 pairs, frozen independently of the 40-pair collection"
        )
    if inputs.raw:
        values["Collection cutoff UTC"] = inputs.raw["cutoff"]
        values["Collection execution UTC"] = inputs.raw["execution_time"]
        values["Catalog limitation"] = (
            "Current exchangeInfo response; not a complete historical symbol catalog"
        )
        if context.analysis == "annual-volume":
            values["Partial periods"] = (
                "Current UTC month is Partial month; current UTC year is Year-to-date"
            )
        if context.analysis == "trade-counts":
            values["Activity definition"] = (
                "Sum of number_of_trades from closed daily candles through the previous UTC day"
            )
    return pd.concat(
        [configuration_table(values), configuration_table(asdict(context.settings))],
        ignore_index=True,
    )
