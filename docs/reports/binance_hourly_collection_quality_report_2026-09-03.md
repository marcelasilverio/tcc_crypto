# Binance Hourly Collection Quality Report

Updated: 2026-09-05

## Report scope

This report assesses the completed Binance Spot hourly kline collection for
the approved initial universe of 30 USDT-quoted trading pairs. The requested
period is from 2017-01-01 00:00:00 UTC through 2026-09-01 23:59:59.999 UTC, and
the interval is one hour.

The collection was completed in two executions:

- initial manifest:
  `data/raw/binance/spot/1h/collection_manifest_20260903T024652412977Z.xlsx`;
- recovery manifest:
  `data/raw/binance/spot/1h/collection_manifest_20260905T181544320481Z.xlsx`;
- collection identifier: `binance_selected_usdt_hourly_2017_2026-09-01`;
- initial execution timestamp: 2026-09-03 02:46:52 UTC;
- recovery execution timestamp: 2026-09-05 18:15:44 UTC;
- per-pair collection timestamps: 2026-09-03 02:46:52 through
  2026-09-05 18:20:41 UTC;
- selection source SHA-256:
  `9da47d82b1458fc32f7ab1a9ac09ecf94a5e2eabd2f653697b3718346ae30454`.

The first execution finalized 24 pairs. The recovery execution resumed the six
remaining checkpoints and finalized `SOLUSDT`, `XRPUSDT`, `SHIBUSDT`,
`DOGEUSDT`, `BNBUSDT`, and `ADAUSDT` without recollecting the other pairs.

The collection records two code revisions:

- revision `7daa5820b68f72a4ec8ff283ad28d8e0e628287c` for the first 24 pairs;
- revision `afb0c0a7954ed6832eaafb6758e20697f27c9ed5` for the six recovered pairs.

The recovery revision added targeted subset execution and retry handling for
`http.client.IncompleteRead` and remote disconnect errors. The data schema,
date range, endpoint, validation policy, and output formats remained unchanged.

The canonical source for row-level analysis is each gzip-compressed CSV. Excel
files are derived review copies. JSON sidecars provide provenance, checksums,
and validation summaries. This report independently recomputes key quality
metrics from all 30 canonical CSVs rather than relying only on the manifests.

## Executive assessment

The initial 30-pair collection is **complete and internally consistent under
the approved raw-data validation rules**.

- All 30 pairs have a canonical `.csv.gz`, a derived `.xlsx`, and a
  `.metadata.json` sidecar.
- No partial CSVs or checkpoint files remain.
- The 30 canonical CSVs contain 1,607,196 hourly observations.
- There are 1,709 missing hourly openings within pair-specific observed spans.
- Weighted in-span coverage is 99.893779%.
- There are 184 shortened candles, all preserved under the approved `REVIEW`
  policy.
- Twenty-three pairs contain both missing hours and shortened candles.
- Seven pairs have neither review condition: `FLOKIUSDT`, `BONKUSDT`,
  `PEPEUSDT`, `SUIUSDT`, `WIFUSDT`, `NEIROUSDT`, and `WLDUSDT`.
- No pair has a recomputed fatal schema, timestamp, OHLC, volume, or trade-count
  violation.
- All 60 artifact hashes, covering 30 canonical CSVs and 30 review workbooks,
  match their JSON sidecars.
- Row counts, first and last timestamps, missing hours, and shortened-candle
  counts independently recomputed from each CSV agree with the JSON metadata.
- Every pair ends at 2026-09-01 23:59:59.999 UTC, exactly matching the approved
  collection boundary.

Completion means that the raw collection stage succeeded. It does not mean
that every observation is suitable for modeling without an approved cleaning
and alignment policy.

The largest material concern remains `LUNAUSDT`. Its 457 missing hours include
a single 437-hour interruption from 2022-05-13 01:00 UTC through 2022-05-31
05:00 UTC. That gap represents 25.57% of all missing pair-hours in the complete
30-pair collection. It overlaps the documented Terra migration concern and
must not be treated as an ordinary exchange-wide interruption without a
separate continuity decision.

## Interpretation rules

The following definitions are used throughout the report:

- **Observed span**: from a pair's first returned hourly opening through its
  final opening at 2026-09-01 23:00 UTC. Time before the first returned candle
  is not counted as missing because pairs were listed at different times.
