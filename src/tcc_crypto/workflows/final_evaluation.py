"""Coordinate final evaluation after loading and validating completed grid evidence."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Mapping, Sequence

import matplotlib.pyplot as plt
import pandas as pd

from tcc_crypto.modeling.final_config import (
    FinalEvaluationConfig,
    load_final_evaluation_config,
)
from tcc_crypto.modeling.final_evaluation import run_final_evaluation
from tcc_crypto.paths import (
    CONFIGURATION_SNAPSHOT_NAME,
    EXPERIMENT_OVERVIEW_NAME,
    FINAL_EVALUATION_CONFIG_PATH,
    RUN_METADATA_NAME,
    SVM_WORKBOOK_NAME,
    FinalArtifactPaths,
    metadata_path,
)
from tcc_crypto.reporting.final_evaluation import write_final_workbook
from tcc_crypto.reporting.provenance import execution_metadata, file_sha256
from tcc_crypto.reporting.tables import (
    ensure_writable,
    read_table,
    write_json,
    write_table,
)
from tcc_crypto.reporting.workbooks import configuration_table, write_workbook
from tcc_crypto.visualization.final_evaluation import final_evaluation_figures
from tcc_crypto.workflows.context import DailyContext, load_context
from tcc_crypto.workflows.daily_data import read_stage
from tcc_crypto.workflows.svm import result_table_paths


def _inputs(context: DailyContext, config_path: Path):
    if context.profile != "development":
        raise ValueError("Final evaluation requires a development search context.")
    config = load_final_evaluation_config(context.root, config_path)
    if config.grid_search_config != context.configuration_files[0]:
        raise ValueError(
            "Final evaluation and search must reference the same configuration."
        )
    paths = FinalArtifactPaths(context.root, config.evaluation_id, context.data.symbol)
    full = load_context(
        "experiment",
        root=context.root,
        symbol=context.data.symbol,
        config_path=context.configuration_files[0],
    )
    signature = json.loads(
        json.dumps(
            {
                "evaluation": asdict(config),
                "full_period": full.signature(),
                "development": context.signature(),
                "evaluation_config_sha256": file_sha256(context.root / config_path),
            },
            default=str,
        )
    )
    return config, paths, full, signature


def run(
    context: DailyContext,
    *,
    config_path: Path = FINAL_EVALUATION_CONFIG_PATH,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Evaluate frozen choices; never collect raw data or rerun a search."""
    config, paths, full, signature = _inputs(context, config_path)
    tables = paths.tables()
    figures = paths.figures()
    ensure_writable(
        [
            *(item for path in tables.values() for item in (path, metadata_path(path))),
            *figures.values(),
            paths.directory / SVM_WORKBOOK_NAME,
            paths.directory / RUN_METADATA_NAME,
            paths.directory / CONFIGURATION_SNAPSHOT_NAME,
        ],
        overwrite=overwrite,
    )
    development = read_stage(context, "dataset")
    dataset = read_stage(full, "dataset")
    pd.testing.assert_frame_equal(
        development,
        dataset.loc[context.data.sample_start_utc : context.data.sample_end_utc],
        check_freq=False,
        check_exact=True,
    )
    grid_paths = result_table_paths(context)
    grid_tables = {
        name: read_table(path, context=context.signature(), stage=context.kind)
        for name, path in grid_paths.items()
    }
    # Frozen choices are loaded before the evaluator sees any test labels.
    result = run_final_evaluation(
        dataset,
        symbol=context.data.symbol,
        selected=grid_tables["selected_configurations"],
        eligibility=grid_tables["eligibility"],
        grid_config=context.model,
        config=config,
        selection_config=context.features.feature_selection,
    )
    sources = [context.root / config_path, *context.configuration_files]
    for source in [
        *grid_paths.values(),
        context.paths.table("dataset"),
        full.paths.table("dataset"),
    ]:
        sources.extend((source, metadata_path(source)))
    for name, path in tables.items():
        write_table(
            getattr(result, name),
            path,
            root=context.root,
            context=signature,
            sources=sources,
            overwrite=overwrite,
        )
    write_json(
        paths.directory / CONFIGURATION_SNAPSHOT_NAME,
        {
            "effective_configuration": signature,
            "files": {
                str(path): json.loads(path.read_text())
                for path in [context.root / config_path, *context.configuration_files]
            },
        },
    )
    export(context, config_path=config_path, overwrite=overwrite)
    outputs = [
        *tables.values(),
        *figures.values(),
        paths.directory / SVM_WORKBOOK_NAME,
        paths.directory / CONFIGURATION_SNAPSHOT_NAME,
    ]
    write_json(
        paths.directory / RUN_METADATA_NAME,
        {
            **execution_metadata(context.root),
            "configuration": signature,
            "development_data_equality": "exact_full_period_subset",
            "frozen_search_checksums": {
                str(path): file_sha256(path) for path in grid_paths.values()
            },
            "test_used_for_hyperparameter_selection": False,
            "comparison_models": [
                "tuned_svc",
                "default_svc",
                "always_negative",
                "training_class_frequency",
            ],
            "universe_interpretation": "ex_post_fixed_2026_snapshot",
            "checksums": {str(path): file_sha256(path) for path in outputs},
        },
    )
    return {
        **tables,
        "workbook": paths.directory / SVM_WORKBOOK_NAME,
        **{f"{name}_figure": path for name, path in figures.items()},
    }


