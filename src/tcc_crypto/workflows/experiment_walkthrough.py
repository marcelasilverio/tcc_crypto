"""Explicit execution and saved-stage inspection for the complete daily walkthrough."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from tcc_crypto.paths import (
    FINAL_EVALUATION_CONFIG_PATH,
    SVM_WORKBOOK_NAME,
    metadata_path,
)
from tcc_crypto.reporting.tables import ensure_writable, read_table, write_table
from tcc_crypto.reporting.workbooks import configuration_table
from tcc_crypto.workflows import (
    daily_data,
    daily_review,
    experiment_review,
    final_evaluation,
    svm,
)
from tcc_crypto.workflows.context import DailyContext


def _check(context: DailyContext, mode: str) -> None:
    if mode not in ("run", "load"):
        raise ValueError("Mode must be 'run' or 'load'.")
    if context.run_id is None:
        raise ValueError("The walkthrough requires an explicit run ID.")


def protocol(context: DailyContext) -> pd.DataFrame:
    config, _, full, _ = final_evaluation._inputs(context, FINAL_EVALUATION_CONFIG_PATH)
    return configuration_table(
        {
            "Symbol": context.data.symbol,
            "Run ID": context.run_id,
            "Development": asdict(context.data),
            "Full preparation": asdict(full.data),
            "Final evaluation": asdict(config),
            "Candidates per search": context.model.candidate_count,
            "Targets": context.model.targets,
            "Training windows": context.model.training_window_sizes,
            "Validation folds": context.model.n_splits,
            "Validation rows per fold": context.model.test_size,
            "Gap observations": context.model.gap,
        }
    )


def paths(context: DailyContext) -> pd.DataFrame:
    _, final, full, _ = final_evaluation._inputs(context, FINAL_EVALUATION_CONFIG_PATH)
    entries = {
        f"development.{name}": path
        for name, path in context.paths.inventory(context.kind).items()
    }
    entries.update(
        {f"full.{name}": path for name, path in full.paths.inventory(full.kind).items()}
    )
    entries.update(
        {f"final.{name}": str(path) for name, path in final.tables().items()}
    )
    entries.update(
        {f"final.{name}_figure": str(path) for name, path in final.figures().items()}
    )
    entries["final.workbook"] = str(final.directory / SVM_WORKBOOK_NAME)
    entries["training_review"] = str(final.training_metrics)
    entries.update(
        {
            f"inspection.{name}": str(path)
            for name, path in context.paths.window_inspection().items()
        }
    )
    return configuration_table(entries)


def preparation(
    context: DailyContext, stage: str, *, mode: str, overwrite: bool = False
) -> pd.DataFrame:
    _check(context, mode)
    actions = {
        "aligned": daily_data.align,
        "features": daily_data.features,
        "targets": daily_data.targets,
        "dataset": daily_data.dataset,
    }
    if stage not in actions:
        raise ValueError(f"Unknown preparation stage: {stage}")
    if mode == "run":
        actions[stage](context, overwrite=overwrite)
    return daily_data.read_stage(context, stage)


def imputed_rows(aligned: pd.DataFrame) -> pd.DataFrame:
    return aligned.loc[aligned.is_imputed].copy()


def target_examples(targets: pd.DataFrame, *, rows: int = 8) -> pd.DataFrame:
    return targets.reindex(
        columns=[
            "target_date_utc",
            "next_day_open",
            "next_day_high",
            "next_day_d0",
            "target_2pct",
            "target_3pct",
            "target_4pct",
            "target_is_imputed",
        ]
    ).head(rows)


def compare_datasets(development: DailyContext, full: DailyContext) -> pd.DataFrame:
    if development.run_id != full.run_id or development.data.symbol != full.data.symbol:
        raise ValueError("Dataset comparison requires the same run and symbol.")
    first = daily_data.read_stage(development, "dataset")
    second = daily_data.read_stage(full, "dataset")
    pd.testing.assert_frame_equal(
        first,
        second.loc[development.data.sample_start_utc : development.data.sample_end_utc],
        check_exact=True,
        check_freq=False,
    )
    return configuration_table(
        {
            "Development rows": len(first),
            "Full rows": len(second),
            "Development equals full-period slice": True,
        }
    )


def inspect_training(
    context: DailyContext, *, mode: str, overwrite: bool = False
) -> dict[str, pd.DataFrame]:
    """Persist one approved first-fold example; load never fits preprocessing."""
    _check(context, mode)
    destinations = context.paths.window_inspection()
    if mode == "run":
        ensure_writable(
            [item for p in destinations.values() for item in (p, metadata_path(p))],
            overwrite=overwrite,
        )
        window = daily_review.inspect_window(context)
        for name, path in destinations.items():
            write_table(
                getattr(window, name),
                path,
                root=context.root,
                context=context.signature(),
                sources=[
                    context.paths.table("dataset"),
                    metadata_path(context.paths.table("dataset")),
                    *context.configuration_files,
                ],
                overwrite=overwrite,
            )
    return {
        name: read_table(path, context=context.signature(), stage="training inspection")
        for name, path in destinations.items()
    }


def inspection_table(inspection: dict[str, pd.DataFrame], name: str) -> pd.DataFrame:
    return inspection[name]


def grid_search(context: DailyContext, *, mode: str, overwrite: bool = False):
    _check(context, mode)
    if mode == "run":
        svm.run(context, overwrite=overwrite)
    return daily_review.load_model(context)


def final_test(
    context: DailyContext, *, mode: str, overwrite: bool = False
) -> experiment_review.ExperimentReview:
    _check(context, mode)
    if mode == "run":
        final_evaluation.run(context, overwrite=overwrite)
    return experiment_review.load_results(
        root=context.root, symbols=(context.data.symbol,), run_id=context.run_id
    )


def training_review(
    context: DailyContext, *, mode: str, overwrite: bool = False
) -> pd.DataFrame:
    _check(context, mode)
    if mode == "run":
        return experiment_review.reconstruct_in_sample(
            root=context.root,
            symbols=(context.data.symbol,),
            run_id=context.run_id,
            overwrite=overwrite,
        )
    _, paths, _, _ = final_evaluation._inputs(context, FINAL_EVALUATION_CONFIG_PATH)
    return read_table(
        paths.training_metrics, context=context.signature(), stage="training-review"
    )


def final_observation(
    context: DailyContext, *, feature_date: str, target: str, window_size: int
) -> pd.DataFrame:
    _, paths, _, signature = final_evaluation._inputs(
        context, FINAL_EVALUATION_CONFIG_PATH
    )
    data = read_table(
        paths.tables()["predictions"], context=signature, stage="final-test"
    )
    date = pd.Timestamp(feature_date)
    date = date.tz_localize("UTC") if date.tzinfo is None else date.tz_convert("UTC")
    chosen = data.loc[
        data.feature_date_utc.eq(date)
        & data.target.eq(target)
        & data.window_size.eq(window_size)
    ]
    return chosen.reindex(
        columns=[
            "model",
            "feature_date_utc",
            "target_date_utc",
            "training_start_utc",
            "training_end_utc",
            "gap_date_utc",
            "training_rows",
            "selected_features",
            "scaler_mean",
            "scaler_scale",
            "actual",
            "prediction",
            "status",
        ]
    )


def export_saved(
    context: DailyContext, *, overwrite: bool = False, regenerate: bool = False
) -> pd.DataFrame:
    _, _, full, _ = final_evaluation._inputs(context, FINAL_EVALUATION_CONFIG_PATH)
    if not regenerate:
        return paths(context)
    outputs = {
        "development": daily_data.export_dataset(context, overwrite=overwrite),
        "full": daily_data.export_dataset(full, overwrite=overwrite),
        "grid": svm.export_results(context, overwrite=overwrite),
        "final": final_evaluation.export(context, overwrite=overwrite),
    }
    return configuration_table(outputs)