- **Expected hours**: the number of hourly grid positions in the observed span,
  inclusive of its first and last opening timestamps.
- **Coverage**: `observed rows / expected hours` for one pair. The overall
  figure is weighted by the expected hours of all 30 pairs.
- **Missing hour**: an absent UTC-hour opening strictly inside the observed
  span.
- **Gap cluster**: one or more consecutive missing hourly openings.
- **Shortened candle**: a preserved candle whose close is at or after its open
  but before the final millisecond of its nominal one-hour window.
- **Clean under current collection checks**: no missing-hour or
  shortened-candle review flag and no fatal validation failure. This does not
  mean that a pair is automatically approved for modeling.

The aggregate count of 1,608,905 expected hours is a sum of pair-hours across
different listing spans. It is not a count of unique market timestamps.

## Collection completion status

| Status | Pair count | Artifact state | Research use |
|---|---:|---|---|
| Finalized | 30 | Canonical CSV, review workbook, JSON sidecar, and verified hashes present for every pair | Eligible for cleaning and methodological review, subject to the issues in this report |
| Incomplete | 0 | No partial CSVs or checkpoints remain | Not applicable |

The completed universe contains 23 pairs whose first candle is in or before
2021 and seven pairs whose first candle is after 2021. The six recovered pairs
all belong to the first group.

## Pair diagnostics

All timestamps in the table are UTC. Coverage is calculated over each pair's
observed span, not from the common requested start date.

