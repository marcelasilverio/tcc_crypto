"""Load observations and report gaps without applying modeling imputation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from tcc_crypto.analysis.correlation import load_correlation_inputs
from tcc_crypto.analysis.daily_descriptive import filter_analysis_window
from tcc_crypto.collection.exploratory import (
    Requester,
    collect_exploration,
    snapshot_requester,
)
from tcc_crypto.data.exploratory import (
    canonical_csv_path,
    load_daily_open_high,
    load_daily_price_volume,
    load_hourly_market_activity,
    load_hourly_prices,
)
from tcc_crypto.data.loaders import load_daily_feature_input
from tcc_crypto.reporting.provenance import file_sha256
from tcc_crypto.reporting.tables import write_json
from tcc_crypto.workflows.exploration_context import API_ANALYSES, ExplorationContext


@dataclass
class ExplorationInputs:
    values: dict[str, pd.DataFrame] = field(default_factory=dict)
    sources: tuple[Path, ...] = ()
    diagnostics: pd.DataFrame = field(default_factory=pd.DataFrame)
    missing_dates: dict[str, pd.DataFrame] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


def load_inputs(context: ExplorationContext) -> ExplorationInputs:
    """Validate immutable files; only feature analysis produces per-asset blocking diagnostics."""
    if context.analysis in API_ANALYSES:
        raise ValueError("API analysis requires collect_inputs or load_saved_inputs.")
    if context.analysis == "feature-selection":
        return load_feature_inputs(context)
    sources = {
        symbol: canonical_csv_path(context.root, context.collection, symbol)
        for symbol in context.symbols
    }
    if context.analysis in ("open-correlation", "return-correlation"):
        tables = load_correlation_inputs(sources, context.settings)
        return ExplorationInputs(tables, tuple(sources.values()))
    values = {}
    for symbol, path in sources.items():
        if context.analysis == "hourly-prices":
            values[symbol] = load_hourly_prices(path, context.settings.price_fields)
        elif context.analysis == "hourly-activity":
            values[symbol] = load_hourly_market_activity(
                path, context.settings.activity_fields
            )
        elif context.analysis == "daily-descriptive":
            values[symbol] = filter_analysis_window(
                load_daily_price_volume(path),
                context.settings.analysis_start_utc,
                context.settings.analysis_end_utc,
            )
        else:
            values[symbol] = load_daily_open_high(path)
    return ExplorationInputs(values, tuple(sources.values()))


def load_feature_inputs(context: ExplorationContext) -> ExplorationInputs:
    values, sources, diagnostics, missing = {}, [], [], {}
    directory = context.root / context.collection.output_directory
    for symbol in context.symbols:
        candidates = sorted((directory / symbol).glob(f"{symbol}_1d_*.csv.gz"))
        sources.extend(candidates)
        try:
            path = canonical_csv_path(context.root, context.collection, symbol)
            values[symbol] = load_daily_feature_input(path)
        except (ValueError, TypeError, FileNotFoundError) as error:
            dates = pd.DatetimeIndex([], tz="UTC")
            if len(candidates) == 1:
                try:
                    frame = pd.read_csv(candidates[0], usecols=["open_time_ms"])
                    times = pd.DatetimeIndex(
                        pd.to_datetime(frame["open_time_ms"], unit="ms", utc=True)
                    )
                    if len(times):
                        dates = pd.date_range(
                            times.min(), times.max(), freq="D"
                        ).difference(times)
                except (ValueError, TypeError, KeyError):
                    pass  # Keep the original validation failure as the diagnostic.
            missing[symbol] = pd.DataFrame({"missing_date_utc": dates})
            diagnostics.append(
                {
                    "symbol": symbol,
                    "status": "BLOCKED",
                    "missing_utc_days": len(dates),
                    "diagnostic": f"{type(error).__name__}: {error}",
                }
            )
    return ExplorationInputs(values, tuple(sources), pd.DataFrame(diagnostics), missing)


def collect_inputs(
    context: ExplorationContext,
    *,
    requester: Requester | None = None,
    execution_time: pd.Timestamp | None = None,
) -> ExplorationInputs:
    if context.analysis not in API_ANALYSES:
        raise ValueError("This analysis reads existing raw files; it does not collect.")
    state_path = context.paths.raw / "execution.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state["context"] != context.signature():
            raise ValueError(
                "Collection run configuration changed; use a new run identifier."
            )
        recorded = pd.Timestamp(state["execution_time"])
        if execution_time is not None and execution_time != recorded:
            raise ValueError("A resumed collection must preserve its execution cutoff.")
        execution_time = recorded
    else:
        execution_time = execution_time or pd.Timestamp.now(tz="UTC")
        write_json(
            state_path,
            {
                "context": context.signature(),
                "execution_time": execution_time.isoformat(),
            },
        )

    def store_record(record: dict) -> dict:
        symbol = record["pair"]["Trading Pair"]
        path = context.paths.raw / "symbols" / (symbol + ".json")
        if path.exists():
            if json.loads(path.read_text()) != record:
                raise ValueError(f"Saved symbol response differs: {symbol}")
        else:
            write_json(path, record)
        return {"record_path": str(path), "sha256": file_sha256(path)}

    raw = collect_exploration(
        context.analysis,
        context.settings,
        requester=snapshot_requester(context.paths.raw, context.settings, requester),
        execution_time=execution_time,
        record_sink=store_record,
    )
    return ExplorationInputs(
        sources=tuple(sorted(context.paths.raw.rglob("*.json"))), raw=raw
    )
