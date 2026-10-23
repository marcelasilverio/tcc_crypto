"""Train on prepared datasets, persist results, and independently export Excel."""

from __future__ import annotations

import json
from pathlib import Path

from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from tcc_crypto.data.config import DailyModelingDatasetConfig
from tcc_crypto.modeling.config import DailySvmGridSearchConfig
from tcc_crypto.modeling.grid_search import (
    DailySvmGridSearchResult,
    run_temporal_grid_search,
)
from tcc_crypto.modeling.pilot import DailySvmPilotResult, run_default_svc_rolling_pilot
from tcc_crypto.paths import (
    CONFIGURATION_SNAPSHOT_NAME,
    GRID_TABLE_NAMES,
    PILOT_TABLE_NAMES,
    RUN_METADATA_NAME,
    SVM_WORKBOOK_NAME,
    metadata_path,
)
from tcc_crypto.reporting.provenance import execution_metadata, file_sha256
from tcc_crypto.reporting.tables import (
    ensure_writable,
    read_table,
    write_json,
    write_table,
)
from tcc_crypto.reporting.workbooks import write_svm_workbook
from tcc_crypto.workflows.context import DailyContext
from tcc_crypto.workflows.daily_data import raw_source, read_stage


def result_table_paths(context: DailyContext) -> dict[str, Path]:
    if context.profile == "experiment":
        raise ValueError(
            "The experiment profile is preparation-only; use a separate modeling context."
        )
    names = PILOT_TABLE_NAMES if context.kind == "pilot" else GRID_TABLE_NAMES
    return {
        name: context.paths.results(context.kind) / filename
        for name, filename in names.items()
    }


def run(context: DailyContext, *, overwrite: bool = False) -> dict[str, Path]:
    """Execute only the selected model stage; require an existing valid dataset."""
    paths = result_table_paths(context)
    directory = context.paths.results(context.kind)
    ensure_writable(
        [item for path in paths.values() for item in (path, metadata_path(path))]
        + [
            directory / name
            for name in (
                SVM_WORKBOOK_NAME,
                RUN_METADATA_NAME,
                CONFIGURATION_SNAPSHOT_NAME,
            )
        ],
        overwrite=overwrite,
    )
    # Validate the complete upstream chain before any model fit.
    for stage in ("aligned", "features", "targets"):
        read_stage(context, stage)
    data = read_stage(context, "dataset")
    if context.profile == "pilot":
        if not isinstance(context.model, DailyModelingDatasetConfig):
            raise TypeError("Pilot requires a pilot configuration.")
        result = run_default_svc_rolling_pilot(
            data, selection_config=context.features.feature_selection
        )
    else:
        if not isinstance(context.model, DailySvmGridSearchConfig):
            raise TypeError("Grid search requires a development configuration.")
        result = run_temporal_grid_search(
            data,
            symbol=context.data.symbol,
            config=context.model,
            selection_config=context.features.feature_selection,
        )
    return persist_results(context, result, overwrite=overwrite)


def persist_results(
    context: DailyContext,
    result: DailySvmPilotResult | DailySvmGridSearchResult,
    *,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Persist an already calculated result, including notebook executions."""
    paths = result_table_paths(context)
    directory = context.paths.results(context.kind)
    ensure_writable(
        [item for path in paths.values() for item in (path, metadata_path(path))]
        + [
            directory / name
            for name in (
                SVM_WORKBOOK_NAME,
                RUN_METADATA_NAME,
                CONFIGURATION_SNAPSHOT_NAME,
            )
        ],
        overwrite=overwrite,
    )
    signature = context.signature()
    sources = [raw_source(context), *context.configuration_files]
    for stage in ("aligned", "features", "targets", "dataset"):
        source = context.paths.table(stage)
        sources.extend((source, metadata_path(source)))
    for name, path in paths.items():
        write_table(
            getattr(result, name),
            path,
            root=context.root,
            context=signature,
            sources=sources,
            overwrite=overwrite,
        )
    snapshot = {
        str(path): json.loads(path.read_text(encoding="utf-8"))
        for path in context.configuration_files
    }
    write_json(
        directory / CONFIGURATION_SNAPSHOT_NAME,
        {"files": snapshot, "effective_configuration": signature},
    )
    export_results(context, overwrite=overwrite)
    write_json(
        directory / RUN_METADATA_NAME,
        {
            **execution_metadata(context.root),
            "configuration": signature,
            "artifacts": context.paths.inventory(context.kind),
            "input_features": list(context.features.active_features),
            "scaler_parameters": StandardScaler().get_params(),
            "svc_default_parameters": SVC().get_params(),
            "final_test_feature_rows_used": False,
            "checksums": {
                str(path): file_sha256(path)
                for path in [
                    *paths.values(),
                    directory / SVM_WORKBOOK_NAME,
                    directory / CONFIGURATION_SNAPSHOT_NAME,
                ]
            },
        },
    )
    return paths


def export_results(context: DailyContext, *, overwrite: bool = False) -> Path:
    """Regenerate a results workbook without constructing or fitting a model."""
    tables = {
        name: read_table(path, context=context.signature(), stage=context.kind)
        for name, path in result_table_paths(context).items()
    }
    path = write_svm_workbook(
        context.paths.results(context.kind) / SVM_WORKBOOK_NAME,
        context.kind,
        tables,
        context.signature(),
        overwrite=overwrite,
    )

    manifest = context.paths.results(context.kind) / RUN_METADATA_NAME
    if manifest.exists():
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        metadata["checksums"][str(path)] = file_sha256(path)
        write_json(manifest, metadata)
    return path


def assess(context: DailyContext, *, overwrite: bool = False) -> Path:
    """Persist eligibility without evaluating any SVC candidate."""
    from tcc_crypto.modeling.eligibility import assess_symbol_eligibility

    if context.profile != "development":
        raise ValueError("Eligibility assessment requires the development profile.")
    data = read_stage(context, "dataset")
    eligibility = assess_symbol_eligibility(
        data, symbol=context.data.symbol, config=context.model
    )
    source = context.paths.table("dataset")
    return write_table(
        eligibility,
        result_table_paths(context)["eligibility"],
        root=context.root,
        context=context.signature(),
        sources=[
            source,
            metadata_path(source),
            raw_source(context),
            *context.configuration_files,
        ],
        overwrite=overwrite,
    )
