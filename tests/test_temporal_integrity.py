"""Check independent temporal and candidate-selection invariants."""

import numpy as np
import pandas as pd
import pytest
from test_block_experiment import candles, small_config

from tcc_crypto import dataset, preparation, training


@pytest.mark.parametrize("window", [60, 75, 90])
def test_blocks_preserve_exact_calendar_sizes(window):
    blocks = list(training.outer_blocks(3 * window + 7, window))
    assert [(len(a), len(b)) for a, b in blocks] == [
        (window, window),
        (window, window),
        (window, 7),
    ]
    for previous, following in zip(blocks, blocks[1:]):
        np.testing.assert_array_equal(previous[1], following[0])


@pytest.mark.parametrize(
    "column, first, second",
    [
        ("mean_f1", 0.9, 0.8),
        ("mean_precision", 0.9, 0.8),
        ("f1_standard_deviation", 0.1, 0.2),
        ("mean_roc_auc", 0.9, 0.8),
        ("kernel", "linear", "rbf"),
        ("C", 0.1, 1.0),
        ("candidate_order", 0, 1),
    ],
)
def test_each_ranking_priority(column, first, second):
    base = dict(
        mean_f1=0.8,
        mean_precision=0.8,
        f1_standard_deviation=0.1,
        mean_roc_auc=0.8,
        kernel="rbf",
        C=1.0,
        candidate_order=0,
        failed_fold_count=0,
    )
    rows = pd.DataFrame([{**base, column: second}, {**base, column: first}])
    assert training.select_best_candidate(rows, tolerance=1e-12).name == 1
    rows.loc[1, "failed_fold_count"] = 1
    assert training.select_best_candidate(rows, tolerance=1e-12).name == 0


def test_outer_targets_do_not_enter_fit_and_inner_scaling_uses_only_training():
    config = small_config()
    treated = preparation.prepare_symbol(
        candles(), "BTCUSDT", config.values["study"]
    ).treated
    table = dataset.build_dataset(treated, config.values).dataset
    first = training.train_symbol(table, "BTCUSDT", config.values, config.grid)
    usable = table.index[table.is_usable]
    changed = table.copy()
    changed.loc[usable[60:], "target_1pct"] = (
        1 - changed.loc[usable[60:], "target_1pct"]
    )
    second = training.train_symbol(changed, "BTCUSDT", config.values, config.grid)
    a = first["predictions"].query("block_id == 0")
    b = second["predictions"].query("block_id == 0")
    pd.testing.assert_series_equal(a.predicted, b.predicted)
    pd.testing.assert_series_equal(a.score, b.score)
    scales = first["scaling"].query(
        "block_id == 0 and fit_scope == 'inner' and fold == 0"
    )
    train = table.loc[usable[:10]]
    for row in scales.itertuples():
        assert row.mean == pytest.approx(train[row.feature].mean())
    assert first["folds"].query("block_id == 0").fold.tolist() == list(range(5))


def test_undefined_ranking_metrics_are_missing():
    metrics = training.calculate_classification_metrics([0, 0], [0, 0], [0.0, 0.0])
    assert metrics["precision"] == metrics["recall"] == 0
    assert np.isnan(metrics["roc_auc"]) and np.isnan(metrics["average_precision"])


def test_failed_candidates_are_excluded_but_audited():
    config = small_config()
    settings = config.values
    X = pd.DataFrame({"a": np.arange(60.0), "b": np.sin(np.arange(60.0))})
    y = np.arange(60) % 2
    grid = {**config.grid, "parameter_grid": [{"kernel": ["linear"], "C": [-1.0, 1.0]}]}
    with pytest.warns(Warning):
        search = training.fit_search(X, y, settings, grid)
    candidates = training.candidate_table(search.cv_results_)
    assert candidates.failed_fold_count.tolist() == [5, 0]
    assert search.best_params_["svc__C"] == 1.0


def test_all_candidates_failed_preserves_failure_evidence():
    config = small_config()
    config.grid["parameter_grid"] = [{"kernel": ["linear"], "C": [-1.0]}]
    table = dataset.build_dataset(
        preparation.prepare_symbol(
            candles(), "BTCUSDT", config.values["study"]
        ).treated,
        config.values,
    ).dataset
    result = training.train_symbol(table, "BTCUSDT", config.values, config.grid)
    assert not result["fold_scores"].empty
    assert result["candidates"].status.eq("search_failed").all()
    assert result["predictions"].query("model == 'tuned_svc'").predicted.isna().all()


def test_single_class_inner_fold_keeps_other_fold_scores():
    config = small_config()
    table = dataset.build_dataset(
        preparation.prepare_symbol(
            candles(), "BTCUSDT", config.values["study"]
        ).treated,
        config.values,
    ).dataset
    usable = table.index[table.is_usable]
    table.loc[usable[:10], "target_1pct"] = 0
    output = training.train_symbol(table, "BTCUSDT", config.values, config.grid)
    scores = output["fold_scores"].query("block_id == 0")
    assert scores.f1.isna().sum() == 1
    assert scores.f1.notna().sum() == 4
    assert output["candidates"].query("block_id == 0").failed_fold_count.iloc[0] == 1
    assert (
        output["predictions"]
        .query("block_id == 0 and model == 'tuned_svc'")
        .predicted.isna()
        .all()
    )


def test_scaling_precedes_selection_and_keeps_all_feature_audit():
    config = small_config()
    X = pd.DataFrame(
        {
            "small": np.arange(60.0) * 0.0001,
            "large": np.sin(np.arange(60.0)) * 1000,
            "constant": np.ones(60),
        }
    )
    fitted = training.pipeline(config.values).fit(X, np.arange(60) % 2)
    assert list(fitted.named_steps) == ["scaling", "selection", "svc"]
    selector = fitted.named_steps["selection"]
    assert selector.selected_features_ == ["small", "large"]
    np.testing.assert_allclose(selector.variances_, [1.0, 1.0, 0.0], atol=1e-12)
    audit = {}
    training._save_preprocessing(
        fitted,
        {"fit_scope": "full_in_sample"},
        lambda name, frame, identity: audit.update({name: frame}),
    )
    assert audit["scaling"].feature.tolist() == list(X.columns)
    np.testing.assert_allclose(audit["scaling"]["mean"], X.mean())
    before = fitted.named_steps["scaling"].mean_.copy()
    fitted.predict(X * 100)
    np.testing.assert_array_equal(fitted.named_steps["scaling"].mean_, before)
