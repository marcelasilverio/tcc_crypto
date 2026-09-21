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

### Expansion to 40 pairs

Approved on 2026-09-05 for hourly data collection:

- retain the initial 30 pairs and their ranking order;
- add the next 10 highest-ranked eligible pairs from the same selection
  workbook and snapshot;
- keep the ranking measure, eligibility rules, collection interval, requested
  date range, listing treatment, output formats, validation rules, and
  immutability rules unchanged;
- interpret "volume" in this expansion request as the already approved
  activity measure, total Binance `number_of_trades`, rather than base-asset or
  quote-asset volume.

The added pairs, continuing the approved ranking order, are:

31. `HBARUSDT` — 277,362,059 trades
32. `VETUSDT` — 274,259,884 trades
33. `ETCUSDT` — 263,371,631 trades
34. `ATOMUSDT` — 262,860,917 trades
35. `SANDUSDT` — 257,547,013 trades
36. `ENAUSDT` — 256,503,604 trades
37. `ICPUSDT` — 240,635,578 trades
38. `CRVUSDT` — 232,297,531 trades
39. `MANAUSDT` — 230,327,720 trades
40. `CHZUSDT` — 229,916,648 trades

`EOSUSDT` ranks between `HBARUSDT` and `VETUSDT` in the unfiltered workbook,
but it is excluded because its current status in the selection snapshot is
`BREAK`. No additional stablecoin pair occurs between ranks 31 and 40 after
the existing eligibility filters are applied.

This expansion changes only the collection universe. It does not retroactively
change the explicitly approved 30-pair candidate universes used by the
exploratory correlation notebooks. Including the new pairs in those analyses
requires a separate methodology decision and regenerated outputs.

## Daily collection for the expanded 40-pair universe

Approved on 2026-09-20 for subsequent data collection:

- replace the hourly candle interval with daily (`1d`) candles aligned to UTC;
- retain the approved expanded universe of 40 pairs and its ranking order;
- retain the requested range from 2017-01-01 00:00:00 UTC through
  2026-09-01 23:59:59.999 UTC;
- retain the Binance Spot endpoint, quote asset, selection source, selection
  rules, listing treatment, immutable raw format, checkpoint behavior,
  provenance outputs, and validation principles from the hourly collection;
- store the daily collection separately under `data/raw/binance/spot/1d/`,
  without modifying or replacing the existing hourly artifacts;
- report missing UTC-day openings within each pair's observed span, without
  synthesizing observations before listing or across gaps;
- interpret the nominal daily candle duration as 86,400,000 milliseconds;
  preserve shorter positive-duration candles for review and reject candles
  whose close precedes the open or exceeds the nominal daily window.

This change approves the collection frequency only. It does not automatically
approve daily feature definitions, target holding windows, rebalance frequency,
or modeling and backtesting parameters. Those choices remain separate
methodological decisions.

## Exploratory hourly open-price correlation

Approved on 2026-09-05 for the exploratory notebook
`notebooks/06_binance_hourly_open_price_correlation.ipynb`:

- candidate universe: the 30 USDT-quoted pairs in the approved initial hourly
  collection;
- analysis eligibility: include only pairs whose first observed Binance hourly
  candle occurred in or before calendar year 2021 UTC;
- input field: the hourly Binance kline `open` price, quoted in USDT;
- observation period: each pair's full observed span through
  2026-09-01 23:00 UTC;
- correlation method: Pearson product-moment correlation on price levels;
- temporal alignment: exact hourly opening timestamps in UTC;
- missing-data and listing treatment: calculate every pairwise coefficient
  from timestamps observed for both assets; do not interpolate, forward-fill,
  backfill, or synthesize observations;
- supporting diagnostic: report the number of paired observations used for
  every coefficient.

Because pairwise alignment gives different comparison periods to pairs listed
at different dates, coefficients are not strictly based on a common sample.
The analysis is descriptive and exploratory. Correlation between non-stationary
price levels may reflect common trends and must not be interpreted as evidence
of causality, direct price dependence, or predictive power. Analysis of returns
would require a separate approved methodology decision.

## Exploratory hourly high-to-open return correlation

Approved on 2026-09-05 for the exploratory notebook
`notebooks/07_binance_hourly_high_open_return_correlation.ipynb`:

- candidate universe: the 30 USDT-quoted pairs in the approved initial hourly
  collection;
- analysis eligibility: include only pairs whose first observed Binance hourly
  candle occurred in or before calendar year 2021 UTC;
- return definition: `(high - open) / open` for each hourly candle, where
  `high` and `open` are the Binance kline fields quoted in USDT;
- correlation method: Pearson product-moment correlation between the defined
  hourly return series;
- temporal alignment: exact hourly opening timestamps in UTC;
- missing-data and listing treatment: calculate every pairwise coefficient
  from timestamps observed for both assets; do not interpolate, forward-fill,
  backfill, or synthesize observations;
- supporting diagnostic: report the number of paired observations used for
  every coefficient.

