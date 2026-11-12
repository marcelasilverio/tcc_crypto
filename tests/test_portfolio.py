"""Financial examples, temporal boundaries and independent portfolio execution."""

import builtins
import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")

from tcc_crypto import backtesting, experiment, portfolio, results
from tcc_crypto.config import (
    load_config,
    load_portfolio_config,
    validate_portfolio_config,
)
from tcc_crypto.paths import PORTFOLIO_TABLES, Paths, PortfolioPaths


@pytest.fixture
def settings():
    return load_portfolio_config()


@pytest.fixture
def source_run(tmp_path):
    """Use the existing saved CSV contracts with small deterministic inputs."""
    settings = load_portfolio_config()
    config = load_config()
    config.values["symbols"] = ["BTCUSDT", "ETHUSDT"]
    config.values["excluded_symbols"] = []
    paths = Paths(tmp_path, "training_01")
    signature = experiment.open_execution(config, paths)
    history = pd.date_range("2020-01-01", periods=64, tz="UTC")
    days = history[60:63]
    for index, symbol in enumerate(config.values["symbols"]):
        features = pd.DataFrame(
            {"feature_time_utc": history, "r1": np.sin(np.arange(64) + index) / 100}
        )
        treated = pd.DataFrame(
            {
                "date_utc": history,
                "open": 100.0,
                "high": 104.0,
                "low": 98.0,
                "close": 99.0,
                "is_imputed": False,
                "source_date_utc": history,
            }
        )
        targets = pd.DataFrame(
            {
                "feature_time_utc": history,
                "target_time_utc": history + pd.Timedelta(days=1),
            }
        )
        for q in settings["targets"]:
            targets[f"target_{q * 100:g}pct"] = pd.Series(
                [1] * len(history), dtype="Int64"
            )
        records = []
        for q in settings["targets"]:
            for step, day in enumerate(days):
                records.append(
                    {
                        "feature_time_utc": day - pd.Timedelta(days=1),
                        "target_time_utc": day,
                        "actual": 1,
                        "predicted": pd.NA if step == 1 else 1,
                        "score": 1.0,
                        "role": "out_of_sample",
                        "model": "tuned_svc",
                        "status": "ok" if step != 1 else "single_class_training",
                        "fit_time_utc": days[0] - pd.Timedelta(milliseconds=1),
                        "prediction_time_utc": day - pd.Timedelta(milliseconds=1),
                        "symbol": symbol,
                        "window_size": 60,
                        "target": f"target_{q * 100:g}pct",
                        "block_id": step,
                    }
                )
        predictions = pd.DataFrame(records)
        predictions["predicted"] = predictions.predicted.astype("Int64")
        predictions["actual"] = predictions.actual.astype("Int64")
        for name, frame in {
            "features": features,
            "treated": treated,
            "targets": targets,
            "predictions": predictions,
        }.items():
            destination = (
                paths.audit(symbol, name)
                if name == "predictions"
                else paths.table(symbol, name)
            )
            results.write_table(frame, destination, context=signature)
    return paths, settings


def allocation_inputs(paths, settings):
    saved = experiment.load_portfolio_inputs(paths, settings)
    tables = saved["tables"]
    return {
        "predictions": pd.concat(tables["predictions"].values(), ignore_index=True),
        "features": {
            s: f[["feature_time_utc", "r1"]] for s, f in tables["features"].items()
        },
        "history_markers": {
            s: f[["date_utc", "is_imputed"]] for s, f in tables["treated"].items()
        },
        "symbols": saved["symbols"],
        "settings": settings,
    }


def test_minimum_variance_known_solution_and_single_asset(settings):
    portfolio.check_solver("CLARABEL")
    history = pd.DataFrame({"A": [-1.0, 1, -1, 1], "B": [-2.0, -2, 2, 2]})
    weights, _ = portfolio.minimum_variance_weights(history, settings["allocation"])
    assert weights == pytest.approx([0.8, 0.2], abs=1e-5)
    single, corrected = portfolio.minimum_variance_weights(
        history[["A"]], settings["allocation"]
    )
    assert single.tolist() == [1.0]
    assert not corrected
    with pytest.raises(ValueError, match="finite"):
        portfolio.minimum_variance_weights(
            history.assign(A=np.nan), settings["allocation"]
        )