def export(
    context: DailyContext,
    *,
    config_path: Path = FINAL_EVALUATION_CONFIG_PATH,
    overwrite: bool = False,
) -> Path:
    """Reload final tables and regenerate workbook/figures without fitting models."""
    config, paths, _, signature = _inputs(context, config_path)
    output = paths.directory / SVM_WORKBOOK_NAME
    ensure_writable([output, *paths.figures().values()], overwrite=overwrite)
    tables = {
        name: read_table(path, context=signature, stage="final-test")
        for name, path in paths.tables().items()
    }
    write_final_workbook(output, tables, signature, overwrite=overwrite)
    _write_figures(context, config, paths, tables)
    _update_export_checksums(paths, [output, *paths.figures().values()])
    return output


def _write_figures(
    context: DailyContext,
    config: FinalEvaluationConfig,
    paths: FinalArtifactPaths,
    tables: Mapping[str, pd.DataFrame],
) -> None:
    figures = final_evaluation_figures(
        tables["roc"],
        tables["precision_recall"],
        symbol=context.data.symbol,
        start=config.feature_start_utc,
        end=config.feature_end_utc,
    )
    try:
        for name, figure in figures.items():
            figure.savefig(paths.figures()[name], dpi=140)
    finally:
        for figure in figures.values():
            plt.close(figure)


def _update_export_checksums(
    paths: FinalArtifactPaths, outputs: Sequence[Path]
) -> None:
    manifest = paths.directory / RUN_METADATA_NAME
    if manifest.exists():
        metadata = json.loads(manifest.read_text())
        metadata["checksums"].update({str(path): file_sha256(path) for path in outputs})
        write_json(manifest, metadata)