| Rank | Pair | First observed open | Rows | Expected hours | Missing | Coverage | Gap clusters | Longest gap | Shortened | Assessment |
|---:|---|---|---:|---:|---:|---:|---:|---|---:|---|
| 1 | BTCUSDT | 2017-08-17 04:00 | 79,140 | 79,268 | 128 | 99.838522% | 28 | 33 h, 2018-02-08 01:00 to 2018-02-09 09:00 | 14 | Long history; shared legacy gaps; includes one 1 ms candle |
| 2 | FLOKIUSDT | 2023-05-05 18:00 | 29,166 | 29,166 | 0 | 100.000000% | 0 | None | 0 | Clean under current collection checks |
| 3 | ETHUSDT | 2017-08-17 04:00 | 79,140 | 79,268 | 128 | 99.838522% | 28 | 33 h, 2018-02-08 01:00 to 2018-02-09 09:00 | 14 | Same gap pattern as BTC; includes one 1 ms candle |
| 4 | BONKUSDT | 2023-12-15 08:00 | 23,800 | 23,800 | 0 | 100.000000% | 0 | None | 0 | Clean; relatively short history |
| 5 | SOLUSDT | 2020-08-11 06:00 | 53,086 | 53,106 | 20 | 99.962339% | 10 | 4 h, 2020-12-21 14:00 to 17:00 | 5 | Recovered successfully; synchronized gaps |
| 6 | XRPUSDT | 2018-05-04 08:00 | 72,936 | 73,024 | 88 | 99.879492% | 25 | 10 h, 2018-06-26 02:00 to 11:00 | 9 | Recovered successfully; legacy shared gaps |
| 7 | SHIBUSDT | 2021-05-10 11:00 | 46,566 | 46,573 | 7 | 99.984970% | 3 | 4 h, 2021-08-13 02:00 to 05:00 | 2 | Recovered successfully; limited shared review items |
| 8 | DOGEUSDT | 2019-07-05 12:00 | 62,728 | 62,772 | 44 | 99.929905% | 18 | 8 h, 2019-08-15 02:00 to 09:00 | 8 | Recovered successfully; legacy shared gaps |
| 9 | BNBUSDT | 2017-11-06 03:00 | 77,203 | 77,325 | 122 | 99.842224% | 27 | 33 h, 2018-02-08 01:00 to 2018-02-09 09:00 | 13 | Recovered successfully; long history |
| 10 | ADAUSDT | 2018-04-17 04:00 | 73,348 | 73,436 | 88 | 99.880168% | 25 | 10 h, 2018-06-26 02:00 to 11:00 | 10 | Recovered successfully; legacy shared gaps |
| 11 | LTCUSDT | 2017-12-13 03:00 | 76,315 | 76,437 | 122 | 99.840391% | 27 | 33 h, 2018-02-08 01:00 to 2018-02-09 09:00 | 13 | Long history; shared legacy gaps |
| 12 | PEPEUSDT | 2023-05-05 18:00 | 29,166 | 29,166 | 0 | 100.000000% | 0 | None | 0 | Clean; relatively short history |
| 13 | SUIUSDT | 2023-05-03 12:00 | 29,220 | 29,220 | 0 | 100.000000% | 0 | None | 0 | Clean; relatively short history |
| 14 | LINKUSDT | 2019-01-16 10:00 | 66,794 | 66,854 | 60 | 99.910252% | 20 | 10 h, 2019-05-15 03:00 to 12:00 | 9 | Shared market-wide patterns dominate |
| 15 | AVAXUSDT | 2020-09-22 06:00 | 52,078 | 52,098 | 20 | 99.961611% | 10 | 4 h, 2020-12-21 14:00 to 17:00 | 6 | Highly complete; synchronized gaps |
| 16 | DOTUSDT | 2020-08-18 23:00 | 52,901 | 52,921 | 20 | 99.962208% | 10 | 4 h, 2020-12-21 14:00 to 17:00 | 6 | Highly complete; synchronized gaps |
| 17 | TRXUSDT | 2018-06-11 11:00 | 72,021 | 72,109 | 88 | 99.877963% | 25 | 10 h, 2018-06-26 02:00 to 11:00 | 9 | Long history; shared legacy gaps |
| 18 | WIFUSDT | 2024-03-05 14:00 | 21,850 | 21,850 | 0 | 100.000000% | 0 | None | 0 | Clean; short history |
| 19 | NEARUSDT | 2020-10-14 05:00 | 51,551 | 51,571 | 20 | 99.961219% | 10 | 4 h, 2020-12-21 14:00 to 17:00 | 6 | Highly complete; synchronized gaps |
| 20 | NEIROUSDT | 2024-09-16 10:00 | 17,174 | 17,174 | 0 | 100.000000% | 0 | None | 0 | Clean; shortest history |
| 21 | AAVEUSDT | 2020-10-15 03:00 | 51,529 | 51,549 | 20 | 99.961202% | 10 | 4 h, 2020-12-21 14:00 to 17:00 | 6 | Highly complete; synchronized gaps |
| 22 | WLDUSDT | 2023-07-24 09:00 | 27,255 | 27,255 | 0 | 100.000000% | 0 | None | 0 | Clean; relatively short history |
| 23 | XLMUSDT | 2018-05-31 09:00 | 72,287 | 72,375 | 88 | 99.878411% | 25 | 10 h, 2018-06-26 02:00 to 11:00 | 9 | Same broad gap pattern as TRX |
| 24 | ZECUSDT | 2019-03-21 04:00 | 65,270 | 65,324 | 54 | 99.917335% | 19 | 10 h, 2019-05-15 03:00 to 12:00 | 8 | Shared market-wide patterns dominate |
| 25 | FILUSDT | 2020-10-15 17:00 | 51,515 | 51,535 | 20 | 99.961191% | 10 | 4 h, 2020-12-21 14:00 to 17:00 | 6 | Highly complete; synchronized gaps |
| 26 | BCHUSDT | 2019-11-28 10:00 | 59,238 | 59,270 | 32 | 99.946010% | 15 | 5 h, 2020-02-19 12:00 to 16:00 | 8 | Shared market-wide patterns dominate |
| 27 | LUNAUSDT | 2020-08-21 10:00 | 52,405 | 52,862 | 457 | 99.135485% | 11 | 437 h, 2022-05-13 01:00 to 2022-05-31 05:00 | 7 | Material asset-specific continuity risk |
| 28 | UNIUSDT | 2020-09-17 03:00 | 52,201 | 52,221 | 20 | 99.961701% | 10 | 4 h, 2020-12-21 14:00 to 17:00 | 5 | Highly complete; synchronized gaps |
| 29 | GALAUSDT | 2021-09-13 06:00 | 43,551 | 43,554 | 3 | 99.993112% | 2 | 2 h, 2021-09-29 07:00 to 08:00 | 2 | Minor synchronized review items |
| 30 | FETUSDT | 2019-02-28 10:00 | 65,762 | 65,822 | 60 | 99.908845% | 20 | 10 h, 2019-05-15 03:00 to 12:00 | 9 | Shared market-wide patterns dominate |

### Pair-level interpretation

