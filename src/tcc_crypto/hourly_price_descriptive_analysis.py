"""Compatibility imports; implementations live in domain packages."""

# ruff: noqa: F401
from tcc_crypto.analysis.hourly_prices import (
    describe_coverage,
    describe_extremes,
    describe_price_levels,
)
from tcc_crypto.analysis.hourly_prices_config import (
    PRICE_FIELDS,
    DescriptiveAnalysisConfig,
    load_analysis_config,
)
from tcc_crypto.data.exploratory import HOUR_MS, canonical_csv_path, load_hourly_prices
from tcc_crypto.workflows.descriptive_compat import (
    AnalysisArtifacts,
    _write_workbook,
    plot_symbol_open_close,
    run_descriptive_analysis,
)
