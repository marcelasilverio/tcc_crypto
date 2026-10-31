"""Modeling: ranking."""

from __future__ import annotations

from typing import Mapping

import pandas as pd

PARAMETER_COLUMNS = ("kernel", "C", "gamma", "degree", "coef0", "class_weight")


def _parameter_values(parameters: Mapping[str, object]) -> dict[str, object]:
    return {column: parameters.get(column, pd.NA) for column in PARAMETER_COLUMNS}


def _aggregate_candidate_results(fold_results: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_columns = ["symbol", "target", "window_size", "candidate_order"]
    for keys, group in fold_results.groupby(group_columns, sort=False, dropna=False):
        symbol, target, window_size, candidate_order = keys
        first = group.iloc[0]
        row: dict[str, object] = {
            "symbol": symbol,
            "target": target,
            "window_size": int(window_size),
            "candidate_order": int(candidate_order),
            **{column: first[column] for column in PARAMETER_COLUMNS},
            "successful_fold_count": int((group["status"] == "ok").sum()),
            "failed_fold_count": int((group["status"] != "ok").sum()),
        }
        for metric in (
            "accuracy",
            "precision",
            "recall",
            "f1",
            "balanced_accuracy",
            "roc_auc",
            "average_precision",
        ):
            row[f"mean_{metric}"] = float(group[metric].mean())
        row["f1_standard_deviation"] = float(group["f1"].std(ddof=0))
        row["mean_fit_seconds"] = float(group["fit_seconds"].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def select_best_candidate(candidates: pd.DataFrame, *, tolerance: float) -> pd.Series:
    """Select one candidate using the approved deterministic tie-break rule."""
    ranked = rank_candidates(candidates, tolerance=tolerance)
    return ranked.loc[ranked["selection_rank"] == 1].iloc[0]


def rank_candidates(candidates: pd.DataFrame, *, tolerance: float) -> pd.DataFrame:
    """Rank candidates with F1 tolerance and the approved secondary ordering."""
    required = {
        "mean_f1",
        "mean_precision",
        "f1_standard_deviation",
        "mean_roc_auc",
        "kernel",
        "C",
        "candidate_order",
        "failed_fold_count",
    }
    missing = required.difference(candidates.columns)
    if missing:
        raise ValueError(f"Candidate table is missing columns: {sorted(missing)}.")
    valid = candidates.loc[
        (candidates["failed_fold_count"] == 0) & candidates["mean_f1"].notna()
    ].copy()
    if valid.empty:
        raise ValueError("No candidate completed every temporal fold.")
    kernel_order = {"linear": 0, "rbf": 1, "poly": 2}
    ranked_indexes: list[object] = []
    remaining = valid.copy()
    while not remaining.empty:
        best_f1 = float(remaining["mean_f1"].max())
        tied = remaining.loc[remaining["mean_f1"] >= best_f1 - tolerance].copy()
        tied["_precision"] = tied["mean_precision"].fillna(float("-inf"))
        tied["_f1_std"] = tied["f1_standard_deviation"].fillna(float("inf"))
        tied["_roc_auc"] = tied["mean_roc_auc"].fillna(float("-inf"))
        tied["_kernel"] = tied["kernel"].map(kernel_order).fillna(len(kernel_order))
        tied = tied.sort_values(
            [
                "_precision",
                "_f1_std",
                "_roc_auc",
                "_kernel",
                "C",
                "candidate_order",
            ],
            ascending=[False, True, False, True, True, True],
            kind="stable",
        )
        ranked_indexes.extend(tied.index)
        remaining = remaining.drop(index=tied.index)

    invalid = candidates.drop(index=valid.index).sort_values(
        "candidate_order", kind="stable"
    )
    ranked_indexes.extend(invalid.index)
    ranked = candidates.loc[ranked_indexes].copy()
    ranked.insert(4, "selection_rank", range(1, len(ranked) + 1))
    return ranked