`BTCUSDT`, `ETHUSDT`, `BNBUSDT`, and `LTCUSDT` traverse the largest number of
early Binance interruptions. Their maximum gap is the same 33-hour interval in
February 2018. BTC and ETH have equal row, missing-hour, cluster, and shortened
counts. BNB and LTC each have 122 missing hours in 27 clusters and 13 shortened
candles. These repeated patterns are evidence against independent pair-level
illiquidity as the primary explanation for the shared gaps, although the report
does not assign an external cause without separate source confirmation.

`XRPUSDT`, `ADAUSDT`, `TRXUSDT`, and `XLMUSDT` each have 88 missing hours in 25
clusters. Their maximum 10-hour gap begins at the same timestamp. XRP, TRX, and
XLM each have nine shortened candles, while ADA has ten.

`DOGEUSDT` begins in July 2019 and has 44 missing hours in 18 clusters. Its
maximum eight-hour gap is shared with the other pairs that existed on
2019-08-15. Its diagnostics fit the broader exchange-synchronized pattern.

`LINKUSDT`, `ZECUSDT`, and `FETUSDT` form another long-history group. LINK and
FET each have 60 missing hours in 20 clusters and nine shortened candles. ZEC
begins later and ends with 54 missing hours in 19 clusters and eight shortened
candles.

`SOLUSDT`, `AVAXUSDT`, `DOTUSDT`, `NEARUSDT`, `AAVEUSDT`, `FILUSDT`, and
`UNIUSDT` each have 20 missing hours in 10 clusters. Their longest gap is the
same four-hour interval on 2020-12-21. Shortened-candle counts range from five
to six because listing times and event participation differ slightly.

`SHIBUSDT` has only seven missing hours in three clusters. Its maximum gap is
the shared four-hour interruption on 2021-08-13. `GALAUSDT` has three missing
hours in two clusters. Both pairs' shortened candles occur at broadly
synchronized timestamps.

The seven pairs with no review flags all have relatively short histories and
begin after the last broadly shared missing event in March 2023, or shortly
after it in the cases of SUI, FLOKI, and PEPE. Their perfect in-span coverage
is encouraging but is not directly comparable to older pairs that traverse
several years of early exchange history.

`LUNAUSDT` remains qualitatively different. Ten of its eleven gap clusters
match the common 2020-2023 pattern, while its 437-hour May 2022 interruption is
unique to LUNA. Excluding LUNA, the other 29 pairs contain 1,252 missing
pair-hours and have weighted coverage of 99.919539%.

## Recovery execution results

The second execution finalized all six previously incomplete pairs by resuming
their existing checkpoints.

| Rank | Pair | Final rows | Missing hours | Shortened candles | Final status |
|---:|---|---:|---:|---:|---|
| 5 | SOLUSDT | 53,086 | 20 | 5 | `COLLECTED` |
| 6 | XRPUSDT | 72,936 | 88 | 9 | `COLLECTED` |
| 7 | SHIBUSDT | 46,566 | 7 | 2 | `COLLECTED` |
| 8 | DOGEUSDT | 62,728 | 44 | 8 | `COLLECTED` |
| 9 | BNBUSDT | 77,203 | 122 | 13 | `COLLECTED` |
| 10 | ADAUSDT | 73,348 | 88 | 10 | `COLLECTED` |

The recovery manifest contains no error for these pairs. All six now have final
artifacts and checksums. Their partial CSVs and checkpoints were removed only
after finalization, as required by the collection protocol. The successful
recovery also verifies the targeted subset interface and the practical value
of page-level checkpointing.

The manifests remain execution-specific: the first records the original
30-pair attempt, including six failures, and the second records the successful
six-pair recovery. The complete status in this report is therefore reconciled
from both manifests and the physical 30-pair artifact inventory. A future
validation-only run over all configured symbols could generate one consolidated
manifest without downloading the candles again.

## Cross-pair missing-hour patterns

There are 565 unique missing timestamps across the complete collection. Of the
1,709 missing pair-hour observations, 1,124, or 65.77%, occur at timestamps
missing in at least eight pairs.

The strongest synchronized gaps are:

