"""Typed CSV persistence and consultation tables, without scientific computation."""

import hashlib
import json
import platform
import shutil
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from uuid import uuid4

import pandas as pd

from tcc_crypto.paths import metadata_path

NULL_TOKEN = "__NULL__"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def execution_metadata(root: Path) -> dict:
    packages = {}
    for name in ("pandas", "numpy", "scikit-learn", "feature-engine", "TA-Lib"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None

    def git(*args):
        try:
            result = subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True
            )
        except OSError:
            return None
        return result.stdout.strip() if result.returncode == 0 else None

    return {
        "execution_time_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "package_versions": packages,
        "revision": git("rev-parse", "HEAD"),
        "working_tree_status": git("status", "--porcelain"),
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, default=str, sort_keys=True) + "\n"
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def ensure_writable(paths, *, overwrite: bool) -> None:
    existing = [str(p) for p in paths if p.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"Outputs exist; use --overwrite: {existing}")


def write_table(
    frame: pd.DataFrame, path: Path, *, context: dict, sources=(), overwrite=False
) -> Path:
    """Write explicit columns, schema and upstream checksums atomically."""
    ensure_writable([path, metadata_path(path)], overwrite=overwrite)
    data = frame.copy()
    if not isinstance(data.index, pd.RangeIndex):
        data = data.reset_index()
    if data.columns.has_duplicates:
        raise ValueError("Duplicate CSV column names.")
    for column in data.select_dtypes(include=["object"]).columns:
        data[column] = data[column].astype("string")
    for column in data.select_dtypes(include=["string"]).columns:
        if data[column].eq(NULL_TOKEN).any():
            raise ValueError("Reserved CSV missing-value token in data.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        data.to_csv(temporary, index=False, na_rep=NULL_TOKEN, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    write_json(
        metadata_path(path),
        {
            "schema_version": 2,
            "context": context,
            "sha256": file_sha256(path),
            "columns": {str(c): str(t) for c, t in data.dtypes.items()},
            "column_order": list(data.columns),
            "row_count": len(data),
            "sources": {str(Path(p).resolve()): file_sha256(Path(p)) for p in sources},
            "written_at_utc": datetime.now(timezone.utc).isoformat(),
            "attributes": data.attrs,
        },
    )
    return path


def validate_artifact(path: Path, context: dict, stage: str, seen=None) -> dict:
    """Validate the complete dependency graph, including stale grandparents."""
    seen = set() if seen is None else seen
    if path.resolve() in seen:
        raise ValueError("Cyclic artifact dependencies.")
    seen = seen | {path.resolve()}
    if not path.exists() or not metadata_path(path).exists():
        raise FileNotFoundError(f"Missing input {path}; run '{stage}' first.")
    meta = json.loads(metadata_path(path).read_text())
    if meta.get("schema_version") != 2 or meta["context"] != context:
        raise ValueError(f"Incompatible {stage} artifact: {path}")
    if file_sha256(path) != meta["sha256"]:
        raise ValueError(f"Modified {stage} artifact: {path}")
    for source, digest in meta["sources"].items():
        source = Path(source)
        if not source.exists() or file_sha256(source) != digest:
            raise ValueError(f"Stale {stage} input: {source}")
        if metadata_path(source).exists():
            upstream = json.loads(metadata_path(source).read_text())
            if upstream.get("schema_version") == 2:
                validate_artifact(source, context, stage, seen)
    return meta


def read_table(path: Path, *, context: dict, stage: str) -> pd.DataFrame:
    meta = validate_artifact(path, context, stage)
    if not meta["columns"]:
        return pd.DataFrame()
    dates = [c for c, t in meta["columns"].items() if t.startswith("datetime64")]
    data = pd.read_csv(
        path,
        dtype={c: t for c, t in meta["columns"].items() if c not in dates},
        keep_default_na=False,
        na_values=[NULL_TOKEN],
        float_precision="round_trip",
    )
    for column in dates:
        data[column] = pd.to_datetime(data[column], utc=True)
    if list(data.columns) != meta["column_order"] or len(data) != meta["row_count"]:
        raise ValueError(f"CSV schema mismatch: {path}")
    data.attrs = meta.get("attributes", {})
    return data


def binary_matrix(
    predictions: pd.DataFrame, symbols: list[str], role: str, *, actual=False
) -> pd.DataFrame:
    """Keep experiment coordinates; unavailable values are nullable, never zero."""
    keys = ["feature_time_utc", "target", "window_size"]
    if predictions.empty:
        return pd.DataFrame(columns=[*keys, *symbols])
    rows = predictions.loc[
        (predictions["role"] == role) & (predictions["model"] == "tuned_svc")
    ]
    if rows.duplicated([*keys, "symbol"]).any():
        raise ValueError("Multiple predictions share the same matrix coordinate.")
    value = "actual" if actual else "predicted"
    matrix = rows.pivot(index=keys, columns="symbol", values=value).reindex(
        columns=symbols
    )
    for symbol in symbols:
        matrix[symbol] = matrix[symbol].astype("Int64")
    matrix.columns.name = None
    return matrix.reset_index().sort_values(keys)


