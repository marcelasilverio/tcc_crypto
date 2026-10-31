"""Typed CSV artifacts with configuration and upstream-integrity checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping
from uuid import uuid4

import numpy as np
import pandas as pd

from tcc_crypto.paths import metadata_path
from tcc_crypto.reporting.provenance import execution_metadata, file_sha256

SCHEMA_VERSION = 1
NULL_TOKEN = "__TCC_NULL__"


def ensure_writable(paths: list[Path], *, overwrite: bool) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing and not overwrite:
        raise FileExistsError(
            "Outputs already exist; use --overwrite: " + ", ".join(existing)
        )


def write_json(path: Path, payload: object) -> None:
    """Replace a JSON file atomically after its caller checks overwrite policy."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _object_schema(frame: pd.DataFrame) -> dict[str, dict[str, list[int]]]:
    """CSV has no scalar type tags; retain tags for non-string object cells."""
    schema = {}
    for column in frame.select_dtypes(include=["object"]):
        kinds = {}
        for position, value in enumerate(frame[column]):
            if isinstance(value, np.generic):
                value = value.item()
            if value is pd.NA:
                kind = "pd.NA"
            elif value is None:
                kind = "None"
            elif isinstance(value, str):
                continue
            elif isinstance(value, (bool, int, float)):
                kind = type(value).__name__
            else:
                raise TypeError(
                    f"Unsupported object scalar in {column}: {type(value).__name__}"
                )
            kinds.setdefault(kind, []).append(position)
        schema[column] = kinds
    return schema


def _restore_objects(frame: pd.DataFrame, schema: dict) -> None:
    converters = {
        "pd.NA": lambda value: pd.NA,
        "None": lambda value: None,
        "int": int,
        "float": float,
        "bool": lambda value: str(value) == "True",
    }
    for column, kinds in schema.items():
        for kind, positions in kinds.items():
            for position in positions:
                frame.iat[position, frame.columns.get_loc(column)] = converters[kind](
                    frame.iloc[position][column]
                )


def write_table(
    frame: pd.DataFrame,
    path: Path,
    *,
    root: Path,
    context: Mapping[str, object],
    sources: list[Path],
    overwrite: bool = False,
) -> Path:
    """Persist the full table, including index, nullable dtypes, and provenance."""
    sidecar = metadata_path(path)
    ensure_writable([path, sidecar], overwrite=overwrite)
    if frame.columns.has_duplicates:
        raise ValueError("Artifact columns must be unique.")
    for column in frame.select_dtypes(include=["object", "string"]):
        if frame[column].eq(NULL_TOKEN).any():
            raise ValueError("Artifact contains the reserved CSV null token.")
    object_schema = _object_schema(frame)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        frame.to_csv(
            temporary,
            index=True,
            na_rep=NULL_TOKEN,
            compression={"method": "gzip", "mtime": 0}
            if path.suffix == ".gz"
            else None,
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    index = {
        "name": frame.index.name,
        "dtype": str(frame.index.dtype),
        "range": isinstance(frame.index, pd.RangeIndex),
        "frequency": getattr(frame.index, "freqstr", None),
    }
    metadata = {
        **execution_metadata(root),
        "schema_version": SCHEMA_VERSION,
        "context": dict(context),
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "row_count": len(frame),
        "columns": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
        "column_order": list(frame.columns),
        "index": index,
        "columns_range": isinstance(frame.columns, pd.RangeIndex),
        "object_schema": object_schema,
        "attributes": frame.attrs,
        "sources": {str(source.resolve()): file_sha256(source) for source in sources},
    }
    write_json(sidecar, metadata)
    return path


def read_table(
    path: Path, *, context: Mapping[str, object], stage: str
) -> pd.DataFrame:
    """Reject missing, modified, or stale inputs before restoring their schema."""
    sidecar = metadata_path(path)
    if not path.exists() or not sidecar.exists():
        raise FileNotFoundError(
            f"Missing {stage} artifact or metadata: {path}. Run '{stage}' first."
        )
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    if metadata["schema_version"] != SCHEMA_VERSION or metadata["context"] != dict(
        context
    ):
        raise ValueError(
            f"Incompatible {stage} configuration: {path}. Rebuild this stage."
        )
    if metadata["sha256"] != file_sha256(path):
        raise ValueError(f"Modified {stage} artifact: {path}. Rebuild this stage.")
    for source, checksum in metadata["sources"].items():
        if not Path(source).exists() or file_sha256(Path(source)) != checksum:
            raise ValueError(f"Stale {stage} input: {source}. Rebuild this stage.")
    dtypes = metadata["columns"]
    scalar_types = {
        name: dtype
        for name, dtype in dtypes.items()
        if not dtype.startswith("datetime64")
    }
    frame = pd.read_csv(
        path,
        index_col=0,
        dtype=scalar_types,
        keep_default_na=False,
        na_values=[NULL_TOKEN],
        float_precision="round_trip",
    )
    for name, dtype in dtypes.items():
        if dtype.startswith("datetime64"):
            frame[name] = pd.to_datetime(frame[name], utc="UTC" in dtype)
    _restore_objects(frame, metadata.get("object_schema", {}))
    if metadata.get("columns_range"):
        frame.columns = pd.RangeIndex(len(frame.columns))
    index = metadata["index"]
    if index["dtype"].startswith("datetime64"):
        frame.index = pd.DatetimeIndex(
            pd.to_datetime(frame.index, utc="UTC" in index["dtype"])
        )
    elif index["range"]:
        frame.index = pd.RangeIndex(len(frame))
    else:
        frame.index = frame.index.astype(index["dtype"])
    if index.get("frequency") is not None:
        frame.index = pd.DatetimeIndex(frame.index, freq=index["frequency"])
    frame.index.name = index["name"]
    if (
        list(frame.columns) != metadata["column_order"]
        or len(frame) != metadata["row_count"]
    ):
        raise ValueError(f"Artifact schema differs from metadata: {path}")
    frame.attrs = metadata.get("attributes", {})
    for key in ("first_observed_utc", "last_observed_utc"):
        if key in frame.attrs:
            frame.attrs[key] = pd.Timestamp(frame.attrs[key])
    return frame