| Missing interval (UTC) | Duration | Pairs affected |
|---|---:|---:|
| 2018-06-26 02:00 to 11:00 | 10 h | 8 |
| 2018-07-04 01:00 to 07:00 | 7 h | 8 |
| 2018-11-14 02:00 to 08:00 | 7 h | 8 |
| 2019-03-12 02:00 to 07:00 | 6 h | 10 |
| 2019-05-15 03:00 to 12:00 | 10 h | 11 |
| 2019-08-15 02:00 to 09:00 | 8 h | 12 |
| 2020-02-19 12:00 to 16:00 | 5 h | 13 |
| 2020-06-28 02:00 to 04:00 | 3 h | 13 |
| 2020-11-30 06:00 | 1 h | 21 |
| 2020-12-21 14:00 to 17:00 | 4 h | 21 |
| 2020-12-25 02:00 | 1 h | 21 |
| 2021-02-11 04:00 | 1 h | 21 |
| 2021-03-06 02:00 | 1 h | 21 |
| 2021-04-20 02:00 to 03:00 | 2 h | 21 |
| 2021-04-25 05:00 to 07:00 | 3 h | 21 |
| 2021-08-13 02:00 to 05:00 | 4 h | 22 |
| 2021-09-29 07:00 to 08:00 | 2 h | 23 |
| 2023-03-24 13:00 | 1 h | 23 |

This synchronization, combined with similarly timed shortened candles, is
consistent with exchange-wide trading or historical-data availability events.
That statement is an inference from the collected data, not an independently
verified attribution. Pair counts vary because not every pair had been listed
at every event timestamp.

## Shortened-candle analysis

The 184 shortened candles occur at only 15 unique opening timestamps. Of those
observations, 169, or 91.85%, occur at timestamps shared by at least eight
pairs. This concentration is strong evidence that most shortened candles are
systematic timestamp events rather than independent corrupt rows.

| Candle open (UTC) | Pairs | Observed duration range | Relationship to gaps |
|---|---:|---:|---|
| 2017-09-06 16:00 | 2 | 1 ms | Immediately precedes a six-hour BTC/ETH gap |
| 2017-12-18 12:00 | 4 | 1,753,420-1,755,396 ms | Shared by BTC, ETH, BNB, and LTC |
| 2018-01-04 03:00 | 4 | 14,839-16,866 ms | Immediately precedes a one-hour gap |
| 2018-02-08 00:00 | 4 | 1,694,789-1,696,812 ms | Immediately precedes the 33-hour gap |
| 2018-07-04 00:00 | 8 | 1,345,552-1,349,106 ms | Immediately precedes a seven-hour gap |
| 2019-06-07 21:00 | 11 | 793,525-799,387 ms | Shared shortened event |
| 2020-02-19 11:00 | 13 | 2,132,287-2,138,306 ms | Immediately precedes a five-hour gap |
| 2020-03-04 09:00 | 13 | 1,306,695-1,309,902 ms | Immediately precedes a one-hour gap |
| 2020-12-21 13:00 | 21 | 2,840,522-2,845,304 ms | Immediately precedes a four-hour gap |
| 2021-02-11 03:00 | 21 | 2,453,843-2,459,258 ms | Immediately precedes a one-hour gap |
| 2021-04-25 04:00 | 21 | 57,121-62,973 ms | Immediately precedes a three-hour gap |
| 2021-08-13 01:00 | 22 | 3,599,001 ms | Immediately precedes a four-hour gap |
| 2021-12-24 04:00 | 16 | 3,592,510-3,598,666 ms | Shared event without a following broad gap in this summary |
| 2022-05-13 00:00 | 1 | 2,400,000 ms | LUNA only; immediately precedes its 437-hour gap |
| 2023-03-24 12:00 | 23 | 2,379,986-2,388,464 ms | Immediately precedes a one-hour gap |

The most extreme duration is the 1 ms candle at 2017-09-06 16:00 UTC for both
BTC and ETH. It is valid under the approved collection rule because its close
is not before its open and does not extend beyond the nominal window, but it is
not economically equivalent to a normal hourly observation. The approved rule
preserves it for review. It does not approve its use in return or indicator
calculations.

The 2021-08-13 event illustrates why duration must be interpreted precisely:
3,599,001 ms is only 999 ms shorter than a nominal hour. In contrast, the 1 ms
BTC/ETH candles contain essentially none of the intended hourly interval. A
single binary `shortened` flag therefore covers materially different degrees
of exposure.

## Independent integrity results

The following checks were recomputed from all 30 canonical CSVs rather than
accepted solely from the JSON summaries:

