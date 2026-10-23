"""Training reconstruction and truthful phase separation in supervisor reports."""

import json
from dataclasses import replace
from types import SimpleNamespace

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from test_daily_svm_grid_search import _dataset, _selection_config, _small_config

from tcc_crypto.analysis.experiment_results import (
    METRICS,
    asset_overview,
    development_vs_final,
    selected_folds,
)
from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.modeling.final_evaluation import freeze_configurations
from tcc_crypto.modeling.grid_search import run_temporal_grid_search
from tcc_crypto.modeling.training_review import reconstruct_training_metrics
from tcc_crypto.paths import FinalArtifactPaths
from tcc_crypto.reporting.tables import write_table
from tcc_crypto.visualization.experiment_results import (
    confusion_figure,
    curve_figure,
    figure_image,
    phase_comparison,
)
from tcc_crypto.workflows import experiment_review as review


@pytest.fixture
def evidence():
    data = _dataset()
    for index, feature in enumerate(ACTIVE_FEATURES):
        data[feature] = data["signal" if index % 2 else "secondary"] + index
    config = _small_config()
    selection = _selection_config()
    search = run_temporal_grid_search(
        data, symbol="BTCUSDT", config=config, selection_config=selection
    )
    chosen = freeze_configurations(
        search.selected_configurations, search.eligibility, "BTCUSDT", config
    )
    return data, config, selection, search, chosen


def reconstruct(evidence, **changes):
    data, config, selection, search, chosen = evidence
    return reconstruct_training_metrics(
        changes.get("dataset", data),
        chosen,
        changes.get("folds", search.fold_results),
        config=config,
        selection_config=selection,
    )


def test_reconstructs_only_selected_fits_and_preserves_temporal_windows(
    evidence, monkeypatch
):
    from tcc_crypto.modeling import training_review

    _, config, _, _, chosen = evidence
    original = training_review.SVC
    fitted_parameters = []

    def estimator(**parameters):
        fitted_parameters.append(parameters)
        return original(**parameters)

    monkeypatch.setattr(training_review, "SVC", estimator)
    result = reconstruct(evidence)
    assert len(result) == config.n_splits * len(chosen) == len(fitted_parameters)
    assert all(
        parameters == json.loads(chosen.iloc[0].frozen_parameters)
        for parameters in fitted_parameters
    )
    assert result.validation_reproduced.all()
    assert result.training_rows.eq(4).all()
    assert (
        result.training_end_utc + pd.Timedelta(days=1) < result.validation_start_utc
    ).all()
    assert result.in_sample_f1.between(0, 1).all()


def test_reconstruction_rejects_validation_drift_and_future_rows(evidence):
    data, config, selection, search, chosen = evidence
    folds = search.fold_results.copy()
    folds["f1"] = 999.0
    with pytest.raises(ValueError, match="validation f1 differs"):
        reconstruct(evidence, folds=folds)
    with pytest.raises(ValueError, match="development data only"):
        reconstruct_training_metrics(
            data,
            chosen,
            search.fold_results,
            config=replace(config, development_end_utc=data.index[0]),
            selection_config=selection,
        )
    folds = search.fold_results.copy()
    folds["training_start_utc"] += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match="boundaries differ"):
        reconstruct(evidence, folds=folds)


def test_phase_means_are_not_pooled_or_mislabeled(evidence):
    training = reconstruct(evidence)
    chosen = evidence[-1].copy()
    metrics = pd.DataFrame(
        [
            {
                "symbol": "BTCUSDT",
                "target": "target_2pct",
                "window_size": 4,
                "model": "tuned_svc",
                "evaluated_dates": 10,
                "omitted_dates": 2,
                "actual_positive": 3,
                "actual_negative": 7,
                **{metric: 0.123 for metric in METRICS},
            }
        ]
    )
    table = development_vs_final(chosen, metrics, training)
    assert table.iloc[0].final_f1 == 0.123
    assert table.iloc[0].validation_f1 == chosen.iloc[0].mean_f1
    assert table.iloc[0].in_sample_f1 == training.in_sample_f1.mean()
    assert table.iloc[0].final_positive_rate == 0.3
    missing = development_vs_final(chosen, metrics)
    assert missing.iloc[0].in_sample_status == "Not recorded"
    assert "in_sample_f1" not in missing


