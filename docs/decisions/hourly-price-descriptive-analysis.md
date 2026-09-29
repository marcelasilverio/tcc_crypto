---
type: Methodology Decision
title: Hourly price descriptive analysis
description: Approved parameters for descriptive analysis of hourly Binance price fields.
tags: [binance, hourly, descriptive-analysis, prices]
status: stable
authority: approved-methodology
decision_status: approved
generated: { by: "process:okf-migration", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:marcela-prata-silverio", at: "2026-09-29T10:16:31Z" }
sources:
  - id: analysis-config
    resource: ../../configs/binance_hourly_price_descriptive_analysis.json
    title: Binance hourly price descriptive-analysis configuration
  - id: analysis-notebook
    resource: ../../notebooks/08_binance_hourly_price_descriptive_analysis.ipynb
    title: Binance hourly price descriptive-analysis notebook
---

# Exploratory hourly price descriptive analysis

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
