"""Recognized historical artifact mappings and checksum-verified, resumable moves."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from tcc_crypto.paths import MIGRATION_MANIFEST_DIR, ArtifactPaths, ExplorationPaths
from tcc_crypto.reporting.provenance import file_sha256
from tcc_crypto.reporting.tables import write_json

MIGRATION_NAME = "exploration-v1.json"


@dataclass(frozen=True)
class MigrationItem:
    source: str
    destination: str
    sha256: str
    status: str = "planned"
    note: str = "Historical bytes preserved; original provenance is not rewritten."


def _recognized_groups(root: Path) -> list[tuple[Path, ExplorationPaths, str]]:
    configs = root / "configs"

    def identifier(filename: str, key: str = "analysis_id") -> str:
        return json.loads((configs / filename).read_text())[key]

    groups = []

    def add(
        source: str,
        analysis: str,
        analysis_id: str,
        interval: str = "1d",
        scope: str = "legacy",
    ):
        groups.append(
            (
                root / source,
                ExplorationPaths(root, analysis, analysis_id, scope, interval),
                scope,
            )
        )

    add(
        "outputs/binance_hourly_price_descriptive_analysis",
        "hourly-prices",
        identifier("binance_hourly_price_descriptive_analysis.json"),
        "1h",
    )
    add(
        "outputs/binance_hourly_market_activity_descriptive_analysis",
        "hourly-activity",
        identifier("binance_hourly_market_activity_descriptive_analysis.json"),
        "1h",
    )
    add(
        "outputs/01a0c054-31e7-71c1-9ce9-1017d0823230/binance_daily_price_volume_descriptive_analysis",
        "daily-descriptive",
        identifier("binance_daily_price_volume_descriptive_analysis.json"),
    )
    add(
        "outputs/binance_daily_future_high_returns_2019H2_2026-09-01",
        "future-high",
        identifier("binance_daily_future_high_returns.json"),
    )
    add(
        "outputs/01a1019c-c098-7d61-b949-3bfbff52d8dd",
        "future-high",
        identifier("binance_daily_future_high_returns.json"),
        scope="legacy_workbook",
    )
    feature_id = identifier("binance_daily_features.json", "feature_set_id")
    for scope in ("full", "smoke_1_symbols"):
        add(
            "outputs/binance_daily_feature_analysis/" + scope,
            "feature-selection",
            feature_id,
            scope="legacy_" + scope,
        )
    add(
        "data/processed/binance/daily_features_silva_2026_v1",
        "feature-selection",
        feature_id,
        scope="legacy_full",
    )
    for source, analysis, analysis_id in [
        ("tmp/daily_feature_workbook_packets", "feature-selection", feature_id),
        ("tmp/daily_feature_workbook_qa", "feature-selection", feature_id),
        (
            "tmp/daily_price_volume_workbook_inputs",
            "daily-descriptive",
            identifier("binance_daily_price_volume_descriptive_analysis.json"),
        ),
        (
            "tmp/daily_price_volume_workbook_qa",
            "daily-descriptive",
            identifier("binance_daily_price_volume_descriptive_analysis.json"),
        ),
    ]:
        add(source, analysis, analysis_id, scope="legacy_" + Path(source).name)
    for source, analysis in [
        ("binance_spot_btc_quote_pair_annual_volume.xlsx", "annual-volume"),
        ("binance_spot_btc_quote_pair_kline_coverage.xlsx", "coverage"),
        ("binance_spot_usdt_quote_pair_trade_counts.xlsx", "trade-counts"),
    ]:
        add(
            "data/exploration/" + source,
            analysis,
            identifier("binance_exploration_" + analysis.replace("-", "_") + ".json"),
            "mixed",
        )
    # Finder directory metadata is relocated too, so obsolete research directories can disappear.
    add(
        "outputs/binance_daily_feature_analysis/.DS_Store",
        "feature-selection",
        feature_id,
        scope="legacy_directory_metadata",
    )
    add(
        "outputs/01a0c054-31e7-71c1-9ce9-1017d0823230/.DS_Store",
        "daily-descriptive",
        identifier("binance_daily_price_volume_descriptive_analysis.json"),
        scope="legacy_directory_metadata",
    )
    # These two workbooks and the report have identifiable research titles, but no reproducible workflow metadata.
    add(
        "data/exploration/binance_spot_market_universe.xlsx",
        "market-universe",
        "historical_snapshot",
        "mixed",
    )
    add(
        "outputs/daily_pair_semester_coverage_20260920",
        "semester-coverage",
        "historical_20260920",
    )
    add(
        "outputs/pdf/binance_btc_correlation_analysis_report.pdf",
        "correlation-report",
        "historical_universe_unverified",
        "1h",
    )
    return groups


def inventory(root: Path) -> list[MigrationItem]:
    """Whitelist known research groups; never traverse arbitrary outputs or raw data."""
    root = root.resolve()
    items = []
    for source, paths, scope in _recognized_groups(root):
        files = (
            [source]
            if source.is_file()
            else sorted(p for p in source.rglob("*") if p.is_file())
        )
        for path in files:
            if path.is_symlink():
                continue
            relative = Path(path.name) if source.is_file() else path.relative_to(source)
            if path.suffix == ".xlsx":
                base = paths.workbooks.parent / "history" / scope
            elif path.name.endswith((".csv", ".csv.gz")):
                base = paths.tables.parent / "history" / scope
            else:
                base = paths.outputs.parent / "history" / scope
            # Distinguish groups sharing a historical scope, including system directory metadata.
            destination = base / source.stem / relative
            items.append(
                MigrationItem(
                    str(path.relative_to(root)),
                    str(destination.relative_to(root)),
                    file_sha256(path),
                )
            )
    for source, kind, key in [
        ("outputs/btc_daily_svm_pilot_2019H2", "pilot", "dataset_id"),
        (
            "outputs/binance_daily_svm_temporal_grid_search_v1",
            "grid-search",
            "experiment_id",
        ),
    ]:
        config = (
            "binance_daily_svm_pilot_dataset.json"
            if kind == "pilot"
            else "binance_daily_svm_grid_search.json"
        )
        context_id = json.loads((root / "configs" / config).read_text())[key]
        directory = root / source
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(directory)
            symbol = (
                relative.parts[0]
                if relative.parts[0].endswith("USDT")
                else "BTCUSDT"
                if kind == "pilot"
                else "universe"
            )
            destination = (
                ArtifactPaths(root, context_id, symbol).results(kind)
                / "history"
                / "legacy"
                / relative
            )
            items.append(
                MigrationItem(
                    str(path.relative_to(root)),
                    str(destination.relative_to(root)),
                    file_sha256(path),
                )
            )
    destinations = [item.destination for item in items]
    if len(destinations) != len(set(destinations)):
        raise ValueError(
            "Ambiguous historical destinations; migration cannot continue."
        )
    return items


def _safe_path(root: Path, relative: str) -> Path:
    path = root / relative
    if (
        path.is_symlink()
        or not path.resolve().is_relative_to(root)
        or path.resolve().is_relative_to(root / "data/raw")
    ):
        raise ValueError(f"Unsafe migration path: {relative}")
    return path


def apply_migration(root: Path, items: list[MigrationItem] | None = None) -> dict:
    """Copy exclusively, verify, journal, then remove the identical source."""
    root = root.resolve()
    journal = root / MIGRATION_MANIFEST_DIR / MIGRATION_NAME
    if journal.exists():
        payload = json.loads(journal.read_text())
        if payload["root"] != str(root):
            raise ValueError("Migration manifest belongs to a different repository.")
        known_sources = {item["source"] for item in payload["items"]}
        discovered = inventory(root) if items is None else items
        payload["items"].extend(
            asdict(item) for item in discovered if item.source not in known_sources
        )
    else:
        payload = {
            "root": str(root),
            "migration": "exploration-v1",
            "items": [
                asdict(item) for item in (inventory(root) if items is None else items)
            ],
        }
    # Preflight every collision and changed source before starting any new move.
    for item in payload["items"]:
        source = _safe_path(root, item["source"])
        destination = _safe_path(root, item["destination"])
        if source.exists() and file_sha256(source) != item["sha256"]:
            raise ValueError(f"Historical source changed: {source}")
        if destination.exists() and file_sha256(destination) != item["sha256"]:
            raise FileExistsError(f"Migration collision: {destination}")
        if not source.exists() and not destination.exists():
            raise FileNotFoundError(
                f"Both source and destination are missing: {source}"
            )
    write_json(journal, payload)
    for item in payload["items"]:
        source = _safe_path(root, item["source"])
        destination = _safe_path(root, item["destination"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            with source.open("rb") as reader, destination.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
        if file_sha256(destination) != item["sha256"]:
            raise ValueError(f"Copy verification failed: {destination}")
        item["status"] = "verified"
        write_json(journal, payload)
        if source.exists():
            if file_sha256(source) != item["sha256"]:
                raise ValueError(f"Source changed during copy: {source}")
            source.unlink()
        item["status"] = "migrated"
        write_json(journal, payload)
        parent = source.parent
        while parent != root and parent.parts[
            len(root.parts) : len(root.parts) + 1
        ] in [("outputs",), ("tmp",), ("data",)]:
            if parent in (
                root / "outputs",
                root / "tmp",
                root / "data",
                root / "data/exploration",
                root / "data/processed",
            ):
                break
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    return payload
