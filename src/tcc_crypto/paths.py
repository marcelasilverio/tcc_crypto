"""Canonical artifact locations. Importing this module performs no filesystem I/O."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from tcc_crypto.collection.config import CollectionConfig

from tcc_crypto.data.repository import find_repository_root

RAW_DAILY_DIR: Final = Path("data/raw/binance/spot/1d")
PROCESSED_DAILY_DIR: Final = Path("data/processed/binance/spot/1d")
ALIGNED_DAILY_DIR: Final = PROCESSED_DAILY_DIR / "aligned"
DAILY_FEATURES_DIR: Final = PROCESSED_DAILY_DIR / "features"
DAILY_TARGETS_DIR: Final = PROCESSED_DAILY_DIR / "targets"
DAILY_DATASETS_DIR: Final = PROCESSED_DAILY_DIR / "datasets"
DAILY_OUTPUTS_DIR: Final = Path("outputs/binance/spot/1d")
DATASET_WORKBOOKS_DIR: Final = DAILY_OUTPUTS_DIR / "datasets"
SVM_PILOT_RESULTS_DIR: Final = DAILY_OUTPUTS_DIR / "svm_pilot"
SVM_GRID_SEARCH_RESULTS_DIR: Final = DAILY_OUTPUTS_DIR / "grid_search"
SVM_FINAL_RESULTS_DIR: Final = DAILY_OUTPUTS_DIR / "svm_final"
FINAL_EVALUATION_CONFIG_PATH: Final = Path(
    "configs/binance_daily_svm_final_evaluation.json"
)
FINAL_TABLE_NAMES: Final = {
    "eligibility": "asset_eligibility.csv",
    "predictions": "dated_predictions.csv.gz",
    "metrics": "classification_metrics.csv",
    "roc": "roc_curve_points.csv.gz",
    "precision_recall": "precision_recall_curve_points.csv.gz",
    "selected_configurations": "frozen_configurations.csv",
}
FINAL_FIGURE_NAMES: Final = {
    "roc": "roc_curves.png",
    "precision_recall": "precision_recall_curves.png",
}
TRAINING_REVIEW_DIR_NAME: Final = "supervisor_review"
TRAINING_FOLD_METRICS_NAME: Final = "training_fold_metrics.csv"
EXPERIMENT_OVERVIEW_NAME: Final = "experiment_overview.xlsx"
DATASET_WORKBOOK_NAME: Final = "features_and_targets.xlsx"
SVM_WORKBOOK_NAME: Final = "svm_results.xlsx"
RUN_METADATA_NAME: Final = "run_metadata.json"
CONFIGURATION_SNAPSHOT_NAME: Final = "configuration_snapshot.json"
PILOT_TABLE_NAMES: Final = {
    "predictions": "rolling_predictions.csv",
    "summary": "metrics_summary.csv",
}
GRID_TABLE_NAMES: Final = {
    "eligibility": "asset_eligibility.csv",
    "fold_results": "fold_results.csv.gz",
    "candidate_results": "candidate_results.csv.gz",
    "selected_configurations": "selected_configurations.csv",
}
PILOT_CONFIG_PATH: Final = Path("configs/binance_daily_svm_pilot_dataset.json")
GRID_CONFIG_PATH: Final = Path("configs/binance_daily_svm_grid_search.json")
COLLECTION_CONFIG_PATH: Final = Path(
    "configs/binance_selected_usdt_daily_collection.json"
)


def repository_root(explicit: Path | None = None) -> Path:
    """Resolve an explicit root or the installed editable source checkout."""
    return (
        explicit.resolve()
        if explicit is not None
        else find_repository_root(Path(__file__).parent)
    )


@dataclass(frozen=True)
class FinalArtifactPaths:
    """Final classifier outputs, isolated from development and pilot evidence."""

    root: Path
    evaluation_id: str
    symbol: str

    @property
    def directory(self) -> Path:
        return self.root / SVM_FINAL_RESULTS_DIR / self.evaluation_id / self.symbol

    def tables(self) -> dict[str, Path]:
        return {
            name: self.directory / filename
            for name, filename in FINAL_TABLE_NAMES.items()
        }

    def figures(self) -> dict[str, Path]:
        return {
            name: self.directory / filename
            for name, filename in FINAL_FIGURE_NAMES.items()
        }


def resolve_path(root: Path, path: Path | str) -> Path:
    return (root / path).resolve()


def metadata_path(path: Path) -> Path:
    return path.with_name(path.name + ".metadata.json")


@dataclass(frozen=True)
class ArtifactPaths:
    """All outputs for one context and asset, with explicit legacy overrides."""

    root: Path
    context_id: str
    symbol: str
    raw_directory: Path = RAW_DAILY_DIR
    results_directory: Path | None = None
    feature_directory: Path | None = None

    def __post_init__(self) -> None:
        for value in (self.context_id, self.symbol):
            if (
                not value
                or Path(value).name != value
                or value in (".", "..")
                or "\\" in value
            ):
                raise ValueError("Context and symbol must be single path components.")
        object.__setattr__(self, "root", self.root.resolve())

    @property
    def raw(self) -> Path:
        return resolve_path(self.root, self.raw_directory) / self.symbol

    def table(self, stage: str) -> Path:
        directories = {
            "aligned": ALIGNED_DAILY_DIR,
            "features": DAILY_FEATURES_DIR,
            "targets": DAILY_TARGETS_DIR,
            "dataset": DAILY_DATASETS_DIR,
        }
        if stage == "features" and self.feature_directory is not None:
            return (
                resolve_path(self.root, self.feature_directory)
                / self.context_id
                / f"{self.symbol}.csv.gz"
            )
        return (
            self.root / directories[stage] / self.context_id / f"{self.symbol}.csv.gz"
        )

    @property
    def dataset_workbook(self) -> Path:
        return (
            self.root
            / DATASET_WORKBOOKS_DIR
            / self.context_id
            / self.symbol
            / DATASET_WORKBOOK_NAME
        )

    def results(self, kind: str) -> Path:
        directory = {
            "pilot": SVM_PILOT_RESULTS_DIR,
            "grid-search": SVM_GRID_SEARCH_RESULTS_DIR,
        }[kind]
        if self.results_directory is not None:
            return resolve_path(self.root, self.results_directory) / self.symbol
        return self.root / directory / self.context_id / self.symbol

    def inventory(self, kind: str) -> dict[str, str]:
        paths = {
            "raw_directory": self.raw,
            **{
                stage: self.table(stage)
                for stage in ("aligned", "features", "targets", "dataset")
            },
            "dataset_workbook": self.dataset_workbook,
        }
        if kind == "preparation":
            return {key: str(value) for key, value in paths.items()}
        names = PILOT_TABLE_NAMES if kind == "pilot" else GRID_TABLE_NAMES
        paths.update(
            {name: self.results(kind) / filename for name, filename in names.items()}
        )
        paths.update(
            {
                "results_workbook": self.results(kind) / SVM_WORKBOOK_NAME,
                "run_metadata": self.results(kind) / RUN_METADATA_NAME,
                "configuration_snapshot": self.results(kind)
                / CONFIGURATION_SNAPSHOT_NAME,
            }
        )
        return {key: str(value) for key, value in paths.items()}


@dataclass(frozen=True)
class PairOutputPaths:
    """Final and resumable artifact paths for one trading pair."""

    directory: Path
    raw_csv_gz: Path
    workbook: Path
    metadata_json: Path
    partial_csv: Path
    checkpoint_json: Path


def pair_output_paths(
    symbol: str,
    config: CollectionConfig,
    repository_root: Path,
) -> PairOutputPaths:
    """Return the structured per-symbol paths for final and partial artifacts."""
    start_date = config.start_time_utc.strftime("%Y-%m-%d")
    end_date = config.end_time_utc.strftime("%Y-%m-%d")
    stem = f"{symbol}_{config.interval}_{start_date}_{end_date}"
    directory = repository_root / config.output_directory / symbol
    return PairOutputPaths(
        directory=directory,
        raw_csv_gz=directory / f"{stem}.csv.gz",
        workbook=directory / f"{stem}.xlsx",
        metadata_json=directory / f"{stem}.metadata.json",
        partial_csv=directory / f".{stem}.partial.csv",
        checkpoint_json=directory / f".{stem}.checkpoint.json",
    )


# Exploratory artifacts use one explicit UTC execution identifier across stages.
EXPLORATION_RAW_DIR: Final = Path("data/raw/binance/spot/exploration")
EXPLORATION_WORKBOOKS_DIR: Final = Path("data/exploration/binance/spot")
EXPLORATION_OUTPUTS_DIR: Final = Path("outputs/binance/spot")
EXPLORATION_PROCESSED_DIR: Final = Path("data/processed/binance/spot")
MIGRATION_MANIFEST_DIR: Final = Path("outputs/migrations")
ANALYSIS_TABLE_SUFFIX: Final = ".csv.gz"
ANALYSIS_INPUTS_NAME: Final = "inputs.json"
ANALYSIS_RESULTS_NAME: Final = "results.json"
ANALYSIS_WORKBOOK_NAME: Final = "analysis.xlsx"


def reject_legacy_analysis_paths(payload: dict) -> None:
    """Require migration instead of silently writing to historical directories."""
    obsolete = {
        "output_directory",
        "analysis_output_directory",
        "packet_directory",
    } & payload.keys()
    if obsolete:
        raise ValueError(
            f"Legacy analysis path keys {sorted(obsolete)} must be removed. "
            "Use 'python -m tcc_crypto.migrate' to inventory and migrate historical outputs."
        )


def analysis_output_directory(root: Path, analysis: str, analysis_id: str) -> Path:
    return root / EXPLORATION_OUTPUTS_DIR / analysis / analysis_id


def new_run_id() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


@dataclass(frozen=True)
class ExplorationPaths:
    """Resolved locations for an exploratory execution; construction does no I/O."""

    root: Path
    analysis: str
    analysis_id: str
    run_id: str
    interval: str

    def __post_init__(self) -> None:
        for value in (self.analysis, self.analysis_id, self.run_id, self.interval):
            if (
                not value
                or Path(value).name != value
                or value in (".", "..")
                or "\\" in value
            ):
                raise ValueError("Analysis identifiers must be single path components.")
        object.__setattr__(self, "root", self.root.resolve())

    @property
    def raw(self) -> Path:
        return self.root / EXPLORATION_RAW_DIR / self.analysis / self.run_id

    @property
    def tables(self) -> Path:
        return (
            self.root
            / EXPLORATION_PROCESSED_DIR
            / self.interval
            / "analyses"
            / self.analysis
            / self.analysis_id
            / self.run_id
        )

    @property
    def workbooks(self) -> Path:
        return (
            self.root
            / EXPLORATION_WORKBOOKS_DIR
            / self.analysis
            / self.analysis_id
            / self.run_id
        )

    @property
    def outputs(self) -> Path:
        return (
            analysis_output_directory(self.root, self.analysis, self.analysis_id)
            / self.run_id
        )

    def table(self, name: str) -> Path:
        if Path(name).name != name or name in (".", ".."):
            raise ValueError("Table name must be a single path component.")
        return self.tables / (name + ANALYSIS_TABLE_SUFFIX)

    def inventory(self) -> dict[str, str]:
        return {
            name: str(getattr(self, name))
            for name in ("raw", "tables", "workbooks", "outputs")
        }