@pytest.mark.parametrize(
    "actual,high,close,expected",
    [(1, 104, 99, 0.02), (0, 101, 100.5, 0.005), (0, 101, 99, -0.01), (0, 101, 100, 0)],
)
def test_realized_returns(actual, high, close, expected):
    candle = pd.Series(
        {
            "open": 100.0,
            "high": high,
            "low": 98.0,
            "close": close,
            "is_imputed": True,
            "source_date_utc": pd.Timestamp("2020-01-01", tz="UTC"),
        }
    )
    trade = backtesting.realized_trade(candle, actual, 0.02)
    assert trade["realized_return"] == pytest.approx(expected)
    assert trade["operation_is_imputed"]
    with pytest.raises(ValueError, match="disagrees"):
        backtesting.realized_trade(candle, 1 - actual, 0.02)


def test_alignment_zero_fill_and_reproducible_shared_draws(source_run):
    paths, settings = source_run
    args = allocation_inputs(paths, settings)
    first = portfolio.allocate_portfolios(**args)
    second = portfolio.allocate_portfolios(**args)
    pd.testing.assert_frame_equal(first.signals, second.signals)
    pd.testing.assert_frame_equal(first.weights, second.weights)
    missing = first.signals.original_prediction.isna()
    assert missing.sum() == 6
    assert first.signals.loc[missing, "effective_prediction"].eq(0).all()
    assert first.signals.loc[~missing, "effective_prediction"].eq(1).all()
    assert not first.signals.signal_reused.any()
    assert first.signals.loc[missing, "signal_source_date"].isna().all()
    assert first.signals.loc[missing, "signal_source_block"].isna().all()
    cash = first.weights[
        first.weights.operation_date.eq(
            first.signals.loc[missing, "operation_date"].iloc[0]
        )
        & first.weights.strategy.str.startswith("svm")
    ]
    assert cash.allocation_status.eq("no_eligible_selection").all()
    assert cash.weight.eq(0).all()
    assert (
        (first.signals.operation_date - first.signals.history_end)
        .eq(pd.Timedelta(days=1))
        .all()
    )
    assert (
        (first.signals.operation_date - first.signals.history_start)
        .eq(pd.Timedelta(days=60))
        .all()
    )
    for (_, _), group in first.weights[
        first.weights.strategy.str.startswith("random")
    ].groupby(["operation_date", "target"]):
        assert (
            group[group.strategy.eq("random_min_variance")].symbol.tolist()
            == group[group.strategy.eq("random_equal_weight")].symbol.tolist()
        )
    for (_, _, _), group in first.weights.groupby(
        ["operation_date", "target", "strategy"]
    ):
        assert group.weight.sum() == pytest.approx(
            1 if group.allocation_status.iloc[0] == "invested" else 0
        )


@pytest.mark.parametrize("drop_rows", [False, True])
def test_missing_signals_never_reuse_previous_block(source_run, drop_rows):
    paths, settings = source_run
    args = allocation_inputs(paths, settings)
    predictions = args["predictions"]
    dates = sorted(predictions.target_time_utc.unique())
    # Keep positive ETH signals to retain the full calendar, including absent rows.
    missing = predictions.symbol.eq("BTCUSDT") & predictions.target_time_utc.isin(
        dates[1:]
    )
    predictions.loc[missing, "predicted"] = pd.NA
    if drop_rows:
        predictions = predictions.loc[~missing].copy()
    signals = portfolio.effective_signals(predictions, args["symbols"], settings)
    btc = signals[signals.symbol.eq("BTCUSDT")]
    assert btc.loc[btc.operation_date.eq(dates[0]), "effective_prediction"].eq(1).all()
    absent = btc[btc.operation_date.isin(dates[1:])]
    assert len(absent) == 6
    assert absent.original_prediction.isna().all()
    assert absent.effective_prediction.eq(0).all()
    assert absent.signal_source_date.isna().all()
    assert absent.signal_source_block.isna().all()
    assert not signals.signal_reused.any()


