"""Definitions exported with daily descriptive tables."""

from __future__ import annotations

from tcc_crypto.analysis.daily_descriptive_config import DailyPriceVolumeAnalysisConfig


def definition_rows(config: DailyPriceVolumeAnalysisConfig) -> list[dict[str, str]]:
    """Return concise workbook definitions and interpretation limits."""
    definitions = [
        ("Open", "First traded price recorded in the daily Binance Spot candle."),
        ("High", "Highest traded price recorded in the daily candle."),
        ("Low", "Lowest traded price recorded in the daily candle."),
        ("Close", "Last traded price recorded in the daily candle."),
        (
            "Quote asset volume",
            "Total exchange-reported daily trading volume expressed in USDT.",
        ),
        ("Observations", "Number of observed daily candles used in the calculation."),
        (
            "Missing values",
            "Observed rows with a missing analyzed value; source validation requires zero.",
        ),
        (
            "Missing daily openings",
            "Expected UTC dates absent inside the observed span; gaps are not filled.",
        ),
        (
            "Zero observations",
            "Number of daily USDT-volume observations equal to zero.",
        ),
        (
            "Zero share",
            "Zero-volume observations divided by all observed candles in the period.",
        ),
        ("Total", "Sum of daily quote-asset volume in USDT; reported only for volume."),
        ("Mean", "Arithmetic average of the observed values."),
        (
            "Median",
            "50th percentile; half the observations are at or below this value.",
        ),
        (
            "Sample standard deviation",
            "Sample dispersion around the mean, calculated with ddof=1.",
        ),
        (
            "Sample variance",
            "Square of the sample standard deviation, calculated with ddof=1.",
        ),
        ("Minimum", "Smallest observed value in the specified period."),
        ("Q1", "25th percentile using linear interpolation."),
        ("Q3", "75th percentile using linear interpolation."),
        ("Maximum", "Largest observed value in the specified period."),
        ("Range", "Maximum minus minimum."),
        (
            "Interquartile range",
            "Q3 minus Q1; spread of the central 50% of observations.",
        ),
        (
            "Coefficient of variation",
            "Sample standard deviation divided by the arithmetic mean.",
        ),
        (
            "Skewness",
            "Unbiased normalized sample skewness; positive values indicate a longer right tail.",
        ),
        (
            "Excess kurtosis",
            config.kurtosis_definition
            + "; zero corresponds to normal-distribution kurtosis.",
        ),
        (
            "Semester",
            "UTC calendar semester: H1 is January-June and H2 is July-December.",
        ),
        (
            "Partial semester",
            "A semester without observations covering both nominal UTC calendar-semester boundaries.",
        ),
        (
            "Missing-data treatment",
            "No interpolation, forward fill, backfill, or synthetic observations.",
        ),
        (
            "Listing treatment",
            "Each pair begins on 2019-07-01 UTC or its later first Binance candle.",
        ),
        (
            "Interpretation",
            "Price levels are non-stationary and coverage differs by listing date; these statistics are not return or risk estimates.",
        ),
        (
            "Volume limitation",
            "Kline volume is aggregated exchange-reported activity, not transaction-level data.",
        ),
    ]
    return [
        {"Item": item, "Definition": definition} for item, definition in definitions
    ]