def preview(frame: pd.DataFrame, rows: int = 10) -> pd.DataFrame:
    """Notebook inspection only; no scientific recalculation."""
    return frame.head(rows)


def validate_portfolio_source(source: dict) -> None:
    """Validate the source under its original classification context."""
    for filename, digest in source["checksums"].items():
        path = Path(filename)
        if not path.exists() or file_sha256(path) != digest:
            raise ValueError(f"Missing or modified portfolio source: {filename}")
    for filename in source["tables"]:
        validate_artifact(Path(filename), source["context"], "saved training/data")


def validate_portfolio_bundle(paths, directory: Path | None = None) -> dict:
    """Require an intact, fully committed portfolio generation before reading."""
    base = paths.output if directory is None else directory
    completed = paths.artifact("complete", base)
    if not completed.exists():
        raise ValueError(
            "Incomplete portfolio result; run the explicit portfolio command."
        )
    manifest = json.loads(completed.read_text())
    if manifest.get("status") != "complete" or manifest.get("run_id") != paths.run_id:
        raise ValueError("Incompatible portfolio completion manifest.")
    from tcc_crypto.paths import PORTFOLIO_TABLES

    expected = {
        paths.artifact(name, base).name
        for name in ("configuration", "source", "execution", *PORTFOLIO_TABLES)
    }
    expected.update(
        metadata_path(paths.artifact(name, base)).name for name in PORTFOLIO_TABLES
    )
    if set(manifest["files"]) != expected:
        raise ValueError("Portfolio manifest has an unexpected artifact set.")
    for filename, digest in manifest["files"].items():
        path = base / filename
        if not path.exists() or file_sha256(path) != digest:
            raise ValueError(f"Incomplete or modified portfolio artifact: {filename}")
    return json.loads(paths.artifact("configuration", base).read_text())


def publish_portfolio(
    paths, directory: Path, signature: dict, source: dict, tables: dict, execution: dict
) -> None:
    """Stage a self-contained generation and commit its integrity manifest last."""
    from tcc_crypto.paths import PORTFOLIO_TABLES

    if set(tables) != set(PORTFOLIO_TABLES):
        raise ValueError("Portfolio tables differ from the required artifact set.")
    write_json(paths.artifact("configuration", directory), signature)
    write_json(paths.artifact("source", directory), source)
    write_json(paths.artifact("execution", directory), execution)
    for name, frame in tables.items():
        destination = paths.artifact(name, directory)
        # Source CSVs belong to another context. Their graph is checked explicitly
        # through source.json by the report loader, preserving the generic reader.
        write_table(frame, destination, context=signature)
        read_table(destination, context=signature, stage="portfolio")
    validate_portfolio_source(source)
    files = [p for p in directory.iterdir() if p.is_file()]
    write_json(
        paths.artifact("complete", directory),
        {
            "status": "complete",
            "run_id": paths.run_id,
            "files": {p.name: file_sha256(p) for p in files},
        },
    )
    validate_portfolio_bundle(paths, directory)


# A directory lock covers calculation and publication. Readers reject locked
# generations, including the short replacement interval during overwrite.
@contextmanager
def portfolio_transaction(paths, signature: dict, source: dict, *, overwrite=False):
    """Protect one output ID and restore its preceding generation on publish failure."""
    paths.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        paths.lock.mkdir()
    except FileExistsError as error:
        raise FileExistsError(f"Portfolio execution is locked: {paths.lock}") from error
    stage = paths.temporary(f"staging-{uuid4().hex}")
    backup = paths.temporary(f"backup-{uuid4().hex}")
    moved_old = False
    try:
        if paths.output.exists():
            if not overwrite:
                raise FileExistsError(
                    "Portfolio output exists; choose another run ID or use --overwrite."
                )
            previous = validate_portfolio_bundle(paths)
            previous_source = json.loads(paths.artifact("source").read_text())
            if previous != signature or previous_source != source:
                raise ValueError("Portfolio context changed; choose a new run ID.")
        stage.mkdir()
        yield stage
        validate_portfolio_bundle(paths, stage)
        if paths.output.exists():
            paths.output.rename(backup)
            moved_old = True
        try:
            stage.rename(paths.output)
        except BaseException:
            if moved_old:
                backup.rename(paths.output)
                moved_old = False
            raise
        if moved_old:
            shutil.rmtree(backup)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        paths.lock.rmdir()