def test_missing_initial_prediction_and_history_filter(source_run):
    paths, settings = source_run
    args = allocation_inputs(paths, settings)
    p = args["predictions"]
    first_day = p.target_time_utc.min()
    p.loc[p.symbol.eq("ETHUSDT") & p.target_time_utc.eq(first_day), "predicted"] = pd.NA
    args["features"]["BTCUSDT"] = args["features"]["BTCUSDT"].iloc[1:].copy()
    allocated = portfolio.allocate_portfolios(**args)
    day = allocated.signals[allocated.signals.operation_date.eq(first_day)]
    assert day[day.symbol.eq("ETHUSDT")].effective_prediction.eq(0).all()
    assert not day[day.symbol.eq("BTCUSDT")].history_eligible.any()
    assert (
        not allocated.weights.loc[
            allocated.weights.operation_date.eq(first_day), "symbol"
        ]
        .eq("BTCUSDT")
        .any()
    )
    assert (
        allocated.weights.loc[
            allocated.weights.operation_date.eq(first_day)
            & allocated.weights.strategy.str.startswith("svm"),
            "allocation_status",
        ]
        .eq("no_eligible_selection")
        .all()
    )


@pytest.mark.filterwarnings("error::FutureWarning")
@pytest.mark.parametrize("marker_dtype", ["bool", "boolean", "object"])
def test_history_imputation_count_with_missing_dates(source_run, marker_dtype):
    paths, settings = source_run
    args = allocation_inputs(paths, settings)
    symbol = "BTCUSDT"
    args["features"][symbol] = args["features"][symbol].iloc[1:].copy()
    markers = args["history_markers"][symbol].iloc[1:].copy()
    markers.loc[markers.index[0], "is_imputed"] = True
    markers["is_imputed"] = markers["is_imputed"].astype(marker_dtype)
    args["history_markers"][symbol] = markers

    allocated = portfolio.allocate_portfolios(**args)

    first_day = allocated.signals.operation_date.min()
    audit = allocated.signals[
        allocated.signals.operation_date.eq(first_day)
        & allocated.signals.symbol.eq(symbol)
    ]
    assert not audit.history_eligible.any()
    assert audit.history_imputed_days.eq(1).all()


def test_future_r1_does_not_change_prior_allocations(source_run):
    paths, settings = source_run
    args = allocation_inputs(paths, settings)
    baseline = portfolio.allocate_portfolios(**args)
    day = baseline.signals.operation_date.min()
    for frame in args["features"].values():
        frame.loc[frame.feature_time_utc.ge(day), "r1"] = 1000.0
    changed = portfolio.allocate_portfolios(**args)
    pd.testing.assert_frame_equal(
        baseline.weights[baseline.weights.operation_date.eq(day)],
        changed.weights[changed.weights.operation_date.eq(day)],
    )


