"""Compatibility imports; implementations live in domain packages."""

# ruff: noqa: F401
from tcc_crypto.analysis.future_high import (
    build_selected_symbol_returns,
    select_reproducible_symbols,
    symbols_observed_on_date,
)
from tcc_crypto.analysis.future_high_config import (
    FutureHighReturnConfig,
    load_future_high_return_config,
)
from tcc_crypto.data.exploratory import load_collection_symbols, load_daily_open_high
from tcc_crypto.data.loaders import find_symbol_csv
from tcc_crypto.targets.future_high import calculate_future_high_returns
