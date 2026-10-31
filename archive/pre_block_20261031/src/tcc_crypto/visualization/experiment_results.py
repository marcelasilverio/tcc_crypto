"""Supervisor-facing tables and figures; no collection, preprocessing or fitting."""

from __future__ import annotations

from io import BytesIO

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Image, Markdown, display

from tcc_crypto.visualization.final_evaluation import final_evaluation_figures

LABELS = {
    "in_sample": "Training / in sample (fold mean)",
    "validation": "Development validation (fold mean)",
    "final": "Final OOS (matched daily predictions)",
}
COLORS = ("#4472C4", "#ED7D31", "#548235")


def comparison_table(comparison: pd.DataFrame):
    """Render every combination, without selecting winners using final results."""
    if comparison.empty:
        return comparison
    columns = ["target", "window_size"]
    columns += [
        f"{phase}_{metric}"
        for phase in LABELS
        for metric in ("accuracy", "precision", "recall", "f1")
    ]
    columns += ["evaluated_dates", "omitted_dates", "final_positive_rate"]
    table = comparison.reindex(columns=columns).set_index(["target", "window_size"])
    table.columns = pd.MultiIndex.from_tuples(
        [
            ("Training IS", name.removeprefix("in_sample_").replace("_", " ").title())
            if name.startswith("in_sample_")
            else ("Validation", name.removeprefix("validation_").title())
            if name.startswith("validation_")
            else ("Final OOS", name.removeprefix("final_").title())
            if name.startswith("final_") and name != "final_positive_rate"
            else ("Coverage", name.replace("_", " ").title())
            for name in table.columns
        ]
    )
    return table.style.format(precision=3, na_rep="Not recorded").set_caption(
        "Selected SVC: training and validation fold means versus final matched-date metrics. "
        "Metric values are fractions (0–1); window size is daily observations."
    )


def all_asset_sections(comparison: pd.DataFrame, overview: pd.DataFrame) -> None:
    """Display every configured coin, including all excluded coins, in source order."""
    for row in overview.itertuples(index=False):
        display(Markdown(f"### {row.symbol}"))
        display(
            Markdown(
                f"**Eligible combinations:** {row.eligible_combinations}/{row.requested_combinations}. "
                f"**Evaluated combination-dates:** {row.evaluated_combination_dates:,}. "
                f"**Omitted combination-dates:** {row.omitted_combination_dates:,}. "
                + (
                    f"**Exclusions:** {row.exclusion_reasons}."
                    if row.exclusion_reasons
                    else ""
                )
            )
        )
        selected = comparison.loc[comparison.symbol.eq(row.symbol)]
        if not selected.empty:
            display(comparison_table(selected))


def phase_comparison(comparison: pd.DataFrame, *, symbol: str) -> plt.Figure:
    """Keep all nine target/window choices visible rather than optimize on OOS."""
    if comparison.empty:
        figure, axis = plt.subplots(figsize=(9, 3))
        axis.text(0.05, 0.5, f"{symbol}: no eligible selected SVC; see exclusions.")
        axis.set_axis_off()
        plt.close(figure)
        return figure
    figure, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True)
    labels = [
        f"{r.target.replace('target_', '').replace('pct', '%')} / {r.window_size}d"
        for r in comparison.itertuples(index=False)
    ]
    for axis, metric in zip(axes, ("precision", "recall", "f1"), strict=True):
        for offset, (phase, title) in enumerate(LABELS.items()):
            column = f"{phase}_{metric}"
            if column in comparison:
                positions = [i + (offset - 1) * 0.25 for i in range(len(comparison))]
                axis.bar(
                    positions,
                    comparison[column],
                    width=0.24,
                    label=title,
                    color=COLORS[offset],
                )
        axis.set_ylim(0, 1)
        axis.set_ylabel(f"{metric.capitalize()} (0–1)")
        axis.grid(axis="y", alpha=0.2)
    axes[0].legend(loc="upper left", bbox_to_anchor=(0, 1.3), ncol=1)
    axes[-1].set_xticks(range(len(labels)), labels, rotation=35, ha="right")
    axes[-1].set_xlabel("Target threshold / training-window size")
    figure.suptitle(
        f"{symbol} — selected SVC across phases\n"
        "Development-fold means versus frozen-parameter final walk-forward",
        y=1.01,
    )
    figure.tight_layout()
    plt.close(figure)
    return figure


def baseline_table(metrics: pd.DataFrame):
    columns = [
        "target",
        "window_size",
        "model",
        "evaluated_dates",
        "omitted_dates",
        "actual_positive",
        "actual_negative",
        "predicted_positive",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "balanced_accuracy",
        "roc_auc",
        "average_precision",
        "metric_diagnostic",
    ]
    table = metrics.reindex(columns=columns).set_index(
        ["target", "window_size", "model"]
    )
    return table.style.format(precision=3, na_rep="Undefined").set_caption(
        "Final OOS: all four classifiers evaluated on identical valid dates within each target/window. "
        "Metrics are fractions; counts are daily observations."
    )


def confusion_figure(
    metrics: pd.DataFrame, *, symbol: str, target: str, window_size: int
) -> plt.Figure:
    selected = metrics.loc[
        metrics.target.eq(target) & metrics.window_size.eq(window_size)
    ]
    figure, axes = plt.subplots(1, 4, figsize=(15, 4))
    for axis in axes:
        axis.set_axis_off()
    for axis, row in zip(axes, selected.itertuples(index=False)):
        axis.set_axis_on()
        values = [
            [row.true_negative, row.false_positive],
            [row.false_negative, row.true_positive],
        ]
        axis.imshow(values, cmap="Blues", vmin=0, vmax=max(row.evaluated_dates, 1))
        for y in range(2):
            for x in range(2):
                axis.text(
                    x,
                    y,
                    str(int(values[y][x])),
                    ha="center",
                    va="center",
                    color="white"
                    if values[y][x] > row.evaluated_dates / 2
                    else "black",
                )
        axis.set_xticks([0, 1], ["0", "1"])
        axis.set_yticks([0, 1], ["0", "1"])
        axis.set_xlabel("Predicted class")
        axis.set_ylabel("Actual class")
        axis.set_title(
            f"{row.model}\nn={row.evaluated_dates}; omitted={row.omitted_dates}",
            fontsize=10,
        )
    if selected.empty:
        axes[0].text(
            0.1, 0.5, "This target/window is ineligible; see eligibility diagnostics."
        )
    figure.suptitle(
        f"{symbol} — {target}, {window_size}d — final OOS confusion counts\n"
        "Matched valid dates; UTC daily observations"
    )
    figure.tight_layout(rect=(0, 0, 1, 0.84))
    plt.close(figure)
    return figure


def curve_figure(
    curves: dict[str, pd.DataFrame], metrics: pd.DataFrame, *, symbol: str, kind: str
) -> plt.Figure:
    if metrics.empty:
        figure, axis = plt.subplots(figsize=(9, 3))
        axis.text(0.05, 0.5, f"{symbol}: no eligible final-test curves.")
        axis.set_axis_off()
        plt.close(figure)
        return figure
    figures = final_evaluation_figures(
        curves["roc"],
        curves["precision_recall"],
        symbol=symbol,
        start=metrics.evaluation_start_utc.min(),
        end=metrics.evaluation_end_utc.max(),
    )
    for figure in figures.values():
        plt.close(figure)
    return figures[kind]


def figure_image(figure: plt.Figure) -> Image:
    """Embed a PNG even when the kernel uses a non-interactive backend."""
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
    return Image(data=buffer.getvalue())
