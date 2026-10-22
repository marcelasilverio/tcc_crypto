"""Features: catalog."""

from __future__ import annotations

ACTIVE_FEATURES = (
    "r1",
    "r2",
    "r3",
    "r4",
    "r5",
    "r6",
    "r7",
    "r8",
    "r9",
    "r10",
    "r11",
    "r12",
    "r13",
    "r14",
    "r15",
    "momentum_10",
    "rsi_14",
    "parabolic_sar",
    "atr_14",
    "true_range",
    "chaikin_ad",
    "obv",
)


# Descriptive metadata only. Executable formulas live in price.py / indicators.py.
PRICE_FORMULAS = (
    "ln(close[t] / close[t-1])",
    "ln(close[t-1] / close[t-2])",
    "ln(close[t-2] / close[t-3])",
    "ln(close[t-3] / close[t-4])",
    "ln(high[t] / open[t])",
    "ln(high[t] / open[t-1])",
    "ln(high[t] / open[t-2])",
    "ln(high[t] / open[t-3])",
    "ln(high[t-1] / open[t-1])",
    "ln(high[t-2] / open[t-2])",
    "ln(high[t-3] / open[t-3])",
    "ln(low[t] / open[t])",
    "ln(low[t-1] / open[t-1])",
    "ln(low[t-2] / open[t-2])",
    "ln(low[t-3] / open[t-3])",
)
INDICATOR_DEFINITIONS = (
    ("momentum_10", "close[t] - close[t-10]", "close", "period=10", "momentum", "USDT"),
    (
        "rsi_14",
        "100 - 100/(1 + Wilder average gain / average loss)",
        "close",
        "period=14; flat=0; no loss=100",
        "_wilder_rsi",
        "0-100",
    ),
    (
        "parabolic_sar",
        "TA-Lib SAR(high, low)",
        "high, low",
        "acceleration=0; maximum=0; VERIFICATION PENDING",
        "parabolic_sar",
        "USDT",
    ),
    (
        "atr_14",
        "Wilder smoothed True Range; initial arithmetic mean",
        "high, low, close",
        "period=14",
        "_wilder_atr",
        "USDT",
    ),
    (
        "true_range",
        "max(high-low, abs(high-previous close), abs(low-previous close))",
        "high, low, close",
        "first row missing",
        "_true_range",
        "USDT",
    ),
    (
        "chaikin_ad",
        "cumsum(((close-low)-(high-close))/(high-low) * volume)",
        "high, low, close, quote_asset_volume",
        "zero high-low gives multiplier 0",
        "_chaikin_ad",
        "USDT volume",
    ),
    (
        "obv",
        "cumsum(sign(close[t]-close[t-1]) * volume[t])",
        "close, quote_asset_volume",
        "first observation contributes positive volume",
        "_on_balance_volume",
        "USDT volume",
    ),
)


def feature_definitions() -> list[dict[str, str]]:
    """Describe the same ordered feature set used in calculations and workbooks."""
    rows = [
        {
            "Feature": f"r{i}",
            "Formula": formula,
            "Inputs": "daily OHLC",
            "Parameters": "natural log; exact daily lags",
            "Unit": "dimensionless",
            "Implementation": "tcc_crypto.features.price.calculate_price_features",
        }
        for i, formula in enumerate(PRICE_FORMULAS, 1)
    ]
    rows.extend(
        {
            "Feature": name,
            "Formula": formula,
            "Inputs": inputs,
            "Parameters": parameters,
            "Unit": unit,
            "Implementation": f"tcc_crypto.features.indicators.{function}",
        }
        for name, formula, inputs, parameters, function, unit in INDICATOR_DEFINITIONS
    )
    return rows
