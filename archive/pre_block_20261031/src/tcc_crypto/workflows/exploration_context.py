"""Resolve each exploratory configuration and execution before doing work."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TypeAlias

from tcc_crypto.analysis.correlation import CorrelationConfig, load_correlation_config
from tcc_crypto.analysis.daily_descriptive_config import DailyPriceVolumeAnalysisConfig
from tcc_crypto.analysis.daily_descriptive_config import (
    load_analysis_config as load_daily,
)
from tcc_crypto.analysis.future_high_config import (
    FutureHighReturnConfig,
    load_future_high_return_config,
)
from tcc_crypto.analysis.hourly_activity_config import (
    MarketActivityAnalysisConfig,
    load_market_activity_config,
)
from tcc_crypto.analysis.hourly_prices_config import DescriptiveAnalysisConfig
from tcc_crypto.analysis.hourly_prices_config import load_analysis_config as load_prices
from tcc_crypto.collection.config import CollectionConfig, load_collection_config
from tcc_crypto.collection.exploratory_config import (
    ExplorationCollectionConfig,
    load_exploration_collection_config,
)
from tcc_crypto.features.config import DailyFeatureConfig, load_daily_feature_config
from tcc_crypto.paths import ExplorationPaths, new_run_id, repository_root
from tcc_crypto.reporting.provenance import file_sha256

DEFAULT_CONFIGS = {
    "earliest": "binance_exploration_earliest.json",
    "coverage": "binance_exploration_coverage.json",
    "annual-volume": "binance_exploration_annual_volume.json",
    "trade-counts": "binance_exploration_trade_counts.json",
    "open-correlation": "binance_hourly_open_correlation.json",
    "return-correlation": "binance_hourly_high_open_return_correlation.json",
    "hourly-prices": "binance_hourly_price_descriptive_analysis.json",
    "hourly-activity": "binance_hourly_market_activity_descriptive_analysis.json",
    "daily-descriptive": "binance_daily_price_volume_descriptive_analysis.json",
    "future-high": "binance_daily_future_high_returns.json",
    "feature-selection": "binance_daily_features.json",
}
API_ANALYSES = ("earliest", "coverage", "annual-volume", "trade-counts")
Settings: TypeAlias = (
    ExplorationCollectionConfig
    | CorrelationConfig
    | DescriptiveAnalysisConfig
    | MarketActivityAnalysisConfig
    | DailyPriceVolumeAnalysisConfig
    | FutureHighReturnConfig
    | DailyFeatureConfig
)


@dataclass(frozen=True)
class ExplorationContext:
    root: Path
    analysis: str
    settings: Settings
    paths: ExplorationPaths
    configuration_files: tuple[Path, ...]
    collection: CollectionConfig | None = None
    symbols: tuple[str, ...] = ()

    def signature(self) -> dict:
        return {
            "settings": json.loads(json.dumps(asdict(self.settings), default=str)),
            "analysis": self.analysis,
            "analysis_id": self.paths.analysis_id,
            "run_id": self.paths.run_id,
            "symbols": list(self.symbols),
            "configuration": {str(p): file_sha256(p) for p in self.configuration_files},
        }


def open_exploration(
    analysis: str,
    *,
    config_path: Path | None = None,
    root: Path | None = None,
    run_id: str | None = None,
    symbols: tuple[str, ...] | None = None,
) -> ExplorationContext:
    if analysis not in DEFAULT_CONFIGS:
        raise ValueError(f"Unknown analysis: {analysis}")
    root = repository_root(root)
    path = (
        root / (config_path or Path("configs") / DEFAULT_CONFIGS[analysis])
    ).resolve()
    collection = None
    files = [path]
    if analysis in API_ANALYSES:
        settings = load_exploration_collection_config(path)
        interval = "mixed" if len(settings.intervals) > 1 else settings.intervals[0]
    elif analysis in ("open-correlation", "return-correlation"):
        settings = load_correlation_config(path)
        collection_path = root / settings.collection_config
        interval = "1h"
        collection = load_collection_config(collection_path)
        files.append(collection_path)
    elif analysis == "feature-selection":
        settings = load_daily_feature_config(path)
        collection_path = root / settings.collection_config
        interval = "1d"
        collection = load_collection_config(collection_path)
        files.append(collection_path)
    elif analysis == "future-high":
        settings = load_future_high_return_config(path, repository_root=root)
        collection_path = root / settings.collection_config
        interval = "1d"
        collection = load_collection_config(collection_path)
        files.append(collection_path)
    else:
        loader = {
            "hourly-prices": load_prices,
            "hourly-activity": load_market_activity_config,
            "daily-descriptive": load_daily,
        }[analysis]
        settings, collection = loader(path, repository_root=root)
        files.append(settings.collection_config_path)
        interval = collection.interval
    universe = (
        settings.candidate_symbols
        if isinstance(settings, CorrelationConfig)
        else collection.symbols
        if collection
        else settings.symbols
    )
    selected = tuple(symbols) if symbols is not None else tuple(universe)
    if len(set(selected)) != len(selected) or set(selected) - set(universe):
        raise ValueError(
            "Requested symbols must be unique members of the configured universe."
        )
    if (
        isinstance(settings, CorrelationConfig)
        and selected != settings.candidate_symbols
    ):
        raise ValueError(
            "Correlation uses the frozen approved candidate universe; symbol overrides are not permitted."
        )
    analysis_id = (
        settings.feature_set_id
        if isinstance(settings, DailyFeatureConfig)
        else settings.analysis_id
    )
    return ExplorationContext(
        root,
        analysis,
        settings,
        ExplorationPaths(root, analysis, analysis_id, run_id or new_run_id(), interval),
        tuple(files),
        collection,
        selected,
    )
