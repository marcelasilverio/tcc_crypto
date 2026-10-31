# Exploratory refactor references

Reference computations use the implementation at commit `8f91d79`, preserved
before any source extraction. They use small synthetic OHLC and activity values;
no external data or network access is required.

`input.json` has an internal UTC calendar gap and supports comparisons of hourly
statistics, daily/semester statistics, extrema and D0–D3 outcomes. These tables
were captured directly before moving the corresponding implementations.

`market_raw.json` contains two monthly candles spanning a UTC year boundary and
two daily candles separated by a missing day. `monthly.json`, `annual.json` and
`trade_counts.json` were computed by executing the original notebook functions
and aggregation statements from the preserved source, with HTTP calls replaced
by these records. The current monthly candle remains partial; the current year
remains year-to-date. Trade counts retain the internal missing-day diagnostic.

Comparisons allow 1e-12 floating-point tolerance. These fixtures document
existing behavior; they do not approve new scientific parameters. Never
regenerate the expected tables from the refactored implementation.
