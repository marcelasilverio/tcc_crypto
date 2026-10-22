"""Classifier diagnostics; these figures do not represent portfolio performance."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def target_balance(dataset: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "target": target,
                "negative": int(dataset[target].eq(0).sum()),
                "positive": int(dataset[target].eq(1).sum()),
                "positive_rate": float(dataset[target].dropna().eq(1).mean()),
            }
            for target in ("target_2pct", "target_3pct", "target_4pct")
        ]
    ).set_index("target")


def plot_target_balance(balance: pd.DataFrame) -> plt.Figure:
    axis = balance[["negative", "positive"]].plot.bar(figsize=(8, 4), rot=0)
    axis.set_title("Daily target-class balance")
    axis.set_xlabel("Binary target")
    axis.set_ylabel("Daily observations")
    axis.figure.tight_layout()
    return axis.figure


def plot_model_metrics(table: pd.DataFrame, *, kind: str) -> plt.Figure:
    if table.empty:
        figure, axis = plt.subplots()
        axis.text(0.5, 0.5, "No eligible classifier results", ha="center")
        axis.set_axis_off()
        return figure
    if kind == "pilot":
        columns = [
            "out_of_sample_accuracy",
            "out_of_sample_precision",
            "out_of_sample_recall",
            "out_of_sample_f1",
        ]
        values = table.set_index(["target", "window_size"])[columns].rename(
            columns={
                name: name.removeprefix("out_of_sample_").capitalize()
                for name in columns
            }
        )
        values.index = [
            f"{target.removeprefix('target_').replace('pct', '%')} / {window}"
            for target, window in values.index
        ]
        axis = values.plot.bar(figsize=(13, 5), rot=45)
        axis.set_title("Default SVC out-of-sample classification metrics")
        axis.set_xlabel("Target and rolling training-window size")
        axis.set_ylabel("Metric value")
    else:
        axis = table.pivot(
            index="window_size", columns="target", values="mean_f1"
        ).plot(marker="o", figsize=(8, 4))
        axis.set_title("Selected candidate mean development-validation F1")
        axis.set_xlabel("Training-window size (daily observations)")
        axis.set_ylabel("Mean validation F1")
        axis.set_xticks(sorted(table["window_size"].unique()))
    axis.set_ylim(0, 1)
    axis.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
    axis.figure.tight_layout()
    return axis.figure


def plot_split_boundaries(boundaries: pd.DataFrame) -> plt.Figure:
    figure, axis = plt.subplots(figsize=(10, 4))
    for row in boundaries.itertuples():
        axis.plot(
            [row.training_start_utc, row.training_end_utc],
            [row.fold, row.fold],
            linewidth=7,
            color="#4472C4",
        )
        axis.plot(
            [row.validation_start_utc, row.validation_end_utc],
            [row.fold, row.fold],
            linewidth=7,
            color="#ED7D31",
        )
    axis.set_title("Chronological training and validation windows; gap excluded")
    axis.set_xlabel("Observation date (UTC)")
    axis.set_ylabel("Fold")
    figure.tight_layout()
    return figure