def test_overview_preserves_excluded_assets_and_counts_omissions_once(evidence):
    eligibility = evidence[3].eligibility
    excluded = eligibility.assign(
        symbol="EXCLUDED", status="ineligible", reason="no_history"
    )
    metrics = pd.DataFrame(
        [
            {
                "symbol": "BTCUSDT",
                "model": model,
                "evaluated_dates": 8,
                "omitted_dates": 2,
            }
            for model in ("tuned_svc", "default_svc")
        ]
    )
    overview = asset_overview(pd.concat([eligibility, excluded]), metrics)
    assert list(overview.symbol) == ["BTCUSDT", "EXCLUDED"]
    assert overview.iloc[0].omitted_combination_dates == 2
    assert overview.iloc[1].exclusion_reasons == "no_history"


def test_reload_verifies_artifacts_without_fitting(evidence, tmp_path, monkeypatch):
    data, config, _, search, chosen = evidence
    signature = {"test": "saved"}
    context = SimpleNamespace(
        root=tmp_path,
        model=SimpleNamespace(candidate_symbols=("BTCUSDT",)),
        signature=lambda: signature,
    )
    paths = FinalArtifactPaths(tmp_path, "test", "BTCUSDT")
    metrics = pd.DataFrame(
        [
            {
                "symbol": "BTCUSDT",
                "target": "target_2pct",
                "window_size": 4,
                "model": "tuned_svc",
                "evaluated_dates": 10,
                "omitted_dates": 0,
                "actual_positive": 3,
                "actual_negative": 7,
                **{metric: 0.5 for metric in METRICS},
            }
        ]
    )
    for name, table in (
        ("eligibility", search.eligibility),
        ("metrics", metrics),
        ("selected_configurations", chosen),
    ):
        write_table(
            table, paths.tables()[name], root=tmp_path, context=signature, sources=[]
        )
    monkeypatch.setattr(review, "load_context", lambda *args, **kwargs: context)
    monkeypatch.setattr(review, "_inputs", lambda *args: (None, paths, None, signature))
    monkeypatch.setattr(
        review,
        "result_table_paths",
        lambda ctx: {"eligibility": tmp_path / "grid" / "eligibility.csv"},
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Read-only review attempted fitting")

    monkeypatch.setattr(review, "reconstruct_training_metrics", forbidden)
    from sklearn.svm import SVC

    monkeypatch.setattr(SVC, "fit", forbidden)
    report = review.load_results(root=tmp_path)
    assert report.overview.iloc[0].symbol == "BTCUSDT"
    assert (
        review.asset_comparison(report, "BTCUSDT").iloc[0].in_sample_status
        == "Not recorded"
    )
    with pytest.raises(ValueError, match="Unknown"):
        review.asset_metrics(report, "UNKNOWN")
    paths.tables()["metrics"].write_text("modified")
    with pytest.raises(ValueError, match="Modified"):
        review.load_results(root=tmp_path)


def test_notebook_helpers_handle_excluded_assets_and_keep_three_phases():
    table = pd.DataFrame(
        [
            {
                "target": "target_2pct",
                "window_size": 60,
                **{
                    f"{phase}_{metric}": value
                    for phase, value in (
                        ("in_sample", 0.9),
                        ("validation", 0.7),
                        ("final", 0.4),
                    )
                    for metric in ("precision", "recall", "f1")
                },
            }
        ]
    )
    figure = phase_comparison(table, symbol="BTCUSDT")
    assert [bar.get_height() for bar in figure.axes[0].patches] == [0.9, 0.7, 0.4]
    assert figure_image(figure).data.startswith(b"\x89PNG\r\n\x1a\n")
    plt.close(figure)
    empty = pd.DataFrame(columns=["target", "window_size"])
    figure = confusion_figure(
        empty, symbol="EXCLUDED", target="target_2pct", window_size=60
    )
    assert "ineligible" in figure.axes[0].texts[0].get_text()
    plt.close(figure)


def test_excluded_asset_curves_are_explicitly_unavailable():
    figure = curve_figure({}, pd.DataFrame(), symbol="EXCLUDED", kind="roc")
    assert "no eligible" in figure.axes[0].texts[0].get_text()
    plt.close(figure)


def test_excluded_asset_has_no_selected_folds_or_phase_scores():
    assert selected_folds(pd.DataFrame(), pd.DataFrame()).empty
    figure = phase_comparison(pd.DataFrame(), symbol="EXCLUDED")
    assert "no eligible" in figure.axes[0].texts[0].get_text()
    plt.close(figure)
