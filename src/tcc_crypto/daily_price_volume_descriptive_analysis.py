"""Compatibility imports; implementations live in domain packages."""

# ruff: noqa: F401
from tcc_crypto.analysis.daily_descriptive import (
    PRICE_FIELDS,
    VOLUME_FIELD,
    _series_statistics,
    daily_quote_volume_billions,
    describe_coverage,
    describe_extrema,
    describe_semesters,
    describe_statistics,
    filter_analysis_window,
    natural_log_open_close,
    semester_bounds,
    semester_label,
)
from tcc_crypto.analysis.daily_descriptive_config import (
    DailyPriceVolumeAnalysisConfig,
    load_analysis_config,
)
from tcc_crypto.data.exploratory import (
    DAY_MS,
    canonical_csv_path,
    load_daily_price_volume,
)
from tcc_crypto.reporting.descriptive_compat import (
    build_pair_payload,
    prepare_analysis_packets,
)
from tcc_crypto.reporting.descriptive_definitions import definition_rows
from tcc_crypto.workflows.descriptive_compat import (
    DailySmallMultipleArtifacts,
    create_daily_small_multiple_figures,
)


def main() -> None:
    """Delegate CLI execution to the independent exploratory workflow."""
    import sys

    from tcc_crypto.explore import main as explore_main

    explore_main(["daily-descriptive", "run", *sys.argv[1:]])


if __name__ == "__main__":
    main()
