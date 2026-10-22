"""Compatibility imports; implementations live in domain packages."""

# ruff: noqa: F401
from tcc_crypto.analysis.hourly_activity import (
    ACTIVITY_FIELDS,
    activity_unit,
    describe_activity_extremes,
    describe_market_activity,
)
from tcc_crypto.analysis.hourly_activity_config import (
    MarketActivityAnalysisConfig,
    load_market_activity_config,
)
from tcc_crypto.analysis.hourly_prices import describe_coverage
from tcc_crypto.data.exploratory import (
    HOUR_MS,
    canonical_csv_path,
    load_hourly_market_activity,
)
from tcc_crypto.workflows.descriptive_compat import (
    MarketActivityArtifacts,
    plot_symbol_activity,
    run_market_activity_analysis,
)
