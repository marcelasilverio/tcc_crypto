---
type: Methodology Decision
title: Daily price and volume descriptive analysis
description: Approved parameters for descriptive analysis of daily Binance prices and USDT volume.
tags: [binance, daily, descriptive-analysis, prices, volume]
status: stable
authority: approved-methodology
decision_status: approved
generated: { by: "process:okf-migration", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:marcela-prata-silverio", at: "2026-09-29T10:16:31Z" }
sources:
  - id: analysis-config
    resource: ../../configs/binance_daily_price_volume_descriptive_analysis.json
    title: Binance daily price and volume descriptive-analysis configuration
  - id: analysis-notebook
    resource: ../../notebooks/11_binance_daily_price_volume_descriptive_analysis.ipynb
    title: Binance daily price and volume descriptive-analysis notebook
---

# Daily price and USDT-volume descriptive analysis from 2019-H2

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
- cross-pair figures: two 8-by-5 small-multiple PNG figures in approved-symbol
  order, one applying the natural logarithm pointwise to positive daily opening
  and closing prices and one retaining daily USDT quote volume on a linear
  scale, displayed in billions of USDT for readability;
- figure comparability: all panels use the configured UTC analysis interval on
  the horizontal axis, each pair retains an independent vertical scale, and
  missing daily openings break the plotted line rather than being connected,
  interpolated, or filled.

The results describe non-stationary price levels and exchange-reported activity
aggregated inside daily klines. They are not return, risk, or transaction-level
estimates. Cross-pair and cross-period comparisons require caution because
listing dates, observed spans, missing openings, and partial semesters differ.
