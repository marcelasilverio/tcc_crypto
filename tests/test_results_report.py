"""Saved-result visualization must preserve experimental and missing-data boundaries."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pandas as pd
import pytest

from tcc_crypto import experiment, results
from tcc_crypto.paths import Paths


def test_report_load_requires_saved_execution_without_creating_files(tmp_path):
    paths = Paths(tmp_path, "missing")
    with pytest.raises(FileNotFoundError, match="Missing saved execution"):
        experiment.load_report(paths)
    assert not paths.output.exists()


def test_report_load_rejects_different_run(tmp_path):
    paths = Paths(tmp_path, "requested")
    results.write_json(paths.configuration, {"run_id": "another"})
    results.write_json(paths.execution, {})
    with pytest.raises(ValueError, match="run ID"):
        experiment.load_report(paths)


def test_metric_plot_keeps_roles_settings_and_missing_scores_separate():
    frame = pd.DataFrame(
        {
            "target": ["target_1pct"] * 5 + ["target_2pct"],
            "window_size": [60, 60, 60, 60, 120, 60],
            "role": [
                "in_sample",
                "out_of_sample",
                "out_of_sample",
                "out_of_sample",
                "out_of_sample",
                "out_of_sample",
            ],
            "model": ["tuned_svc"] * 6,
            "f1": [1.0, 0.2, 0.6, float("nan"), 1.0, 1.0],
        }
    )
    report = {
        "run_id": "test",
        "tables": {"metrics": frame},
        "configuration": {
            "experiment": {"study": {"start": "2020-01-01", "end": "2020-12-31"}}
        },
    }
    original = frame.copy(deep=True)
    notebook = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "notebooks"
            / "18_binance_daily_svm_results_visual_report.ipynb"
        ).read_text()
    )
    scope = {
        "report": report,
        "display": lambda value: None,
        "study": report["configuration"]["experiment"]["study"],
    }
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap

    scope.update(pd=pd, plt=plt, np=np, ListedColormap=ListedColormap)
    for tag in ("report-filters", "report-style", "report-f1"):
        cell = next(
            c for c in notebook["cells"] if tag in c.get("metadata", {}).get("tags", [])
        )
        exec(compile("".join(cell["source"]), f"notebook:{tag}", "exec"), scope)
    fig = scope["fig"]
    assert fig.axes[0].patches[0].get_height() == 1.0
    assert fig.axes[1].patches[0].get_height() == pytest.approx(0.4)
    assert "n=2" in fig.axes[1].get_xticklabels()[0].get_text()
    pd.testing.assert_frame_equal(frame, original)
    assert scope["tables"]["metrics"].shape[0] == 4