- exact 12-column schema equality across all files;
- row count and JSON reconciliation;
- SHA-256 for every canonical CSV and derived workbook;
- unique open timestamps;
- strictly increasing timestamps;
- UTC-hour alignment of every open timestamp;
- close timestamps at or after open and no later than the nominal hour end;
- positive OHLC values;
- OHLC envelope consistency;
- non-negative base, quote, and taker volumes;
- non-negative trade counts;
- missing-hour grids within observed spans;
- shortened-candle counts and durations;
- first observed open and last observed close reconciliation with metadata.

The recomputation found no fatal violations, schema mismatch, checksum
mismatch, or metadata mismatch in these fields. Across the 30 JSON validation
arrays there are 344 `OK` results and 46 `REVIEW` results. The 46 reviews are
exactly two per affected pair: missing hours and shortened durations for the 23
pairs that contain both conditions. There are no `FAIL` results.

The canonical CSVs occupy 76,605,317 bytes, approximately 73.06 MiB. Their
derived Excel review copies occupy 153,178,559 bytes, approximately 146.08 MiB.
The Excel layer is about 2.00 times the size of the compressed canonical layer.
This supports the current design: gzip CSV should remain the machine-readable
canonical source, while Excel should remain a human-review artifact rather
than the primary analytical input.

## Research implications

### Unequal listing histories

First observations range from 2017-08-17 for BTC and ETH to 2024-09-16 for
NEIRO. A common rectangular panel beginning in 2017 would therefore contain
large amounts of structurally unavailable pre-listing data. Treating those
periods as ordinary missing observations would be incorrect. Eligibility must
be time-aware, or the experiment must explicitly adopt a later common start
date after researcher approval.

### Missing-data treatment remains unresolved

The raw layer correctly preserves gaps. It does not decide whether a processed
modeling layer should drop affected timestamps, restrict the contemporaneous
asset set, carry values forward, interpolate, or apply another rule. Each
choice changes returns, indicators, covariance estimates, SVM samples, and
portfolio eligibility. No such choice should be implemented without explicit
methodological approval.

Synchronized gaps are especially important for portfolio alignment. Dropping a
shared timestamp may be less distortive than independently imputing many
assets, but even that is a research-design decision. Shortened candles also
require a severity-aware rule because durations range from 1 ms to almost a
full hour.

### LUNA continuity is not a generic missing-data case

LUNA's 437-hour interruption and the Terra migration warning in the approved
methodology context indicate a potential change in economic identity or market
continuity. A generic imputation rule would not resolve that question. The
researcher must decide whether to exclude LUNA, split the series into regimes,
or justify another treatment before modeling or backtesting.

### Fixed-universe selection introduces ex-post information

The 30 pairs were selected using trade activity accumulated through 2026-09-01
and current symbol status. Applying this fixed set to historical decisions
would introduce look-ahead and survivorship bias. The collection is suitable
as an initial data universe, but a final backtest must either use point-in-time
eligibility or explicitly describe itself as an ex-post fixed-universe study.

### Finalized does not mean modeling-ready

The current validations establish structural and basic market-data integrity.
They do not establish economic continuity, point-in-time eligibility, adequate
liquidity at every timestamp, treatment of zero-volume candles, outlier policy,
feature availability, or leakage-safe alignment. Those are processed-data and
experimental decisions, not raw-collection decisions.

## Recommended next actions

1. Generate a consolidated validation-only manifest for all 30 pairs so one
   execution record shows the complete final inventory without downloading the
   candles again.
2. Investigate and document LUNA economic continuity before including the pair
   in any processed dataset.
3. Obtain explicit approval for missing-hour and shortened-candle treatment in
   the processed layer. Consider distinguishing nearly full candles from
   severely truncated candles rather than treating all 184 observations as
   equivalent.
4. Define time-aware asset eligibility and the final experimental universe to
   prevent look-ahead and survivorship bias.
5. Preserve the raw artifacts unchanged. Generate any aligned, imputed,
   filtered, or transformed data under a separate processed-data path with its
   own configuration and provenance.

## Reproducibility note

This report records a point-in-time assessment of files present on 2026-09-05.
It does not modify any raw artifact. Future collection or validation runs may
produce additional timestamped manifests. Any later report should identify the
source manifests and recompute aggregate statistics rather than copying the
values above.
