"""Classifier ROC and precision-recall curves, separate from financial returns."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure


def final_evaluation_figures(
    roc: pd.DataFrame,
    precision_recall: pd.DataFrame,
    *,
    symbol: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Figure]:
    """Build comparable target/window panels from persisted curve points."""
    figures = {}
    for kind, table in (("roc", roc), ("precision_recall", precision_recall)):
        figure, axes = plt.subplots(3, 3, figsize=(15, 12), squeeze=False)
        for row, target in enumerate(("target_2pct", "target_3pct", "target_4pct")):
            for column, window in enumerate((60, 75, 90)):
                axis = axes[row, column]
                subset = table.loc[
                    table.target.eq(target) & table.window_size.eq(window)
                ]
                if kind == "roc":
                    x, y = "false_positive_rate", "true_positive_rate"
                    axis.plot(
                        [0, 1], [0, 1], linestyle="--", color="gray", linewidth=0.8
                    )
                    axis.set(xlabel="False positive rate", ylabel="True positive rate")
                else:
                    x, y = "recall", "precision"
                    axis.set(xlabel="Recall", ylabel="Precision")
                for model, values in subset.groupby("model", sort=False):
                    axis.plot(
                        values[x],
                        values[y],
                        label=model.replace("_", " "),
                        drawstyle="steps-post"
                        if kind == "precision_recall"
                        else "default",
                    )
                if subset.empty:
                    axis.text(0.5, 0.5, "No defined curve", ha="center", va="center")
                else:
                    axis.legend(fontsize=7, loc="best")
                axis.set(
                    title=f"{target}: {window} training observations",
                    xlim=(0, 1),
                    ylim=(0, 1),
                )
                axis.grid(alpha=0.2)
        title = "ROC" if kind == "roc" else "Precision-recall"
        figure.suptitle(
            f"{symbol} final {title} curves, {start.date()} to {end.date()} UTC\nCommon successful dates; fixed ex-post candidate universe"
        )
        figure.tight_layout(rect=(0, 0, 1, 0.95))
        figures[kind] = figure
    return figures