def export_figures(
    context: DailyContext,
    *,
    config_path: Path = FINAL_EVALUATION_CONFIG_PATH,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Regenerate only final figures from saved curve points, without fitting."""
    config, paths, _, signature = _inputs(context, config_path)
    ensure_writable(list(paths.figures().values()), overwrite=overwrite)
    tables = {
        name: read_table(paths.tables()[name], context=signature, stage="final-test")
        for name in ("roc", "precision_recall")
    }
    _write_figures(context, config, paths, tables)
    _update_export_checksums(paths, list(paths.figures().values()))
    return paths.figures()


def summarize_universe(
    contexts: Sequence[DailyContext],
    *,
    config_path: Path = FINAL_EVALUATION_CONFIG_PATH,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Aggregate completed assets without fitting, ranking or pooling model scores."""
    if not contexts:
        raise ValueError("Universe summary requires explicit asset contexts.")
    first = contexts[0]
    symbols = tuple(context.data.symbol for context in contexts)
    if symbols != first.model.candidate_symbols:
        raise ValueError("Universe summary requires all configured symbols in order.")
    config, _, _, _ = _inputs(first, config_path)
    destination = FinalArtifactPaths(first.root, config.evaluation_id, "universe")
    outputs = {name: destination.tables()[name] for name in ("metrics", "eligibility")}
    outputs["workbook"] = destination.directory / EXPERIMENT_OVERVIEW_NAME
    ensure_writable(
        [
            *(
                item
                for name, path in outputs.items()
                for item in (
                    [path] if name == "workbook" else [path, metadata_path(path)]
                )
            ),
            destination.directory / RUN_METADATA_NAME,
        ],
        overwrite=overwrite,
    )
    frames = {"metrics": [], "eligibility": []}
    artifacts, sources = [], [first.root / config_path]
    for context in contexts:
        if (
            context.root != first.root
            or context.configuration_files != first.configuration_files
        ):
            raise ValueError(
                "Universe contexts must share repository and configurations."
            )
        _, paths, _, signature = _inputs(context, config_path)
        manifest = paths.directory / RUN_METADATA_NAME
        saved = json.loads(manifest.read_text())
        if any(
            file_sha256(Path(path)) != checksum
            for path, checksum in saved["checksums"].items()
        ):
            raise ValueError(f"Modified final evidence for {context.data.symbol}.")
        sources.append(manifest)
        for name in frames:
            source = paths.tables()[name]
            frame = read_table(source, context=signature, stage="final-test")
            if not frame.empty:
                frames[name].append(frame)
            sources.extend((source, metadata_path(source)))
        artifacts.append(
            {
                "symbol": context.data.symbol,
                "grid_workbook": str(
                    context.paths.results("grid-search") / SVM_WORKBOOK_NAME
                ),
                "final_workbook": str(paths.directory / SVM_WORKBOOK_NAME),
                **{
                    f"{name}_figure": str(path)
                    for name, path in paths.figures().items()
                },
            }
        )
    tables = {
        name: pd.concat(items, ignore_index=True) if items else pd.DataFrame()
        for name, items in frames.items()
    }
    signature = json.loads(
        json.dumps(
            {
                "evaluation": asdict(config),
                "symbols": symbols,
                "configuration_sha256": file_sha256(first.root / config_path),
            },
            default=str,
        )
    )
    for name in frames:
        write_table(
            tables[name],
            outputs[name],
            root=first.root,
            context=signature,
            sources=sources,
            overwrite=overwrite,
        )
    metrics, eligibility = tables["metrics"], tables["eligibility"]
    summary = {
        "Evaluation": config.evaluation_id,
        "Requested assets": len(symbols),
        "Assets with final classifier comparisons": int(metrics.symbol.nunique())
        if not metrics.empty
        else 0,
        "Eligible development combinations": int(
            eligibility.status.eq("eligible").sum()
        ),
        "Feature start UTC": config.feature_start_utc,
        "Feature end UTC": config.feature_end_utc,
        "Attempted model observations": int(metrics.attempted_dates.sum())
        if not metrics.empty
        else 0,
        "Common successful model observations": int(metrics.evaluated_dates.sum())
        if not metrics.empty
        else 0,
        "Omitted model observations": int(metrics.omitted_dates.sum())
        if not metrics.empty
        else 0,
        "Interpretation": "Classifier evidence for an ex-post fixed universe; no portfolio returns; individual target/window scores are not pooled",
    }
    write_workbook(
        outputs["workbook"],
        {
            "Summary": configuration_table(summary),
            "Metrics": metrics,
            "Eligibility": eligibility,
            "Artifacts": pd.DataFrame(artifacts),
        },
        overwrite=overwrite,
    )
    write_json(
        destination.directory / RUN_METADATA_NAME,
        {
            **execution_metadata(first.root),
            "summary": summary,
            "configuration": signature,
            "checksums": {str(path): file_sha256(path) for path in outputs.values()},
        },
    )
    return outputs
