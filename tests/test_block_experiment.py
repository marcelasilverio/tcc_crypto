"""Small independently checkable examples for the daily block experiment."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import ParameterGrid, TimeSeriesSplit

from tcc_crypto import dataset, experiment, preparation, results, training
from tcc_crypto.config import Config, load_config
from tcc_crypto.paths import Paths, raw_paths


def candles(size=160):
    dates = pd.date_range("2019-06-01", periods=size, tz="UTC")
    opened = 100 + np.arange(size) * 0.2 + np.sin(np.arange(size))
    return pd.DataFrame(
        {
            "open_time_ms": dates.asi8 // 1_000_000,
            "open": opened,
            "high": opened * (1 + np.where(np.arange(size) % 2 == 0, 0.04, 0.005)),
            "low": opened * 0.99,
            "close": opened * 1.002,
            "base_asset_volume": 100.0,
            "close_time_ms": dates.asi8 // 1_000_000 + preparation.DAY_MS - 1,
            "quote_asset_volume": 10000.0 + np.arange(size),
            "number_of_trades": 100,
            "taker_buy_base_asset_volume": 50.0,
            "taker_buy_quote_asset_volume": 5000.0,
            "ignore": 0,
        }
    )


def small_config():
    original = load_config()
    settings = deepcopy(original.values)
    settings["symbols"] = ["BTCUSDT", "LUNAUSDT"]
    settings["study"]["end"] = "2019-11-07"
    settings["windows"] = [60]
    settings["targets"] = [0.01]
    grid = deepcopy(original.grid)
    grid["parameter_grid"] = [
        {"kernel": ["linear"], "C": [1.0], "class_weight": [None]}
    ]
    return Config(settings, grid)


def test_production_grid_and_defaults():
    config = load_config()
    assert len(list(ParameterGrid(config.grid["parameter_grid"]))) == 186
    for size, expected in [
        (60, [10, 20, 30, 40, 50]),
        (75, [15, 27, 39, 51, 63]),
        (90, [15, 30, 45, 60, 75]),
    ]:
        splits = list(
            TimeSeriesSplit(**config.values["temporal_cross_validation"]).split(
                range(size)
            )
        )
        assert [len(a) for a, b in splits] == expected
        assert all(len(b) == size // 6 and a[-1] + 1 == b[0] for a, b in splits)


def test_raw_validation_and_bounded_fill():
    raw = candles(10)
    raw.loc[0, "high"] = -1
    raw.loc[3, "number_of_trades"] = None
    raw.loc[9, "close"] = None
    raw = raw.drop(index=5)
    saved = raw.copy(deep=True)
    prepared = preparation.prepare_symbol(
        raw,
        "BTCUSDT",
        {"start": "2019-06-01", "end": "2019-06-10", "warmup_start": "2019-06-01"},
    )
    pd.testing.assert_frame_equal(raw, saved)
    assert prepared.availability.available.tolist() == [0, 1, 1, 0, 1, 0, 1, 1, 1, 0]
    assert len(prepared.treated) == 8
    assert prepared.treated.is_imputed.sum() == 2
    filled = prepared.treated.loc[prepared.treated.is_imputed].iloc[0]
    assert filled.open == raw.loc[2, "open"]
    assert filled.source_date_utc == pd.Timestamp("2019-06-03", tz="UTC")
    assert filled.date_utc == pd.Timestamp("2019-06-04", tz="UTC")
    with pytest.raises(ValueError, match="duplicate"):
        preparation.prepare_symbol(
            pd.concat([raw, raw.iloc[[0]]]),
            "BTCUSDT",
            {"start": "2019-06-01", "end": "2019-06-10", "warmup_start": "2019-06-01"},
        )


def test_dataset_alignment_and_no_future_features():
    config = small_config()
    prepared = preparation.prepare_symbol(candles(), "BTCUSDT", config.values["study"])
    tables = dataset.build_dataset(prepared.treated, config.values)
    values = prepared.treated
    features = tables.features
    assert features.r1.iloc[20] == pytest.approx(
        np.log(values.close.iloc[20] / values.close.iloc[19])
    )
    assert tables.targets.target_1pct.iloc[20] == 0
    assert tables.targets.target_1pct.iloc[21] == 1
    assert pd.isna(tables.targets.target_1pct.iloc[-1])
    changed = values.copy()
    changed.loc[100:, "close"] *= 0.999
    alternative = dataset.build_dataset(changed, config.values)
    pd.testing.assert_frame_equal(features.iloc[:100], alternative.features.iloc[:100])
    assert tables.dataset.is_usable.iloc[-1] == False


def test_outer_blocks_and_label_availability():
    blocks = list(training.outer_blocks(151, 60))
    assert [(len(a), len(b)) for a, b in blocks] == [(60, 60), (60, 31)]
    assert blocks[0][1].tolist() == blocks[1][0].tolist()
    assert list(training.outer_blocks(60, 60)) == []
    config = small_config()
    table = dataset.build_dataset(
        preparation.prepare_symbol(
            candles(), "BTCUSDT", config.values["study"]
        ).treated,
        config.values,
    ).dataset
    training.assert_label_availability(table.iloc[:60], table.iloc[60:120])
    bad = table.iloc[:60].copy()
    bad.loc[bad.index[-1], "target_available_at_utc"] = pd.Timestamp(
        "2030-01-01", tz="UTC"
    )
    with pytest.raises(ValueError, match="not yet available"):
        training.assert_label_availability(bad, table.iloc[60:120])


def test_selection_matches_reference_and_transforms_without_refit():
    X = pd.DataFrame({"a": np.arange(20.0), "b": np.arange(20.0) * 2, "c": np.ones(20)})
    selector = training.FeatureSelector().fit(X)
    assert selector.selected_features_ == ["a"]
    assert (
        selector.audit().set_index("feature").loc["b", "reason"] == "high_correlation"
    )
    assert list(selector.transform(X * 100)) == ["a"]
    fallback = training.FeatureSelector().fit(
        pd.DataFrame({"a": [0.0, 0.001], "b": [0.0, 0.002]})
    )
    assert fallback.selected_features_ == ["b"] and fallback.fallback_error_


def test_csv_roundtrip_staleness_and_overwrite(tmp_path):
    context = {"test": True}
    source = tmp_path / "source.csv"
    frame = pd.DataFrame(
        {
            "time": pd.date_range("2020-01-01", periods=2, tz="UTC"),
            "signal": pd.Series([0, None], dtype="Int64"),
            "filled": pd.Series([True, None], dtype="boolean"),
            "value": [np.pi, np.e],
        }
    )
    results.write_table(frame, source, context=context)
    pd.testing.assert_frame_equal(
        frame, results.read_table(source, context=context, stage="prepare")
    )
    second = tmp_path / "second.csv"
    third = tmp_path / "third.csv"
    results.write_table(frame, second, context=context, sources=[source])
    results.write_table(frame, third, context=context, sources=[second])
    with pytest.raises(FileExistsError):
        results.write_table(frame, source, context=context)
    changed = frame.copy()
    changed.loc[0, "value"] = 9
    results.write_table(changed, source, context=context, overwrite=True)
    with pytest.raises(ValueError, match="Stale"):
        results.read_table(third, context=context, stage="train")


def test_end_to_end_saved_stages_and_export_without_fitting(tmp_path, monkeypatch):
    config = small_config()
    paths = Paths(tmp_path, "test_run")
    raw = raw_paths(tmp_path, "BTCUSDT", config.values["collection"])["raw"]
    raw.parent.mkdir(parents=True)
    candles().to_csv(raw, index=False, compression="gzip")
    save_raw_metadata(config, tmp_path, "BTCUSDT")
    with pytest.raises(FileNotFoundError, match="prepare"):
        experiment.build_datasets(config, ["BTCUSDT"], paths)
    experiment.prepare(config, ["BTCUSDT"], paths)
    experiment.build_datasets(config, ["BTCUSDT"], paths)
    experiment.train(config, ["BTCUSDT"], paths)
    signature = experiment.context(config, paths.run_id)
    predictions = results.read_table(
        paths.audit("BTCUSDT", "predictions"), context=signature, stage="train"
    )
    assert set(predictions.role) == {"in_sample", "out_of_sample"}
    assert predictions.status.eq("ok").all()
    metrics = results.read_table(
        paths.main("metrics"), context=signature, stage="train"
    )
    assert set(metrics.window_size) == {60}
    assert (metrics.evaluated_count > 0).all()
    monkeypatch.setattr(
        training, "train_symbol", lambda *args: pytest.fail("Export must not train")
    )
    experiment.consolidate(config, paths, overwrite=True)
    assert not list(tmp_path.rglob("*.xlsx"))
    assert paths.main("predictions_out_of_sample").exists()


def test_single_class_and_excluded_have_no_fabricated_signals():
    config = small_config()
    table = dataset.build_dataset(
        preparation.prepare_symbol(
            candles(), "BTCUSDT", config.values["study"]
        ).treated,
        config.values,
    ).dataset
    table.loc[table.is_usable, "target_1pct"] = 0
    output = training.train_symbol(table, "BTCUSDT", config.values, config.grid)
    assert output["predictions"].predicted.isna().all()
    assert output["metrics"].evaluated_count.eq(0).all()
    excluded = training.train_symbol(table, "LUNAUSDT", config.values, config.grid)
    assert excluded["predictions"].empty
    assert excluded["failures"].status.iloc[0] == "explicit_symbol_exclusion"


def test_matrix_preserves_asset_specific_dates_and_missing_predictions():
    rows = pd.DataFrame(
        {
            "feature_time_utc": pd.to_datetime(["2020-01-01", "2020-01-02"], utc=True),
            "symbol": ["A", "B"],
            "target": ["target_1pct"] * 2,
            "window_size": [60] * 2,
            "role": ["out_of_sample"] * 2,
            "model": ["tuned_svc"] * 2,
            "predicted": pd.Series([0, None], dtype="Int64"),
            "actual": [1, 0],
        }
    )
    matrix = results.binary_matrix(rows, ["A", "B"], "out_of_sample")
    assert matrix.A.iloc[0] == 0 and pd.isna(matrix.B.iloc[1])
    assert pd.isna(matrix.A.iloc[1])


def test_partial_run_can_add_asset_and_preserve_independent_calendars(tmp_path):
    config = small_config()
    config.values["symbols"].insert(1, "ADAUSDT")
    paths = Paths(tmp_path, "partial")
    for symbol, rows in [("BTCUSDT", candles()), ("ADAUSDT", candles().iloc[40:])]:
        raw = raw_paths(tmp_path, symbol, config.values["collection"])["raw"]
        raw.parent.mkdir(parents=True, exist_ok=True)
        rows.to_csv(raw, index=False, compression="gzip")
        save_raw_metadata(config, tmp_path, symbol)
    experiment.prepare(config, ["BTCUSDT"], paths)
    experiment.prepare(config, ["ADAUSDT"], paths, overwrite=True)
    experiment.build_datasets(config, ["BTCUSDT", "ADAUSDT"], paths)
    experiment.train(config, ["BTCUSDT", "ADAUSDT"], paths)
    matrix = results.read_table(
        paths.main("predictions_out_of_sample"),
        context=experiment.context(config, paths.run_id),
        stage="train",
    )
    assert matrix.BTCUSDT.notna().any() and matrix.ADAUSDT.notna().any()
    assert matrix.ADAUSDT.isna().any() and matrix.LUNAUSDT.isna().all()
    different = deepcopy(config.values)
    different["windows"] = [75]
    with pytest.raises(ValueError, match="another configuration"):
        experiment.open_execution(Config(different, config.grid), paths)


def test_unexpected_dataset_gap_is_rejected():
    config = small_config()
    treated = preparation.prepare_symbol(
        candles(), "BTCUSDT", config.values["study"]
    ).treated
    with pytest.raises(ValueError, match="consecutive"):
        dataset.build_dataset(treated.drop(index=50), config.values)


def test_cli_requires_explicit_scope_and_run_id():
    with pytest.raises(SystemExit):
        experiment.main(["prepare"])
    with pytest.raises(SystemExit):
        experiment.main(["train", "--symbols", "BTCUSDT"])


def save_raw_metadata(config, root, symbol):
    paths = raw_paths(root, symbol, config.values["collection"])
    results.write_json(
        paths["metadata"],
        {
            "symbol": symbol,
            "requested": config.values["collection"],
            "sha256": results.file_sha256(paths["raw"]),
            "completion": "empty_page",
        },
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("open", 0),
        ("high", 1),
        ("low", 999),
        ("close", float("inf")),
        ("quote_asset_volume", -1),
        ("number_of_trades", 1.5),
        ("taker_buy_base_asset_volume", None),
        ("close_time_ms", -1),
    ],
)
def test_identifiable_invalid_candles_are_filled_but_unavailable(field, value):
    raw = candles(5).astype(float)
    raw.loc[2, field] = value
    study = {"start": "2019-06-01", "end": "2019-06-05", "warmup_start": "2019-06-01"}
    result = preparation.prepare_symbol(raw, "BTCUSDT", study)
    assert result.availability.available.tolist() == [1, 1, 0, 1, 1]
    assert result.treated.is_imputed.tolist() == [False, False, True, False, False]
    assert result.treated.close.iloc[2] == result.treated.close.iloc[1]


def test_shortened_candle_remains_valid_and_marked_for_review():
    raw = candles(5)
    raw.loc[2, "close_time_ms"] -= 1000
    study = {"start": "2019-06-01", "end": "2019-06-05", "warmup_start": "2019-06-01"}
    result = preparation.prepare_symbol(raw, "BTCUSDT", study)
    assert result.availability.available.eq(1).all()
    assert result.diagnostics.shortened_candle.iloc[2]
    assert not result.treated.is_imputed.any()
