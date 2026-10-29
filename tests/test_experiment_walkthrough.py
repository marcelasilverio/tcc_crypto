"""Run isolation and notebook execution against small, local research inputs."""

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from tcc_crypto.paths import ArtifactPaths, FinalArtifactPaths
from tcc_crypto.workflows import (
    daily_data,
    daily_review,
    experiment_review,
    final_evaluation,
)
from tcc_crypto.workflows import experiment_walkthrough as walkthrough
from tcc_crypto.workflows.context import load_context

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/17_binance_daily_svm_experiment_walkthrough.ipynb"


def test_run_paths_and_signatures_preserve_legacy_behavior(tmp_path):
    legacy = load_context("development", root=ROOT)
    first = load_context("development", root=ROOT, run_id="first")
    second = load_context("development", root=ROOT, run_id="second")
    assert "run_id" not in legacy.signature()
    assert first.signature()["run_id"] == "first"
    assert first.paths.raw == second.paths.raw == legacy.paths.raw
    assert len({c.paths.table("dataset") for c in (legacy, first, second)}) == 3
    assert "/runs/first/" in str(first.paths.dataset_workbook)
    assert not (tmp_path / "data").exists()
    for invalid in ("", "..", "../outside", "a/b", "a\\b"):
        with pytest.raises(ValueError):
            ArtifactPaths(tmp_path, "context", "BTCUSDT", run_id=invalid)


def test_notebook_run_load_and_export_without_network(tmp_path, monkeypatch):
    import urllib.request

    from IPython.utils.capture import capture_output
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    from test_daily_pipeline import context as fixture
    from test_daily_svm_grid_search import _small_config

    from tcc_crypto.modeling.final_config import FinalEvaluationConfig

    base = fixture.__wrapped__(tmp_path)
    model = replace(
        _small_config(),
        candidate_symbols=("BTCUSDT",),
        raw_directory=base.paths.raw.parent,
        development_start_utc=base.data.sample_start_utc,
        development_end_utc=pd.Timestamp("2019-07-20", tz="UTC"),
    )
    dev = replace(
        base,
        profile="development",
        model=model,
        data=replace(
            base.data,
            context_id="development",
            sample_end_utc=model.development_end_utc,
        ),
        paths=ArtifactPaths(
            tmp_path, "development", "BTCUSDT", base.paths.raw.parent, run_id="small"
        ),
    )
    full = replace(
        base,
        profile="experiment",
        model=model,
        data=replace(base.data, context_id="full"),
        paths=ArtifactPaths(
            tmp_path, "full", "BTCUSDT", base.paths.raw.parent, run_id="small"
        ),
    )
    config = FinalEvaluationConfig(
        "final",
        tmp_path / "unused",
        pd.Timestamp("2019-07-22", tz="UTC"),
        full.data.sample_end_utc,
    )
    config_file = tmp_path / "configs/binance_daily_svm_final_evaluation.json"
    config_file.parent.mkdir()
    config_file.write_text("{}")
    final_paths = FinalArtifactPaths(tmp_path, "final", "BTCUSDT", "small")

    def inputs(*args):
        return config, final_paths, full, {"test": True, "run_id": "small"}

    def context(profile, **kwargs):
        return full if profile == "experiment" else dev

    monkeypatch.setattr(final_evaluation, "_inputs", inputs)
    monkeypatch.setattr(experiment_review, "_inputs", inputs)
    monkeypatch.setattr(experiment_review, "load_context", context)
    monkeypatch.setattr(daily_review, "load_context", context)

    def forbidden(*args, **kwargs):
        pytest.fail("Load/export must not train or access the network")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    cells = json.loads(NOTEBOOK.read_text())["cells"]

    def execute(mode):
        namespace = {}
        with capture_output():
            for cell in cells:
                if cell["cell_type"] != "code":
                    continue
                source = "".join(cell["source"])
                source = source.replace('MODE = "run"', f'MODE = "{mode}"')
                source = source.replace("WINDOW_SIZE = 60", "WINDOW_SIZE = 4")
                source = source.replace(
                    'FEATURE_DATE = "2025-01-01"', 'FEATURE_DATE = "2019-07-22"'
                )
                exec(compile(source, str(NOTEBOOK), "exec"), namespace)

    execute("run")
    with pytest.raises(FileExistsError):
        walkthrough.preparation(dev, "aligned", mode="run")
    other = replace(dev, paths=replace(dev.paths, run_id="other"))
    with pytest.raises(FileNotFoundError):
        daily_data.read_stage(other, "dataset")
    monkeypatch.setattr(SVC, "fit", forbidden)
    monkeypatch.setattr(StandardScaler, "fit", forbidden)
    execute("load")
    walkthrough.export_saved(dev, regenerate=True, overwrite=True)
    assert final_paths.training_metrics.exists()


def test_cli_routes_run_id_and_rejects_cross_run_metadata(tmp_path, monkeypatch):
    from test_daily_pipeline import context as fixture

    from tcc_crypto.daily import main
    from tcc_crypto.reporting.tables import read_table
    from tcc_crypto.workflows import context as contexts

    base = fixture.__wrapped__(tmp_path)
    first = replace(base, paths=replace(base.paths, run_id="first"))
    daily_data.align(first)
    with pytest.raises(ValueError):
        read_table(
            first.paths.table("aligned"),
            context=replace(
                base, paths=replace(base.paths, run_id="second")
            ).signature(),
            stage="align",
        )
    seen = []

    def context(profile, **kwargs):
        seen.append(kwargs["run_id"])
        return replace(base, paths=replace(base.paths, run_id=kwargs["run_id"]))

    monkeypatch.setattr(contexts, "load_context", context)
    main(["features", "--profile", "pilot", "--run-id", "first"])
    expected = daily_data.read_stage(first, "features")
    actual = walkthrough.preparation(first, "features", mode="load")
    pd.testing.assert_frame_equal(actual, expected)
    assert seen == ["first", "first"]
    override = ArtifactPaths(
        tmp_path,
        "context",
        "BTCUSDT",
        results_directory=Path("custom"),
        feature_directory=Path("features"),
        run_id="first",
    )
    assert override.results("grid-search") == tmp_path / "custom/runs/first/BTCUSDT"
    assert (
        override.table("features")
        == tmp_path / "features/context/runs/first/BTCUSDT.csv.gz"
    )


def test_training_review_cli_forwards_selected_symbol_and_run(monkeypatch):
    from tcc_crypto.daily import main

    calls = []

    def reconstruct(**kwargs):
        calls.append(kwargs)
        return pd.DataFrame()

    monkeypatch.setattr(experiment_review, "reconstruct_in_sample", reconstruct)
    main(["training-review", "--symbols", "BTCUSDT", "--run-id", "cli-test"])
    assert calls == [
        {
            "root": ROOT,
            "symbols": ("BTCUSDT",),
            "run_id": "cli-test",
            "overwrite": False,
        }
    ]