def test_late_prediction_and_duplicate_are_rejected(source_run):
    paths, settings = source_run
    args = allocation_inputs(paths, settings)
    p = args["predictions"]
    p.loc[0, "prediction_time_utc"] = p.loc[0, "target_time_utc"]
    with pytest.raises(ValueError, match="unavailable"):
        portfolio.allocate_portfolios(**args)
    args["predictions"] = pd.concat([p, p.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate"):
        portfolio.allocate_portfolios(**args)


def test_solver_failure_holds_only_min_variance_in_cash(source_run, monkeypatch):
    paths, settings = source_run

    def fail(*args):
        raise ArithmeticError("simulated solver failure")

    monkeypatch.setattr(portfolio, "minimum_variance_weights", fail)
    allocated = portfolio.allocate_portfolios(**allocation_inputs(paths, settings))
    selected = allocated.weights[allocated.weights.strategy.eq("svm_min_variance")]
    assert selected.weight.eq(0).all()
    missing_day = allocated.signals.loc[
        allocated.signals.original_prediction.isna(), "operation_date"
    ].iloc[0]
    assert (
        selected.loc[selected.operation_date.eq(missing_day), "allocation_status"]
        .eq("no_eligible_selection")
        .all()
    )
    assert (
        selected.loc[selected.operation_date.ne(missing_day), "allocation_status"]
        .eq("optimization_failure")
        .all()
    )
    equal = allocated.weights[allocated.weights.strategy.eq("svm_equal_weight")]
    assert equal.loc[equal.operation_date.eq(missing_day), "weight"].eq(0).all()
    assert equal.loc[equal.operation_date.ne(missing_day), "weight"].eq(0.5).all()
    data = experiment.load_portfolio_inputs(paths, settings)["tables"]
    report = backtesting.simulate_capital(
        allocated.weights, data["treated"], data["targets"], settings
    )
    assert (
        report.capital.loc[
            report.capital.strategy.eq("svm_min_variance"), "closing_capital"
        ]
        .eq(10000)
        .all()
    )


def test_compounding_saved_targets_and_imputation(source_run):
    paths, settings = source_run
    data = experiment.load_portfolio_inputs(paths, settings)["tables"]
    allocated = portfolio.allocate_portfolios(**allocation_inputs(paths, settings))
    report = backtesting.simulate_capital(
        allocated.weights, data["treated"], data["targets"], settings
    )
    curve = report.capital[
        (report.capital.target == "target_2pct")
        & (report.capital.strategy == "svm_equal_weight")
    ]
    assert curve.closing_capital.tolist() == pytest.approx([10200, 10200, 10404])
    day = curve.operation_date.iloc[0]
    data["targets"]["BTCUSDT"].loc[
        data["targets"]["BTCUSDT"].target_time_utc.eq(day), "target_1pct"
    ] = 0
    with pytest.raises(ValueError, match="disagrees"):
        backtesting.simulate_capital(
            allocated.weights, data["treated"], data["targets"], settings
        )


def test_dependency_preflight(monkeypatch):
    import cvxpy

    monkeypatch.setattr(cvxpy, "installed_solvers", lambda: [])
    with pytest.raises(RuntimeError, match="unavailable"):
        portfolio.check_solver("CLARABEL")
    original = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name == "pypfopt":
            raise ImportError("missing")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    with pytest.raises(RuntimeError, match="Install"):
        portfolio.check_solver("CLARABEL")


def test_latest_source_no_fallback_and_tie(source_run):
    paths, settings = source_run
    assert experiment.latest_training_execution(paths.root).run_id == paths.run_id
    latest = Paths(paths.root, "newer")
    results.write_json(latest.execution, {"execution_time_utc": "2099-01-01T00:00:00Z"})
    assert experiment.latest_training_execution(paths.root).run_id == "newer"
    with pytest.raises(FileNotFoundError, match="configuration"):
        experiment.load_portfolio_inputs(latest, settings)
    tied = Paths(paths.root, "tied")
    results.write_json(tied.execution, {"execution_time_utc": "2099-01-01T00:00:00Z"})
    with pytest.raises(ValueError, match="ambiguous"):
        experiment.latest_training_execution(paths.root)


def test_config_rejects_unknown_options(settings):
    settings["history"]["lookahead"] = True
    with pytest.raises(ValueError, match="history"):
        validate_portfolio_config(settings)


def test_independent_command_roundtrip_and_overwrite(source_run, monkeypatch):
    paths, settings = source_run
    original = experiment.execute_portfolio

    def local(run_id, **kwargs):
        return original(run_id, root=paths.root, **kwargs)

    monkeypatch.setattr(experiment, "execute_portfolio", local)

    def forbidden(*args, **kwargs):
        pytest.fail("Classification stage was invoked by portfolio")

    for name in ("collect", "prepare", "build_datasets", "train", "consolidate", "run"):
        monkeypatch.setattr(experiment, name, forbidden)
    experiment.main(["portfolio", "--run-id", "test"])
    report = experiment.load_portfolio_report("test", root=paths.root)
    assert len(report["tables"]["capital"]) == 36
    assert report["source"]["run_id"] == paths.run_id
    assert str(report["tables"]["signals"].effective_prediction.dtype) == "Int64"
    with pytest.raises(FileExistsError, match="exists"):
        original("test", root=paths.root)
    original("test", root=paths.root, overwrite=True)
    again = experiment.load_portfolio_report("test", root=paths.root)
    for name in PORTFOLIO_TABLES:
        pd.testing.assert_frame_equal(report["tables"][name], again["tables"][name])
    p = paths.table("BTCUSDT", "features")
    p.write_text(p.read_text() + "\n")
    with pytest.raises(ValueError, match="modified"):
        experiment.load_portfolio_report("test", root=paths.root)


@pytest.mark.parametrize(
    "stage", ["collect", "prepare", "dataset", "train", "results", "run"]
)
def test_existing_commands_cannot_invoke_portfolio(stage, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Existing stage invoked portfolio")

    monkeypatch.setattr(experiment, "execute_portfolio", forbidden)
    for name in ("collect", "prepare", "build_datasets", "train", "consolidate", "run"):
        monkeypatch.setattr(experiment, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(results, "read_table", lambda *args, **kwargs: pd.DataFrame())
    experiment.main([stage, "--run-id", "unused", "--symbols", "BTCUSDT"])


def test_atomic_failure_lock_and_recovery(source_run, monkeypatch):
    paths, settings = source_run
    experiment.execute_portfolio("test", root=paths.root)
    dest = PortfolioPaths(paths.root, "test")
    before = results.file_sha256(dest.artifact("complete"))
    dest.lock.mkdir()
    with pytest.raises(FileExistsError, match="locked"):
        experiment.execute_portfolio("test", root=paths.root, overwrite=True)
    with pytest.raises(ValueError, match="locked"):
        experiment.load_portfolio_report("test", root=paths.root)
    dest.lock.rmdir()
    original = results.write_table

    def interrupted(frame, path, **kwargs):
        if path.name == "signals.csv":
            raise OSError("simulated interruption")
        return original(frame, path, **kwargs)

    monkeypatch.setattr(results, "write_table", interrupted)
    with pytest.raises(OSError, match="interruption"):
        experiment.execute_portfolio("test", root=paths.root, overwrite=True)
    assert not dest.lock.exists()
    assert results.file_sha256(dest.artifact("complete")) == before
    experiment.load_portfolio_report("test", root=paths.root)
    assert not list(dest.output.parent.glob(".*staging*"))


def test_report_rejects_incomplete_and_tampered(source_run):
    paths, settings = source_run
    with pytest.raises(ValueError, match="Incomplete"):
        experiment.load_portfolio_report("missing", root=paths.root)
    experiment.execute_portfolio("test", root=paths.root)
    dest = PortfolioPaths(paths.root, "test")
    dest.artifact("capital").write_text("modified")
    with pytest.raises(ValueError, match="modified"):
        experiment.load_portfolio_report("test", root=paths.root)


def test_notebook_actual_cells_use_saved_curves(source_run):
    import matplotlib.pyplot as plt

    paths, settings = source_run
    experiment.execute_portfolio("test", root=paths.root)
    report = experiment.load_portfolio_report("test", root=paths.root)
    notebook = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "notebooks/19_binance_daily_portfolio_results_visual_report.ipynb"
        ).read_text()
    )
    scope = {"report": report, "pd": pd, "plt": plt, "display": lambda value: None}
    figures = []
    for cell in notebook["cells"]:
        tags = cell.get("metadata", {}).get("tags", [])
        if "portfolio-summary" in tags or "report-chart" in tags:
            exec(compile("".join(cell["source"]), "portfolio-notebook", "exec"), scope)
        if "report-chart" in tags:
            figures.append(scope["fig"])
    assert len(figures) == 3
    for fig in figures:
        assert len(fig.axes[0].lines) == 4
        for line in fig.axes[0].lines:
            assert line.get_ydata()[0] == 10000
            assert len(line.get_ydata()) == 4
        plt.close(fig)


@pytest.mark.parametrize(
    "raw,should_fail",
    [
        ([0.500000003, 0.500000003], False),
        ([-0.1, 1.1], True),
        ([np.nan, 1.0], True),
        ([0.2, 0.2], True),
    ],
)
def test_weight_validation_and_bounded_correction(
    settings, monkeypatch, raw, should_fail
):
    from pypfopt import EfficientFrontier

    def returned(self):
        self.weights = np.array(raw)
        return dict(zip(self.tickers, raw))

    monkeypatch.setattr(EfficientFrontier, "min_volatility", returned)
    history = pd.DataFrame({"A": [1.0, 2, 3], "B": [3.0, 1, 2]})
    if should_fail:
        with pytest.raises(ArithmeticError, match="invalid"):
            portfolio.minimum_variance_weights(history, settings["allocation"])
    else:
        weights, corrected = portfolio.minimum_variance_weights(
            history, settings["allocation"]
        )
        assert corrected
        assert weights.tolist() == pytest.approx([0.5, 0.5])


def test_no_eligible_assets_preserves_capital_and_nullable_results(source_run):
    paths, settings = source_run
    args = allocation_inputs(paths, settings)
    args["features"] = {
        symbol: frame.iloc[:0] for symbol, frame in args["features"].items()
    }
    allocated = portfolio.allocate_portfolios(**args)
    assert allocated.weights.allocation_status.eq("no_eligible_selection").all()
    data = experiment.load_portfolio_inputs(paths, settings)["tables"]
    evaluated = backtesting.simulate_capital(
        allocated.weights, data["treated"], data["targets"], settings
    )
    assert evaluated.capital.closing_capital.eq(10000).all()
    assert evaluated.operations.actual.isna().all()
    assert evaluated.operations.operation_is_imputed.isna().all()


def test_future_actuals_do_not_enter_allocation(source_run):
    paths, settings = source_run
    args = allocation_inputs(paths, settings)
    baseline = portfolio.allocate_portfolios(**args)
    args["predictions"]["actual"] = 0
    changed = portfolio.allocate_portfolios(**args)
    pd.testing.assert_frame_equal(baseline.weights, changed.weights)
    pd.testing.assert_frame_equal(baseline.signals, changed.signals)


def test_missing_invested_candle_stops_evaluation(source_run):
    paths, settings = source_run
    allocated = portfolio.allocate_portfolios(**allocation_inputs(paths, settings))
    data = experiment.load_portfolio_inputs(paths, settings)["tables"]
    day = allocated.weights.operation_date.min()
    data["treated"]["BTCUSDT"] = data["treated"]["BTCUSDT"].loc[
        lambda frame: frame.date_utc.ne(day)
    ]
    with pytest.raises(ValueError, match="Missing saved operation"):
        backtesting.simulate_capital(
            allocated.weights, data["treated"], data["targets"], settings
        )


def test_overwrite_rejects_changed_configuration(source_run, tmp_path):
    paths, settings = source_run
    experiment.execute_portfolio("test", root=paths.root)
    settings["experiment_id"] = "another_portfolio"
    config = tmp_path / "other.json"
    config.write_text(json.dumps(settings))
    with pytest.raises(ValueError, match="context changed"):
        experiment.execute_portfolio(
            "test", root=paths.root, config_path=config, overwrite=True
        )
    experiment.load_portfolio_report("test", root=paths.root)


def test_publish_rename_failure_restores_old_generation(source_run, monkeypatch):
    paths, settings = source_run
    experiment.execute_portfolio("test", root=paths.root)
    destination = PortfolioPaths(paths.root, "test")
    digest = results.file_sha256(destination.artifact("complete"))
    rename = Path.rename

    def fail_staging(path, target):
        if ".staging-" in path.name:
            raise OSError("simulated rename failure")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_staging)
    with pytest.raises(OSError, match="rename failure"):
        experiment.execute_portfolio("test", root=paths.root, overwrite=True)
    assert results.file_sha256(destination.artifact("complete")) == digest
    experiment.load_portfolio_report("test", root=paths.root)


def test_source_change_during_read_is_rejected(source_run, monkeypatch):
    paths, settings = source_run
    read = results.read_table

    def changed(path, **kwargs):
        frame = read(path, **kwargs)
        if path == paths.table("BTCUSDT", "features"):
            altered = frame.copy()
            altered["r1"] += 0.1
            results.write_table(
                altered, path, context=kwargs["context"], overwrite=True
            )
        return frame

    monkeypatch.setattr(results, "read_table", changed)
    with pytest.raises(ValueError, match="modified portfolio source"):
        experiment.load_portfolio_inputs(paths, settings)


def test_explicit_source_cli_overrides_latest(source_run, monkeypatch):
    paths, settings = source_run
    original = experiment.execute_portfolio

    def local(run_id, **kwargs):
        return original(run_id, root=paths.root, **kwargs)

    def forbidden(*args):
        pytest.fail("Explicit source must bypass latest-run discovery")

    monkeypatch.setattr(experiment, "execute_portfolio", local)
    monkeypatch.setattr(experiment, "latest_training_execution", forbidden)
    experiment.main(
        ["portfolio", "--run-id", "explicit", "--source-run-id", paths.run_id]
    )
    report = experiment.load_portfolio_report("explicit", root=paths.root)
    assert report["source"]["run_id"] == paths.run_id
    assert report["execution"]["source_selection"] == "explicit"
    with pytest.raises(FileNotFoundError):
        original("missing", root=paths.root, source_run_id="absent")


def test_source_option_rejected_for_classification():
    with pytest.raises(SystemExit):
        experiment.main(
            ["train", "--run-id", "test", "--all-symbols", "--source-run-id", "full_01"]
        )


def test_explicit_source_id_validation(source_run):
    paths, settings = source_run
    with pytest.raises(ValueError, match="Invalid path component"):
        experiment.execute_portfolio("test", root=paths.root, source_run_id="../other")
