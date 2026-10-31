"""Compose descriptive tables while preserving distinct field and unit conventions."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.analysis import daily_descriptive, hourly_activity, hourly_prices
from tcc_crypto.analysis.daily_descriptive_config import DailyPriceVolumeAnalysisConfig
from tcc_crypto.analysis.hourly_activity_config import MarketActivityAnalysisConfig
from tcc_crypto.analysis.hourly_prices_config import DescriptiveAnalysisConfig

DescriptiveSettings = (
    DescriptiveAnalysisConfig
    | MarketActivityAnalysisConfig
    | DailyPriceVolumeAnalysisConfig
)


def calculate_descriptive(
    name: str, values_by_symbol: dict[str, pd.DataFrame], config: DescriptiveSettings
) -> dict[str, pd.DataFrame]:
    statistics = []
    coverage = []
    extrema = []
    semesters = []
    for symbol, values in values_by_symbol.items():
        if name == "hourly-prices":
            statistics.append(
                hourly_prices.describe_price_levels(
                    symbol, values, ddof=config.standard_deviation_ddof
                )
            )
            coverage.append(hourly_prices.describe_coverage(symbol, values))
            extrema.append(hourly_prices.describe_extremes(symbol, values))
        elif name == "hourly-activity":
            statistics.append(
                hourly_activity.describe_market_activity(
                    symbol, values, ddof=config.standard_deviation_ddof
                )
            )
            coverage.append(hourly_prices.describe_coverage(symbol, values))
            extrema.append(hourly_activity.describe_activity_extremes(symbol, values))
        else:
            statistics.append(
                daily_descriptive.describe_statistics(
                    values, ddof=config.standard_deviation_ddof
                ).assign(Symbol=symbol)
            )
            coverage.append(daily_descriptive.describe_coverage(symbol, values))
            extrema.append(daily_descriptive.describe_extrema(symbol, values))
            semesters.append(
                daily_descriptive.describe_semesters(
                    values,
                    analysis_start_utc=config.analysis_start_utc,
                    analysis_end_utc=config.analysis_end_utc,
                    ddof=config.standard_deviation_ddof,
                ).assign(Symbol=symbol)
            )
    tables = {
        "statistics": pd.concat(statistics, ignore_index=True),
        "coverage": pd.DataFrame(coverage),
        "extrema": pd.concat(extrema, ignore_index=True),
    }
    if semesters:
        tables["semesters"] = pd.concat(semesters, ignore_index=True)
    return tables