This return definition measures the maximum observed intrahour appreciation
relative to the candle opening price. It is not a close-to-close holding-period
return, and it does not represent a realizable return unless a trading rule and
execution assumptions are separately defined. Pearson correlation is also
sensitive to extreme observations. The analysis is descriptive and does not
establish causality or predictive power.

## Exploratory hourly price descriptive analysis

Approved on 2026-09-16 for the descriptive-analysis stage:

- universe: all 40 USDT-quoted pairs in the approved expanded hourly
  collection;
- source: each pair's immutable canonical gzip-compressed CSV;
- observation period: each pair's full observed span through
  2026-09-01 23:00 UTC;
- analyzed price fields: hourly Binance `open`, `high`, `low`, and `close`,
  quoted in USDT per unit of the base asset;
- reported statistics: observation and missing-value counts, arithmetic mean,
  median, sample standard deviation and variance (`ddof=1`), minimum, first and
  third quartiles, maximum, range, interquartile range, coefficient of
  variation, sample skewness, and Fisher excess kurtosis;
- quartile calculation: linear interpolation at 25%, 50%, and 75%;
- missing-data and listing treatment: do not interpolate, forward-fill,
  backfill, or synthesize observations, and analyze each asset only over its
  own observed span;
- visualization: one full-span hourly line chart per asset and one small-
  multiple overview, each comparing `open` and `close` prices on an individual
  USDT scale.

The statistics describe non-stationary price levels and different assets have
different listing dates and observed spans. Therefore, the results must not be
interpreted as directly comparable return or risk estimates. The charts can
support a qualitative discussion of high- and low-price periods, but a formal
classification of bull and bear regimes requires a separately approved rule.

## Exploratory hourly market-activity descriptive analysis

Approved on 2026-09-16 as an extension of the descriptive-analysis stage:

- universe and source: all 40 pairs and each immutable canonical CSV from the
  approved expanded hourly collection;
- observation period: each pair's full observed span through
  2026-09-01 23:00 UTC;
- analyzed fields: `base_asset_volume`, `quote_asset_volume`,
  `number_of_trades`, `taker_buy_base_asset_volume`, and
  `taker_buy_quote_asset_volume` from each Binance hourly kline;
- units: base-asset quantities remain in the corresponding base asset,
  quote-asset quantities remain in USDT, and `number_of_trades` remains a
  count; values with different units are not combined;
- reported statistics: observation, missing-value, and zero counts; zero
  share; total; arithmetic mean; median; sample standard deviation and
  variance (`ddof=1`); minimum; first and third quartiles; maximum; range;
  interquartile range; coefficient of variation; sample skewness; and Fisher
  excess kurtosis;
- quartile and missing-data treatment: use linear interpolation at 25%, 50%,
  and 75%, with no interpolation, forward fill, backfill, or synthesis of
  source observations;
- visualization: one three-panel hourly activity figure per asset, separating
  base-asset volume, USDT quote volume, and number of trades, plus overview
  panels for USDT quote volume and trade count.

These measures describe exchange-reported activity aggregated inside each
hourly kline. They are not transaction-level records. Totals across assets are
not combined because base-asset quantities use different units, and comparing
full-sample totals requires caution because listing dates and observed spans
differ.

## Daily price and USDT-volume descriptive analysis from 2019-H2

Approved on 2026-09-20 for the descriptive-analysis stage:

- universe and source: all 40 pairs and each immutable canonical daily CSV from
  the approved expanded daily collection;
- analysis interval: daily observations from 2019-07-01 00:00 UTC through
  2026-09-01 00:00 UTC, inclusive;
- listing treatment: each pair begins on 2019-07-01 UTC or its later first
  observed Binance daily candle;
- analyzed fields: daily Binance `open`, `high`, `low`, and `close` prices,
  quoted in USDT per unit of the base asset, plus `quote_asset_volume` expressed
  in USDT; base-asset volume and trade count are excluded;
- reporting periods: the full observed analysis span and UTC calendar
  semesters, where H1 is January through June and H2 is July through December;
- partial periods: semesters that do not cover both applicable configured
  semester boundaries are labeled `Partial`, including 2026-H2 through
  2026-09-01;
- reported statistics: observation and missing-value counts, arithmetic mean,
  median, sample standard deviation and variance (`ddof=1`), minimum, first and
  third quartiles, maximum, range, interquartile range, coefficient of
  variation, sample skewness, and Fisher excess kurtosis;
- volume-only statistics: zero count, zero share, and total USDT quote volume;
- quartiles: linear interpolation at 25%, 50%, and 75%;
- missing-data treatment: do not interpolate, forward-fill, backfill, or
  synthesize observations before listing or across missing daily openings;
- output: one five-sheet Excel workbook per trading pair, with overall and
  semester statistics, extrema, chart-support data, definitions, and native
  charts for opening/closing prices and USDT quote volume.

The results describe non-stationary price levels and exchange-reported activity
aggregated inside daily klines. They are not return, risk, or transaction-level
estimates. Cross-pair and cross-period comparisons require caution because
listing dates, observed spans, missing openings, and partial semesters differ.
