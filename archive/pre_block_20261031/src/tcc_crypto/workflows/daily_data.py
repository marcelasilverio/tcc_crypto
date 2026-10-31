"""Independent daily preparation stages and their explicit sequential workflow."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tcc_crypto.data.dataset import (
    assemble_dataset,
    calculation_period,
    sample_features,
)
from tcc_crypto.data.loaders import find_symbol_csv, load_daily_feature_input
from tcc_crypto.features.daily import calculate_daily_features
from tcc_crypto.paths import metadata_path
from tcc_crypto.reporting.tables import ensure_writable, read_table, write_table
from tcc_crypto.reporting.workbooks import write_dataset_workbook
from tcc_crypto.targets.daily import build_next_day_d0_targets
from tcc_crypto.workflows.context import DailyContext

STAGES = ("aligned", "features", "targets", "dataset")


def raw_source(context: DailyContext) -> Path:
    return find_symbol_csv(context.paths.raw.parent, context.data.symbol)


def read_stage(context: DailyContext, stage: str) -> pd.DataFrame:
    return read_table(
        context.paths.table(stage),
        context=context.signature(),
        stage="align" if stage == "aligned" else stage,
    )


def _save(
    context: DailyContext,
    stage: str,
    frame: pd.DataFrame,
    parents: tuple[str, ...],
    overwrite: bool,
) -> Path:
    sources = [raw_source(context), *context.configuration_files]
    for parent in parents:
        path = context.paths.table(parent)
        sources.extend((path, metadata_path(path)))
    return write_table(
        frame,
        context.paths.table(stage),
        root=context.root,
        context=context.signature(),
        sources=sources,
        overwrite=overwrite,
    )


def align(context: DailyContext, *, overwrite: bool = False) -> Path:
    """Fill only bounded internal gaps, then retain the original calculation span."""
    source = raw_source(context)
    aligned = load_daily_feature_input(source, fill_internal_gaps=True)
    aligned.attrs.update(
        first_observed_utc=aligned.index[0],
        last_observed_utc=aligned.index[-1],
        raw_path=str(source),
    )
    values = calculation_period(aligned, context.data)
    return _save(context, "aligned", values, (), overwrite)


def features(context: DailyContext, *, overwrite: bool = False) -> Path:
    """Calculate all 22 features and retain the leading warm-up rows."""
    aligned = read_stage(context, "aligned")
    calculated = calculate_daily_features(aligned)
    # The extra outcome day is needed by targets, never a development feature row.
    calculated = calculated.loc[: context.data.sample_end_utc].copy()
    return _save(context, "features", calculated, ("aligned",), overwrite)


def targets(context: DailyContext, *, overwrite: bool = False) -> Path:
    aligned = read_stage(context, "aligned")
    calculated = read_stage(context, "features")
    sample = sample_features(calculated, context.data)
    outcomes = build_next_day_d0_targets(
        aligned, sample.index, thresholds=context.data.target_thresholds
    )
    return _save(context, "targets", outcomes, ("aligned", "features"), overwrite)


def dataset(context: DailyContext, *, overwrite: bool = False) -> Path:
    path = context.paths.table("dataset")
    ensure_writable(
        [path, metadata_path(path), context.paths.dataset_workbook], overwrite=overwrite
    )
    tables = {
        stage: read_stage(context, stage)
        for stage in ("aligned", "features", "targets")
    }
    assembled = assemble_dataset(
        tables["features"], tables["targets"], tables["aligned"], context.data
    )
    result = _save(
        context, "dataset", assembled, ("aligned", "features", "targets"), overwrite
    )
    export_dataset(context, overwrite=overwrite)
    return result


def export_dataset(context: DailyContext, *, overwrite: bool = False) -> Path:
    """Read saved artifacts and export Excel without recalculating any stage."""
    tables = {stage: read_stage(context, stage) for stage in STAGES}
    summary = {
        "Context": context.data.context_id,
        "Symbol": context.data.symbol,
        "Profile": context.profile,
        "Timezone": "UTC",
        "Warm-up start": context.data.warmup_start_utc,
        "Feature period start": context.data.sample_start_utc,
        "Feature period end": context.data.sample_end_utc,
        "Imputed rows": int(tables["aligned"]["is_imputed"].sum()),
        "Feature count": 22,
        "Modeling rows": len(tables["dataset"]),
        "Missing data": "Forward-fill internal gaps only; preserve raw data",
        "Source": str(raw_source(context)),
        **context.paths.inventory(context.kind),
    }
    return write_dataset_workbook(
        context.paths.dataset_workbook, tables, summary, overwrite=overwrite
    )


def prepare(context: DailyContext, *, overwrite: bool = False) -> tuple[Path, ...]:
    """Run the four data stages explicitly; never collect or train implicitly."""
    outputs = [
        item
        for stage in STAGES
        for item in (
            context.paths.table(stage),
            metadata_path(context.paths.table(stage)),
        )
    ]
    ensure_writable([*outputs, context.paths.dataset_workbook], overwrite=overwrite)
    return tuple(
        stage(context, overwrite=overwrite)
        for stage in (align, features, targets, dataset)
    )
