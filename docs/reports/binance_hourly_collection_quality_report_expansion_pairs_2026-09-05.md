---
type: Data Quality Report
title: Binance Hourly Collection Quality Report for Expansion Pairs
description: Point-in-time quality assessment of the 10 pairs added to the hourly collection.
tags: [binance, hourly, data-quality, collection-report, universe-expansion]
status: stable
authority: generated-evidence
as_of: "2026-09-05T21:07:02Z"
generated: { by: "process:okf-migration", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:marcela-prata-silverio", at: "2026-09-29T10:16:31Z" }
sources:
  - id: expansion-manifest
    resource: ../../data/raw/binance/spot/1h/collection_manifest_20260905T210702563723Z.xlsx
    title: Expansion-pair hourly collection manifest
---

# Binance Hourly Collection Quality Report for Expansion Pairs

Created: 2026-09-05

## Report scope

This report assesses the Binance Spot hourly kline collection for the 10 pairs
added when the approved collection universe expanded from 30 to 40 pairs. The
requested period is from 2017-01-01 00:00:00 UTC through
2026-09-01 23:59:59.999 UTC, and the interval is one hour.

The report covers selection ranks 31 through 40:

`HBARUSDT`, `VETUSDT`, `ETCUSDT`, `ATOMUSDT`, `SANDUSDT`, `ENAUSDT`,
`ICPUSDT`, `CRVUSDT`, `MANAUSDT`, and `CHZUSDT`.

Collection provenance:

- manifest:
  `data/raw/binance/spot/1h/collection_manifest_20260905T210702563723Z.xlsx`;
- execution timestamp: 2026-09-05 21:07:02 UTC;
- collection identifier: `binance_selected_usdt_hourly_2017_2026-09-01`;
- code revision: `2e2f4377ac4193c57a3e6ce0a75d17175a5810ed`;
- selection source SHA-256:
  `9da47d82b1458fc32f7ab1a9ac09ecf94a5e2eabd2f653697b3718346ae30454`;
- source endpoint: `https://data-api.binance.vision/api/v3/klines`.

The canonical source for row-level analysis is each gzip-compressed CSV. Excel
files are derived review copies, and JSON sidecars provide provenance,
checksums, and validation summaries. The statistics below were independently
recomputed from the 10 canonical CSVs and reconciled with their JSON sidecars.

## Executive assessment

The collection of the 10 expansion pairs is complete, but it is not free of
missing observations.

- All 10 pairs have a canonical `.csv.gz`, a derived `.xlsx`, and a
  `.metadata.json` sidecar.
- No partial CSV or checkpoint remains for any expansion pair.
- The canonical CSVs contain 556,179 hourly observations.
- Their pair-specific observed spans contain 556,530 expected hourly openings.
- There are 351 missing hourly openings within those observed spans.
- Weighted in-span coverage is 99.936931%.
- Nine pairs contain missing hours; `ENAUSDT` is the only pair with none.
- The 351 missing pair-hours form 133 separate gap clusters.
- The longest gaps are 10 hours. They occur in `ETCUSDT`, `VETUSDT`, and
  `ATOMUSDT`, at different points in their available histories.
- There are 63 shortened candles across nine pairs. `ENAUSDT` has none.
- No fatal schema, timestamp, OHLC, volume, trade-count, or candle-window
  violation was found.
- All 20 hashes for the 10 canonical CSVs and 10 review workbooks match the
  corresponding JSON sidecars.
- Recomputed row counts, first and last timestamps, missing-hour counts, and
  shortened-candle counts agree with the metadata.
- Every pair ends at 2026-09-01 23:59:59.999 UTC, matching the approved
  collection boundary.

The direct answer is therefore: **yes, there are gaps**. They are sparse in
percentage terms, but they must be handled explicitly before constructing a
rectangular modeling panel, technical indicators, returns, covariance
matrices, or SVM samples.

## Interpretation rules

- **Observed span**: from a pair's first returned hourly opening through its
  final opening at 2026-09-01 23:00 UTC.
- **Pre-listing time**: timestamps before the first observed candle are not
  treated as missing data.
- **Expected hours**: hourly grid positions in the observed span, including
  the first and last opening timestamps.
- **Missing hour**: an absent UTC-hour opening inside the observed span.
- **Gap cluster**: one or more consecutive missing hourly openings.
- **Coverage**: observed rows divided by expected hours for the pair. The
  aggregate coverage is weighted by expected pair-hours.
- **Shortened candle**: a candle whose close is at or after its open but before
  the final millisecond of its nominal hour. It is preserved and classified as
  `REVIEW` under the approved raw-data rule.

The aggregate expected-hour count is a sum of pair-hours across different
listing spans. It is not a count of unique market timestamps.

## Completion and integrity status

| Status | Pair count | Result |
|---|---:|---|
| Finalized | 10 | Canonical CSV, review workbook, JSON sidecar, and matching hashes present |
| Incomplete | 0 | No partial CSVs or checkpoints remain |
| Fatal validation failure | 0 | No recomputed fatal integrity issue |
| Review condition | 9 | Missing hours and shortened candles are present |
| No review condition | 1 | `ENAUSDT` has complete hourly coverage within its observed span |

The collection manifest reports all 10 pairs as `COLLECTED`. Across the JSON
validation summaries there are 112 `OK` results, 18 `REVIEW` results, and no
`FAIL` result. Each of the nine affected pairs has one review for missing hours
and one for shortened candle durations.

## Pair diagnostics

All timestamps are UTC. Coverage starts at each pair's first observed candle,
not at the common requested date in 2017.

| Rank | Pair | First observed open | Rows | Expected hours | Missing | Coverage | Gap clusters | Longest gap | Shortened | Assessment |
|---:|---|---|---:|---:|---:|---:|---:|---|---:|---|
| 31 | HBARUSDT | 2019-09-29 04:00 | 60,680 | 60,716 | 36 | 99.940708% | 17 | 5 h, 2020-02-19 12:00 to 16:00 | 8 | Sparse, predominantly synchronized gaps |
| 32 | VETUSDT | 2018-07-25 04:00 | 70,990 | 71,060 | 70 | 99.901492% | 22 | 10 h, 2019-05-15 03:00 to 12:00 | 8 | Long history with legacy shared gaps |
| 33 | ETCUSDT | 2018-06-12 02:00 | 72,006 | 72,094 | 88 | 99.877937% | 25 | 10 h, 2018-06-26 02:00 to 11:00 | 10 | Highest missing count among the new pairs |
| 34 | ATOMUSDT | 2019-04-29 04:00 | 64,334 | 64,388 | 54 | 99.916133% | 19 | 10 h, 2019-05-15 03:00 to 12:00 | 9 | Legacy shared gaps dominate |
| 35 | SANDUSDT | 2020-08-14 13:00 | 53,007 | 53,027 | 20 | 99.962283% | 10 | 4 h, 2020-12-21 14:00 to 17:00 | 5 | Highly complete; synchronized gaps |
| 36 | ENAUSDT | 2024-04-02 08:00 | 21,184 | 21,184 | 0 | 100.000000% | 0 | None | 0 | No review condition; relatively short history |
| 37 | ICPUSDT | 2021-05-11 01:00 | 46,552 | 46,559 | 7 | 99.984965% | 3 | 4 h, 2021-08-13 02:00 to 05:00 | 3 | Few synchronized review items |
| 38 | CRVUSDT | 2020-08-15 04:00 | 52,992 | 53,012 | 20 | 99.962273% | 10 | 4 h, 2020-12-21 14:00 to 17:00 | 6 | Highly complete; synchronized gaps |
| 39 | MANAUSDT | 2020-08-06 10:00 | 53,202 | 53,222 | 20 | 99.962422% | 10 | 4 h, 2020-12-21 14:00 to 17:00 | 6 | Highly complete; synchronized gaps |
| 40 | CHZUSDT | 2019-09-06 04:00 | 61,232 | 61,268 | 36 | 99.941242% | 17 | 5 h, 2020-02-19 12:00 to 16:00 | 8 | Sparse, predominantly synchronized gaps |

`ETCUSDT` has the largest absolute gap count, with 88 missing hours in 25
clusters. Its coverage remains 99.877937% because the series spans more than
eight years. `ICPUSDT` has only seven missing hours, while `ENAUSDT` has none.

The three 10-hour maximum gaps are not all the same event:

- `ETCUSDT`: 2018-06-26 02:00 through 11:00 UTC;
- `VETUSDT` and `ATOMUSDT`: 2019-05-15 03:00 through 12:00 UTC.

## Cross-pair missing-hour patterns

The 351 missing pair-hours occur at 88 distinct UTC timestamps. Of the 351
pair-hours, 333, or 94.87%, occur at timestamps missing from at least two of
the expansion pairs. Only 18 missing pair-hours occur at timestamps unique to
one pair in this 10-pair subset.

The strongest synchronized gaps are:

| Missing interval (UTC) | Duration | Expansion pairs affected |
|---|---:|---:|
| 2019-05-15 03:00 to 12:00 | 10 h | 3 |
| 2020-02-19 12:00 to 16:00 | 5 h | 5 |
| 2020-12-21 14:00 to 17:00 | 4 h | 8 |
| 2021-04-20 02:00 to 03:00 | 2 h | 8 |
| 2021-04-25 05:00 to 07:00 | 3 h | 8 |
| 2021-08-13 02:00 to 05:00 | 4 h | 9 |
| 2021-09-29 07:00 to 08:00 | 2 h | 9 |
| 2023-03-24 13:00 | 1 h | 9 |

The repeated timestamps match the broad synchronized patterns already found
in the initial 30-pair quality report. This is evidence that most gaps are not
isolated to a single expansion asset. Describing them as exchange-wide events
would still require an external source; synchronization alone does not prove
the cause.

## Shortened-candle analysis

Nine pairs contain 63 preserved shortened candles. They occur at 10 distinct
opening timestamps. Sixty-two of the 63 observations, or 98.41%, occur at
timestamps shared by at least two expansion pairs.

The strongest shared shortened-candle timestamps are:

| Candle open (UTC) | Expansion pairs affected | Relationship to missing hours |
|---|---:|---|
| 2020-02-19 11:00 | 5 | Immediately precedes a shared five-hour gap |
| 2020-12-21 13:00 | 8 | Immediately precedes a shared four-hour gap |
| 2021-02-11 03:00 | 8 | Immediately precedes a shared one-hour gap |
| 2021-04-25 04:00 | 8 | Immediately precedes a shared three-hour gap |
| 2021-08-13 01:00 | 9 | Immediately precedes a shared four-hour gap |
| 2021-12-24 04:00 | 7 | Shared shortened event |
| 2023-03-24 12:00 | 9 | Immediately precedes a shared one-hour gap |

The shortest preserved duration among the expansion pairs is 57,488 ms in
`ATOMUSDT`, substantially shorter than the nominal 3,600,000 ms hour. The
approved collection rule correctly preserves this raw observation for review,
but it does not establish that the candle is economically comparable to a full
hour for feature or return calculations.

## Independent integrity results

The following checks were recomputed from the canonical CSVs:

- exact 12-column schema;
- canonical CSV and review workbook SHA-256 hashes;
- row counts and metadata reconciliation;
- unique, strictly increasing open timestamps;
- UTC-hour alignment of every open timestamp;
- close timestamps at or after the open and no later than the nominal hour;
- positive OHLC values and OHLC envelope consistency;
- non-negative base, quote, taker, and trade-count fields;
- missing-hour grids within pair-specific observed spans;
- shortened-candle counts;
- first observed open and last observed close reconciliation.

No fatal violation, checksum mismatch, or metadata mismatch was found. The 10
canonical CSVs occupy 24,825,227 bytes, approximately 23.68 MiB. The 10 review
workbooks occupy 50,943,478 bytes, approximately 48.58 MiB. The canonical CSV
should remain the machine-readable source; the Excel files are review copies.

## Research implications

### Missing-data treatment is still unresolved

The collection correctly preserves the gaps and does not fill them. Before
modeling, the researcher must approve whether affected timestamps will be
dropped, assets will become temporarily ineligible, values will be imputed, or
another rule will apply. Each choice affects returns, technical indicators,
target construction, covariance estimates, SVM samples, and portfolio weights.

### Synchronization matters for panel construction

Because 94.87% of the missing pair-hours occur at shared timestamps, the gaps
are likely to remove multiple assets from the same cross-section. A cleaning
rule must therefore be evaluated at the panel level, not pair by pair. Filling
each series independently could create artificial contemporaneous prices at
times when several source candles are absent.

### Listing histories remain unequal

The expansion pairs begin between 2018-06-12 and 2024-04-02. Pre-listing time
must not be confused with a data-quality gap. `ENAUSDT` has perfect in-span
coverage, but its history is much shorter than the histories of `ETCUSDT` or
`VETUSDT`, so coverage percentages alone do not establish equal experimental
eligibility.

### Collection success is not modeling readiness

The absence of fatal raw-data errors establishes structural integrity, not a
complete modeling policy. The missing and shortened observations still need an
approved processed-data treatment. The expanded universe also remains an
ex-post selection based on information accumulated through 2026-09-01.

## Recommended next actions

1. Approve a panel-level rule for missing hourly openings before creating
   features, returns, targets, or covariance matrices.
2. Approve a severity-aware rule for shortened candles; the observed durations
   are not economically equivalent.
3. Preserve all raw artifacts unchanged and create cleaned or aligned data only
   under a separate processed-data path with its own provenance.
4. Regenerate any exploratory analysis only after explicitly deciding whether
   its candidate universe should remain at 30 pairs or expand to 40.

## Reproducibility note

This report is a point-in-time assessment of the 10 expansion-pair artifacts
present on 2026-09-05. It does not modify raw data. The aggregate and pair-level
statistics were recomputed from the canonical CSVs and reconciled with the
manifest and JSON sidecars rather than copied from the Excel review sheets.
