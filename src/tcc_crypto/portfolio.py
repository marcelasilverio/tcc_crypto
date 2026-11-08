"""Daily signals and allocations using historical returns only."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AllocationTables:
    signals: pd.DataFrame
    weights: pd.DataFrame


def check_solver(solver: str) -> None:
    """Fail before simulation if the declared optimization environment is absent."""
    try:
        import cvxpy
        import pypfopt  # noqa: F401
    except ImportError as error:
        raise RuntimeError(
            "Install project dependencies, including PyPortfolioOpt."
        ) from error
    if solver not in cvxpy.installed_solvers():
        raise RuntimeError(f"Required portfolio solver {solver} is unavailable.")


def minimum_variance_weights(
    history: pd.DataFrame, settings: dict
) -> tuple[np.ndarray, bool]:
    """Minimize daily sample variance; correct only bounded floating-point residue.

    Invalid inputs raise ValueError before optimization. Solver failures and
    infeasible returned weights raise ArithmeticError for the approved cash rule.
    """
    values = history.to_numpy(dtype=float)
    if len(history) < 2 or history.shape[1] == 0 or not np.isfinite(values).all():
        raise ValueError("Covariance requires complete finite return histories.")
    if history.shape[1] == 1:
        return np.ones(1), False
    from cvxpy.error import SolverError
    from pypfopt import EfficientFrontier
    from pypfopt.exceptions import OptimizationError

    covariance = history.cov(ddof=settings["covariance_ddof"])
    try:
        optimizer = EfficientFrontier(
            None,
            covariance,
            weight_bounds=tuple(settings["weight_bounds"]),
            solver=settings["solver"],
        )
        optimizer.min_volatility()
    except (SolverError, OptimizationError, ValueError) as error:
        raise ArithmeticError(f"{type(error).__name__}: {error}") from error
    weights = np.asarray(optimizer.weights, dtype=float)
    tolerance = settings["weight_tolerance"]
    if (
        weights.shape != (history.shape[1],)
        or not np.isfinite(weights).all()
        or (weights < -tolerance).any()
        or (weights > 1 + tolerance).any()
        or abs(weights.sum() - 1) > tolerance
    ):
        raise ArithmeticError("Optimizer returned invalid portfolio weights.")
    corrected = np.clip(weights, 0, 1)
    corrected /= corrected.sum()
    return corrected, not np.array_equal(weights, corrected)


def _dated(frame: pd.DataFrame, column: str, name: str) -> pd.DataFrame:
    """Require unique ordered UTC calendar dates without compressing missing days."""
    dates = frame[column]
    if not isinstance(dates.dtype, pd.DatetimeTZDtype) or str(dates.dt.tz) != "UTC":
        raise ValueError(f"{name} requires UTC timestamps.")
    if (
        dates.isna().any()
        or dates.duplicated().any()
        or not dates.is_monotonic_increasing
    ):
        raise ValueError(f"{name} has missing, duplicate or unordered timestamps.")
    if not dates.eq(dates.dt.normalize()).all():
        raise ValueError(f"{name} requires daily midnight timestamps.")
    return frame.set_index(column)


def effective_signals(
    predictions: pd.DataFrame, symbols: list[str], settings: dict
) -> pd.DataFrame:
    """Align saved predictions to operation dates and forward-fill within each target."""
    expected_targets = [f"target_{q * 100:g}pct" for q in settings["targets"]]
    source = settings["source"]
    rows = predictions.loc[
        predictions.model.eq(source["model"])
        & predictions.role.eq(source["sample_role"])
        & predictions.window_size.eq(source["training_window_days"])
    ].copy()
    if (
        rows.empty
        or set(rows.symbol) != set(symbols)
        or set(rows.target) != set(expected_targets)
    ):
        raise ValueError("Saved training lacks required portfolio symbols or targets.")
    if rows.duplicated(["symbol", "target", "target_time_utc"]).any():
        raise ValueError("Duplicate out-of-sample prediction coordinates.")
    for column in (
        "feature_time_utc",
        "target_time_utc",
        "fit_time_utc",
        "prediction_time_utc",
    ):
        if (
            not isinstance(rows[column].dtype, pd.DatetimeTZDtype)
            or str(rows[column].dt.tz) != "UTC"
        ):
            raise ValueError(f"Prediction column {column} requires UTC timestamps.")
    if not rows.target_time_utc.eq(rows.feature_time_utc + pd.Timedelta(days=1)).all():
        raise ValueError("Predictions must refer to the next daily candle.")
    if not rows.target_time_utc.eq(rows.target_time_utc.dt.normalize()).all():
        raise ValueError("Prediction operation dates must be midnight UTC.")
    valid = rows.predicted.notna()
    if not rows.loc[valid, "predicted"].isin([0, 1]).all():
        raise ValueError("Predictions must be binary or missing.")
    available = rows.loc[valid]
    if (
        available[["fit_time_utc", "prediction_time_utc"]].isna().any().any()
        or not available.fit_time_utc.le(available.prediction_time_utc).all()
        or not available.prediction_time_utc.lt(available.target_time_utc).all()
        or not available.prediction_time_utc.ge(
            available.feature_time_utc
            + pd.Timedelta(days=1)
            - pd.Timedelta(milliseconds=1)
        ).all()
    ):
        raise ValueError("Prediction or fit was unavailable before the operation open.")
    calendar = pd.date_range(
        rows.target_time_utc.min(), rows.target_time_utc.max(), freq="D"
    )
    panels = []
    for target in expected_targets:
        for symbol in symbols:
            part = rows.loc[
                rows.target.eq(target) & rows.symbol.eq(symbol)
            ].sort_values("target_time_utc")
            if part.empty:
                raise ValueError(f"Missing saved training for {symbol}, {target}.")
            panel = part.set_index("target_time_utc").reindex(calendar)
            original = panel.predicted.astype("Int64")
            signal = original.ffill()
            source_day = (
                pd.Series(panel.index, index=panel.index)
                .where(original.notna())
                .ffill()
            )
            panels.append(
                pd.DataFrame(
                    {
                        "operation_date": calendar,
                        "symbol": symbol,
                        "target": target,
                        "original_prediction": original.array,
                        "effective_prediction": signal.array,
                        "signal_source_date": source_day.array,
                        "signal_source_block": panel.block_id.where(original.notna())
                        .ffill()
                        .astype("Int64")
                        .array,
                        "signal_reused": (original.isna() & signal.notna()).array,
                    }
                )
            )
    return pd.concat(panels, ignore_index=True)


def allocate_portfolios(
    predictions: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    history_markers: dict[str, pd.DataFrame],
    symbols: list[str],
    settings: dict,
) -> AllocationTables:
    """Calculate allocations without receiving operation-day prices or targets."""
    signals = effective_signals(predictions, symbols, settings)
    indexed = signals.set_index(["operation_date", "target", "symbol"])
    histories = {s: _dated(features[s], "feature_time_utc", s)["r1"] for s in symbols}
    markers = {
        s: _dated(history_markers[s], "date_utc", s)["is_imputed"] for s in symbols
    }
    rng = np.random.Generator(np.random.PCG64(settings["random_signals"]["seed"]))
    audit_rows, allocation_rows = [], []
    for day in sorted(signals.operation_date.unique()):
        dates = pd.date_range(
            day - pd.Timedelta(days=settings["history"]["window_days"]),
            periods=settings["history"]["window_days"],
            freq="D",
        )
        history = pd.DataFrame(
            {s: histories[s].reindex(dates) for s in symbols}, index=dates
        )
        finite_counts = np.isfinite(history.to_numpy(dtype=float)).sum(axis=0)
        eligible = dict(zip(symbols, finite_counts == len(dates), strict=True))
        for q in settings["targets"]:
            target = f"target_{q * 100:g}pct"
            random_signals = rng.binomial(
                1, settings["random_signals"]["positive_probability"], len(symbols)
            )
            selection = {"svm": [], "random": []}
            for position, symbol in enumerate(symbols):
                saved = indexed.loc[(day, target, symbol)]
                imputed = markers[symbol].reindex(dates)
                if eligible[symbol] and imputed.isna().any():
                    raise ValueError(
                        f"Missing history imputation markers for {symbol} on {day}."
                    )
                svm_positive = (
                    pd.notna(saved.effective_prediction)
                    and saved.effective_prediction == 1
                )
                if eligible[symbol] and svm_positive:
                    selection["svm"].append(symbol)
                if eligible[symbol] and random_signals[position] == 1:
                    selection["random"].append(symbol)
                audit_rows.append(
                    {
                        "operation_date": day,
                        "target": target,
                        "symbol": symbol,
                        **saved.to_dict(),
                        "random_signal": int(random_signals[position]),
                        "history_start": dates[0],
                        "history_end": dates[-1],
                        "history_observations": int(finite_counts[position]),
                        "history_imputed_days": int(imputed.fillna(False).sum()),
                        "history_eligible": bool(eligible[symbol]),
                        "exclusion_reason": ""
                        if eligible[symbol]
                        else "insufficient_history",
                    }
                )
            for strategy in settings["strategies"]:
                selected = selection[strategy.split("_", 1)[0]]
                status, diagnostic, corrected = "invested", "", False
                weights = np.zeros(len(selected))
                if not selected:
                    status = "no_eligible_selection"
                elif strategy.endswith("equal_weight"):
                    weights = np.full(len(selected), 1 / len(selected))
                else:
                    try:
                        weights, corrected = minimum_variance_weights(
                            history[selected], settings["allocation"]
                        )
                    except ArithmeticError as error:
                        status, diagnostic = "optimization_failure", str(error)
                for position, symbol in enumerate(selected or [None]):
                    allocation_rows.append(
                        {
                            "operation_date": day,
                            "target": target,
                            "strategy": strategy,
                            "symbol": symbol,
                            "weight": float(weights[position]) if selected else 0.0,
                            "allocation_status": status,
                            "optimizer_diagnostic": diagnostic,
                            "weights_corrected": corrected,
                        }
                    )
    audit = pd.DataFrame(audit_rows)
    for column in (
        "original_prediction",
        "effective_prediction",
        "signal_source_block",
        "random_signal",
    ):
        audit[column] = audit[column].astype("Int64")
    audit["signal_source_date"] = pd.to_datetime(audit.signal_source_date, utc=True)
    return AllocationTables(audit, pd.DataFrame(allocation_rows))
