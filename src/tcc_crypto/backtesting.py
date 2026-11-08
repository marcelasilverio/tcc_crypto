"""Same-day execution and compounded capital from explicit fixed allocations."""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestTables:
    capital: pd.DataFrame
    operations: pd.DataFrame


def realized_trade(candle: pd.Series, actual: object, threshold: float) -> dict:
    """Evaluate a target exit or closing exit using treated daily OHLC prices."""
    prices = np.asarray(
        [candle.open, candle.high, candle.low, candle.close], dtype=float
    )
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("An invested operation requires finite positive OHLC prices.")
    if candle.low > min(candle.open, candle.close) or candle.high < max(
        candle.open, candle.close
    ):
        raise ValueError("Inconsistent OHLC prices for an invested operation.")
    if pd.isna(actual) or actual not in (0, 1):
        raise ValueError("An invested operation requires a saved binary actual target.")
    hit = candle.high / candle.open - 1 >= threshold
    if bool(actual) != hit:
        raise ValueError("Saved actual target disagrees with its treated candle.")
    if pd.isna(candle.is_imputed) or pd.isna(candle.source_date_utc):
        raise ValueError("Operation imputation provenance is missing.")
    return {
        "entry_price": float(candle.open),
        "exit_price": float(candle.open * (1 + threshold) if hit else candle.close),
        "actual": int(actual),
        "realized_return": float(threshold if hit else candle.close / candle.open - 1),
        "operation_is_imputed": bool(candle.is_imputed),
        "candle_source_date": candle.source_date_utc,
    }


def simulate_capital(
    allocations: pd.DataFrame,
    candles: dict[str, pd.DataFrame],
    targets: dict[str, pd.DataFrame],
    settings: dict,
) -> BacktestTables:
    """Apply fixed daily allocations and compound each strategy/target independently."""
    if (
        allocations.empty
        or allocations.duplicated(
            ["operation_date", "target", "strategy", "symbol"]
        ).any()
    ):
        raise ValueError("Allocations must be nonempty and have unique coordinates.")
    if not allocations.allocation_status.isin(
        ["invested", "no_eligible_selection", "optimization_failure"]
    ).all():
        raise ValueError("Unknown allocation status.")
    if not isinstance(allocations.operation_date.dtype, pd.DatetimeTZDtype):
        raise ValueError("Allocations require UTC operation dates.")
    if str(allocations.operation_date.dt.tz) != "UTC":
        raise ValueError("Allocations require UTC operation dates.")
    prices = {s: frame.set_index("date_utc") for s, frame in candles.items()}
    actuals = {s: frame.set_index("target_time_utc") for s, frame in targets.items()}
    thresholds = {f"target_{q * 100:g}pct": q for q in settings["targets"]}
    expected = pd.MultiIndex.from_product(
        [
            pd.date_range(
                allocations.operation_date.min(),
                allocations.operation_date.max(),
                freq="D",
            ),
            list(thresholds),
            settings["strategies"],
        ],
        names=["operation_date", "target", "strategy"],
    )
    observed = pd.MultiIndex.from_frame(
        allocations[["operation_date", "target", "strategy"]].drop_duplicates()
    )
    if len(expected.difference(observed)) or len(observed.difference(expected)):
        raise ValueError("Allocations must cover every day, target and strategy.")
    balances = {
        (target, strategy): float(settings["capital"]["initial"])
        for target in thresholds
        for strategy in settings["strategies"]
    }
    daily_rows, operations = [], []
    for (day, target, strategy), group in allocations.groupby(
        ["operation_date", "target", "strategy"], sort=True
    ):
        initial = balances[target, strategy]
        statuses = group.allocation_status.unique()
        if len(statuses) != 1:
            raise ValueError("Conflicting allocation statuses in a daily portfolio.")
        status = statuses[0]
        weights = group.weight.to_numpy(dtype=float)
        invested = status == "invested"
        if not np.isfinite(weights).all() or (weights < 0).any():
            raise ValueError("Invalid fixed allocations.")
        if (
            invested
            and abs(weights.sum() - 1) > settings["allocation"]["weight_tolerance"]
        ):
            raise ValueError("Invested weights must sum to one.")
        if not invested and weights.any():
            raise ValueError("Cash portfolios cannot contain positive weights.")
        final_values = []
        for record in group.to_dict("records"):
            weight, symbol = record["weight"], record["symbol"]
            amount = initial * weight
            trade = {
                "entry_price": np.nan,
                "exit_price": np.nan,
                "actual": pd.NA,
                "realized_return": np.nan,
                "operation_is_imputed": pd.NA,
                "candle_source_date": pd.NaT,
            }
            final_value, units = 0.0, 0.0
            if weight > 0:
                if (
                    symbol not in prices
                    or day not in prices[symbol].index
                    or day not in actuals[symbol].index
                ):
                    raise ValueError(
                        f"Missing saved operation data for {symbol} on {day}."
                    )
                trade = realized_trade(
                    prices[symbol].loc[day],
                    actuals[symbol].loc[day, target],
                    thresholds[target],
                )
                final_value = amount * (1 + trade["realized_return"])
                units = amount / trade["entry_price"]
                final_values.append(final_value)
            operations.append(
                {
                    **record,
                    **trade,
                    "allocated_capital": amount,
                    "units": units,
                    "final_value": final_value,
                }
            )
        final = math.fsum(final_values) if invested else initial
        if not math.isfinite(final) or final <= 0:
            raise ArithmeticError("Capital must remain finite and positive.")
        balances[target, strategy] = final
        daily_rows.append(
            {
                "operation_date": day,
                "target": target,
                "strategy": strategy,
                "opening_capital": initial,
                "closing_capital": final,
                "daily_return": final / initial - 1,
                "cash_capital": 0.0 if invested else initial,
                "asset_count": int((weights > 0).sum()),
                "cash_reason": "" if invested else status,
            }
        )
    trades = pd.DataFrame(operations)
    trades["actual"] = trades.actual.astype("Int64")
    trades["operation_is_imputed"] = trades.operation_is_imputed.astype("boolean")
    trades["candle_source_date"] = pd.to_datetime(trades.candle_source_date, utc=True)
    return BacktestTables(pd.DataFrame(daily_rows), trades)
