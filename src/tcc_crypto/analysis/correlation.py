"""Pairwise-complete Pearson correlations on exact observed UTC timestamps."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tcc_crypto.data.exploratory import load_hourly_prices
from tcc_crypto.paths import reject_legacy_analysis_paths


@dataclass(frozen=True)
class CorrelationConfig:
    analysis_id: str
    collection_config: Path
    candidate_symbols: tuple[str, ...]
    value: str
    first_candle_cutoff_utc: pd.Timestamp
    end_utc: pd.Timestamp
    reference_symbol: str


def load_correlation_config(path: Path) -> CorrelationConfig:
    payload = json.loads(path.read_text())
    reject_legacy_analysis_paths(payload)
    symbols = tuple(payload["candidate_symbols"])
    if len(symbols) != 30 or len(set(symbols)) != 30:
        raise ValueError("Correlation requires the explicit approved 30-pair universe.")
    if payload["value"] not in ("open", "high_open_return"):
        raise ValueError("Unsupported correlation input.")
    cutoff = pd.Timestamp(payload["first_candle_cutoff_utc"])
    end = pd.Timestamp(payload["end_utc"])
    if cutoff.tzinfo is None or end.tzinfo is None:
        raise ValueError(
            "Correlation boundaries must include UTC timezone information."
        )
    return CorrelationConfig(
        payload["analysis_id"],
        Path(payload["collection_config"]),
        symbols,
        payload["value"],
        cutoff.tz_convert("UTC"),
        end.tz_convert("UTC"),
        payload["reference_symbol"],
    )


def correlation_series(values: pd.DataFrame, value: str) -> pd.Series:
    """Hourly high/open appreciation is an outcome, not a holding-period return."""
    if value == "open":
        return values["open"].copy()
    if value != "high_open_return":
        raise ValueError("Unsupported correlation input.")
    if (values["high"] < values["open"]).any():
        raise ValueError("Hourly high must be at least the opening price.")
    return (values["high"] - values["open"]) / values["open"]


def calculate_correlations(
    series: pd.DataFrame, reference_symbol: str
) -> dict[str, pd.DataFrame]:
    """Never fill gaps: each coefficient uses only its two observed series."""
    correlations = series.corr(method="pearson", min_periods=2)
    if correlations.isna().any().any():
        raise ValueError(
            "Undefined pairwise correlation: insufficient observations or constant series."
        )
    available = series.notna().astype("int64")
    counts = available.T.dot(available)
    relationship = (
        pd.DataFrame(
            {
                f"Pearson correlation with {reference_symbol}": correlations[
                    reference_symbol
                ],
                "Paired observations": counts[reference_symbol],
            }
        )
        .drop(index=reference_symbol)
        .sort_values(f"Pearson correlation with {reference_symbol}", ascending=False)
    )
    return {
        "correlations": correlations,
        "paired_observations": counts,
        "reference_relationship": relationship,
    }


def load_correlation_inputs(
    sources: dict[str, Path], config: CorrelationConfig
) -> dict[str, pd.DataFrame]:
    rows, series = [], []
    fields = ["open"] if config.value == "open" else ["open", "high"]
    for symbol in config.candidate_symbols:
        values = load_hourly_prices(sources[symbol], fields)
        values = values.loc[: config.end_utc]
        if values.empty:
            raise ValueError(f"{symbol} has no observations in the approved period.")
        result = correlation_series(values, config.value).rename(symbol)
        rows.append(
            {
                "Symbol": symbol,
                "Observations": len(result),
                "First open (UTC)": result.index.min(),
                "Last open (UTC)": result.index.max(),
                "Eligible": result.index.min() <= config.first_candle_cutoff_utc,
                "Source file": str(sources[symbol]),
            }
        )
        if rows[-1]["Eligible"]:
            series.append(result)
    aligned = pd.concat(series, axis=1).sort_index()
    if config.reference_symbol not in aligned:
        raise ValueError("Reference symbol is not eligible.")
    return {"series": aligned, "source_summary": pd.DataFrame(rows)}
