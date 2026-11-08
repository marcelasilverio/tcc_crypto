"""Artifact names and immutable path resolution; importing creates nothing."""

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path("configs/experiment.json")
RAW = Path("data/raw/binance/spot/1d")
PROCESSED = Path("data/processed")
OUTPUTS = Path("outputs/experiments")
PORTFOLIO_CONFIG = Path("configs/portfolio.json")
PORTFOLIO_OUTPUTS = Path("outputs/portfolios")
PORTFOLIO_TABLES = ("capital", "signals", "operations")
MAIN_TABLES = (
    "availability",
    "treatment",
    "metrics",
    "feature_selection",
    "predictions_in_sample",
    "actuals_in_sample",
    "predictions_out_of_sample",
    "actuals_out_of_sample",
)


def component(value: str) -> str:
    if not value or value in (".", "..") or Path(value).name != value or "\\" in value:
        raise ValueError(f"Invalid path component: {value!r}")
    return value


@dataclass(frozen=True)
class Paths:
    root: Path
    run_id: str

    def __post_init__(self):
        component(self.run_id)

    @property
    def processed(self):
        return self.root / PROCESSED / f"daily_{self.run_id}"

    @property
    def output(self):
        return self.root / OUTPUTS / f"daily_{self.run_id}"

    @property
    def configuration(self) -> Path:
        return self.output / "configuration.json"

    @property
    def execution(self) -> Path:
        return self.output / "execution.json"

    def table(self, symbol: str, stage: str) -> Path:
        return self.processed / f"{component(symbol)}_{component(stage)}.csv"

    def audit(self, symbol: str, name: str) -> Path:
        return self.output / "audit" / f"{component(symbol)}_{component(name)}.csv"

    def main(self, name: str) -> Path:
        if name not in MAIN_TABLES:
            raise ValueError(f"Unknown main table: {name}")
        return self.output / f"{name}.csv"


def metadata_path(path: Path) -> Path:
    return path.with_name(path.name + ".metadata.json")


@dataclass(frozen=True)
class PortfolioPaths:
    root: Path
    run_id: str

    def __post_init__(self):
        component(self.run_id)

    @property
    def output(self) -> Path:
        return self.root / PORTFOLIO_OUTPUTS / self.run_id

    @property
    def lock(self) -> Path:
        return self.output.with_name(f".{self.run_id}.lock")

    def temporary(self, token: str) -> Path:
        return self.output.with_name(f".{self.run_id}.{component(token)}")

    def artifact(self, name: str, directory: Path | None = None) -> Path:
        suffixes = {
            **dict.fromkeys(PORTFOLIO_TABLES, ".csv"),
            **dict.fromkeys(
                ("configuration", "source", "execution", "complete"), ".json"
            ),
        }
        if name not in suffixes:
            raise ValueError(f"Unknown portfolio artifact: {name}")
        return (self.output if directory is None else directory) / (
            name + suffixes[name]
        )


def raw_paths(root: Path, symbol: str, collection: dict) -> dict[str, Path]:
    directory = root / RAW / component(symbol)
    stem = f"{symbol}_1d_{collection['start_time_utc'][:10]}_{collection['end_time_utc'][:10]}"
    return {
        "raw": directory / f"{stem}.csv.gz",
        "metadata": directory / f"{stem}.metadata.json",
        "partial": directory / f".{stem}.partial.csv",
        "checkpoint": directory / f".{stem}.checkpoint.json",
    }
