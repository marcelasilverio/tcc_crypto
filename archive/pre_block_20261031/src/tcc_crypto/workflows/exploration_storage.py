"""Persist and restore typed stages with configuration and source integrity."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from tcc_crypto.paths import ANALYSIS_INPUTS_NAME, ANALYSIS_RESULTS_NAME, metadata_path
from tcc_crypto.reporting.provenance import execution_metadata, file_sha256
from tcc_crypto.reporting.tables import (
    ensure_writable,
    read_table,
    write_json,
    write_table,
)
from tcc_crypto.workflows.exploration_calculations import ExplorationResult
from tcc_crypto.workflows.exploration_context import ExplorationContext
from tcc_crypto.workflows.exploration_inputs import ExplorationInputs


def _save(
    context: ExplorationContext,
    name: str,
    tables: dict,
    *,
    sources: tuple[Path, ...],
    extra: dict,
    overwrite: bool,
) -> Path:
    manifest = context.paths.outputs / name
    paths = {key: context.paths.table(key) for key in tables}
    ensure_writable(
        [manifest, *[item for p in paths.values() for item in (p, metadata_path(p))]],
        overwrite=overwrite,
    )
    for key, frame in tables.items():
        write_table(
            frame,
            paths[key],
            root=context.root,
            context=context.signature(),
            sources=list(sources),
            overwrite=overwrite,
        )
    write_json(
        manifest,
        {
            **execution_metadata(context.root),
            "context": context.signature(),
            "settings": asdict(context.settings),
            "tables": {key: str(p) for key, p in paths.items()},
            "sources": {str(p): file_sha256(p) for p in sources},
            **extra,
        },
    )
    return manifest


def _load(context: ExplorationContext, name: str) -> tuple[dict, dict]:
    path = context.paths.outputs / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {name}; run collect/load and save_inputs first, or calculate and save_results."
        )
    manifest = json.loads(path.read_text())
    if manifest["context"] != context.signature():
        raise ValueError("Saved execution uses a different configuration or universe.")
    for source, digest in manifest["sources"].items():
        if not Path(source).is_file() or file_sha256(Path(source)) != digest:
            raise ValueError(f"Stale or modified source: {source}")
    tables = {
        key: read_table(
            Path(path),
            context=context.signature(),
            stage="collect" if name == ANALYSIS_INPUTS_NAME else "calculate",
        )
        for key, path in manifest["tables"].items()
    }
    return manifest, tables


def save_inputs(
    context: ExplorationContext, inputs: ExplorationInputs, *, overwrite: bool = False
) -> Path:
    tables = {
        **{"input__" + k: v for k, v in inputs.values.items()},
        "input_diagnostics": inputs.diagnostics,
        **{"missing__" + k: v for k, v in inputs.missing_dates.items()},
    }
    return _save(
        context,
        ANALYSIS_INPUTS_NAME,
        tables,
        sources=(*context.configuration_files, *inputs.sources),
        extra={"raw": inputs.raw, "input_sources": [str(p) for p in inputs.sources]},
        overwrite=overwrite,
    )


def load_saved_inputs(context: ExplorationContext) -> ExplorationInputs:
    manifest, tables = _load(context, ANALYSIS_INPUTS_NAME)
    return ExplorationInputs(
        {
            k.removeprefix("input__"): v
            for k, v in tables.items()
            if k.startswith("input__")
        },
        tuple(Path(p) for p in manifest["input_sources"]),
        tables["input_diagnostics"],
        {
            k.removeprefix("missing__"): v
            for k, v in tables.items()
            if k.startswith("missing__")
        },
        manifest["raw"],
    )


def save_results(
    context: ExplorationContext, result: ExplorationResult, *, overwrite: bool = False
) -> Path:
    inputs = context.paths.outputs / ANALYSIS_INPUTS_NAME
    manifest, tables = _load(context, ANALYSIS_INPUTS_NAME)
    sources = [*context.configuration_files, inputs]
    for value in manifest["tables"].values():
        sources.extend((Path(value), metadata_path(Path(value))))
    return _save(
        context,
        ANALYSIS_RESULTS_NAME,
        result.tables,
        sources=tuple(sources),
        extra={
            "random_behavior": context.analysis == "future-high",
            "random_seed": getattr(context.settings, "random_seed", None),
        },
        overwrite=overwrite,
    )


def load_results(context: ExplorationContext) -> ExplorationResult:
    # Check upstream sources as well as the result tables.
    _load(context, ANALYSIS_INPUTS_NAME)
    return ExplorationResult(_load(context, ANALYSIS_RESULTS_NAME)[1])
