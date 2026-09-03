# Methodology decisions

## Exploratory USDT pair trade-count collection

Approved on 2026-09-02 for the exploratory notebook
`notebooks/04_binance_usdt_quote_pair_trade_count.ipynb`:

- market: Binance Spot;
- quote asset: USDT;
- observation start: 2017-01-01 00:00:00 UTC;
- observation end: the end of the previous UTC calendar day at execution time;
- interval used for aggregation: daily (`1d`) klines;
- activity measure: the sum of Binance's `number_of_trades` kline field for
  each trading symbol;
- symbol-status treatment: do not filter the symbols returned by the current
  `/api/v3/exchangeInfo` response by status;
- timezone: UTC.

This is an exploratory data-collection decision and does not freeze the final
experimental asset universe or sample period.

The symbol universe is limited to records present in the current
`exchangeInfo` response. Binance describes that endpoint as current exchange
information, so this procedure must not be described as a complete historical
catalog of symbols that were removed from the response. A separate approved
historical-symbol source would be required to make that stronger claim.

## Initial cryptocurrency selection for hourly data collection

Approved on 2026-09-02 as the initial data-collection universe:

- selection source:
  `data/exploration/binance_spot_usdt_quote_pair_trade_counts.xlsx`;
- ranking measure: total Binance `number_of_trades` accumulated from the first
  available daily kline through 2026-09-01 UTC;
- market and quote asset: Binance Spot pairs quoted in USDT;
- eligibility at the selection snapshot: current status must be `TRADING`;
- stablecoin treatment: exclude pairs whose base asset is a stablecoin;
- selection size: the 30 highest-ranked eligible pairs;
- hourly collection start: 2017-01-01 00:00:00 UTC;
- hourly collection end: 2026-09-01 23:59:59.999 UTC;
- candle interval: hourly (`1h`), aligned to UTC;
- listing treatment: each pair begins at its first available Binance candle;
  timestamps before listing are not synthesized or classified as missing;
- missing-candle treatment: preserve gaps in raw data and report missing hourly
  openings within each pair's observed span for review;
- raw output organization: one directory per trading pair under
  `data/raw/binance/spot/1h/`;
- canonical raw format: one immutable gzip-compressed CSV per pair, preserving
  the decimal fields returned by Binance as text;
- review output: one derived Excel workbook per pair with kline, metadata,
  validation, and missing-interval sheets;
- provenance output: one JSON sidecar per pair with checksums and validation
  results, plus a timestamped collection manifest;
- interruption treatment: persist a mutable page-level checkpoint while a pair
  is incomplete, resume after the last persisted page, and remove checkpoints
  only after all final pair artifacts are created;
- existing-output treatment: validate the canonical CSV, period coverage,
  workbook structure, row counts, and checksums before treating a pair as
  complete; never infer canonical raw data from an Excel workbook.

Historical candle-duration treatment approved on 2026-09-02:

- preserve a candle when its close timestamp is earlier than the final
  millisecond of its nominal hour but remains at or after its open timestamp;
- classify these shortened candles as `REVIEW`, not `FAIL`;
- record every shortened candle in the workbook's `Nonstandard Durations`
  sheet and summarize its count in metadata and the collection manifest;
- keep a close timestamp earlier than the open timestamp or beyond the nominal
  hourly window as a fatal validation failure;
- do not alter, extend, discard, or synthesize the raw candle during
  collection; any modeling-stage treatment remains a separate decision.

The approved initial selection, in descending ranking order, is:

1. `BTCUSDT`
2. `FLOKIUSDT`
3. `ETHUSDT`
4. `BONKUSDT`
5. `SOLUSDT`
6. `XRPUSDT`
7. `SHIBUSDT`
8. `DOGEUSDT`
9. `BNBUSDT`
10. `ADAUSDT`
11. `LTCUSDT`
12. `PEPEUSDT`
13. `SUIUSDT`
14. `LINKUSDT`
15. `AVAXUSDT`
16. `DOTUSDT`
17. `TRXUSDT`
18. `WIFUSDT`
19. `NEARUSDT`
20. `NEIROUSDT`
21. `AAVEUSDT`
22. `WLDUSDT`
23. `XLMUSDT`
24. `ZECUSDT`
25. `FILUSDT`
26. `BCHUSDT`
27. `LUNAUSDT`
28. `UNIUSDT`
29. `GALAUSDT`
30. `FETUSDT`

The stablecoin pairs removed while applying this rule were `USDCUSDT`,
`BUSDUSDT`, and `FDUSDUSDT`. The pairs removed because their current status was
`BREAK` were `BUSDUSDT`, `MATICUSDT`, and `FTMUSDT`; `BUSDUSDT` belongs to both
excluded groups.

This is an initial collection universe, not the final backtest universe. The
ranking uses activity observed through 2026-09-01 and the eligibility rule uses
the current symbol catalog and status. Applying this fixed selection to earlier
historical portfolio decisions would introduce look-ahead and survivorship
bias. Any final experimental eligibility rule must use only information
available at the corresponding decision timestamp or explicitly characterize
the experiment as an ex-post fixed-universe analysis.

The `LUNAUSDT` daily coverage used for selection contains 17 missing days and
spans the Terra ecosystem migration. Symbol and price-series continuity must
be validated before the pair is used in modeling or backtesting.
