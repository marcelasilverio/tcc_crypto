"""Read-only summaries of development validation and final classifier evidence."""

from __future__ import annotations

import pandas as pd

METRICS = (
    "accuracy",
    "precision",
    "recall",
    "f1",
    "balanced_accuracy",
    "roc_auc",
    "average_precision",
)
KEYS = ["symbol", "target", "window_size"]


def phase_definitions() -> pd.DataFrame:
    """Do not relabel model-selection validation as training performance."""
    return pd.DataFrame(
        [
            {
                "phase": "Training / in sample",
                "observations": "Rows passed to fit",
                "interpretation": "Mean resubstitution score of the selected development folds; reconstructed later",
            },
            {
                "phase": "Development validation",
                "observations": "Three later 60-day folds",
                "interpretation": "Used to select parameters; not untouched final OOS",
            },
            {
                "phase": "Final out of sample",
                "observations": "2025-01-01 to 2026-08-31 UTC",
                "interpretation": "Frozen parameters; daily rolling refits on past rows",
            },
        ]
    )


def asset_overview(eligibility: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    """Preserve exclusions and partial eligibility without pooling performance."""
    rows = []
    for symbol, entries in eligibility.groupby("symbol", sort=False):
        final = metrics.loc[metrics.symbol.eq(symbol) & metrics.model.eq("tuned_svc")]
        reasons = sorted(
            set(entries.loc[entries.status.ne("eligible"), "reason"].dropna())
        )
        rows.append(
            {
                "symbol": symbol,
                "eligible_combinations": int(entries.status.eq("eligible").sum()),
                "requested_combinations": len(entries),
                "final_combinations": len(final),
                "evaluated_combination_dates": int(final.evaluated_dates.sum()),
                "omitted_combination_dates": int(final.omitted_dates.sum()),
                "exclusion_reasons": "; ".join(reasons),
            }
        )
    return pd.DataFrame(rows)


def development_vs_final(
    selected: pd.DataFrame,
    metrics: pd.DataFrame,
    training: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compare each frozen choice, keeping the two scoring protocols explicit."""
    columns = [*KEYS, "kernel", "C", "successful_fold_count"]
    columns += [f"mean_{name}" for name in METRICS]
    development = selected.reindex(columns=columns).rename(
        columns={f"mean_{name}": f"validation_{name}" for name in METRICS}
    )
    final = (
        metrics.loc[metrics.model.eq("tuned_svc")]
        .reindex(
            columns=[
                *KEYS,
                *METRICS,
                "evaluated_dates",
                "omitted_dates",
                "actual_positive",
                "actual_negative",
            ]
        )
        .rename(columns={name: f"final_{name}" for name in METRICS})
    )
    table = development.merge(final, on=KEYS, how="outer", validate="one_to_one")
    table.insert(3, "in_sample_status", "Not recorded")
    if training is not None and not training.empty:
        averages = training.groupby(KEYS, as_index=False)[
            [f"in_sample_{name}" for name in METRICS]
        ].mean()
        table = table.merge(averages, on=KEYS, how="left", validate="one_to_one")
        table.loc[table.in_sample_f1.notna(), "in_sample_status"] = (
            "Reconstructed; validation reproduced"
        )
    table["final_positive_rate"] = table.actual_positive / table.evaluated_dates
    return table


def selected_folds(folds: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    """Keep only the development folds of the already-selected candidates."""
    if selected.empty:
        return folds.iloc[0:0].copy()
    return folds.merge(
        selected[[*KEYS, "candidate_order"]],
        on=[*KEYS, "candidate_order"],
        how="inner",
        validate="many_to_one",
    ).sort_values(["target", "window_size", "fold"])
