---
type: Methodology Decision
title: Hourly open-price correlation
description: Approved parameters for exploratory correlation of hourly Binance opening prices.
tags: [binance, hourly, correlation, exploratory-analysis]
status: stable
authority: approved-methodology
decision_status: approved
generated: { by: "process:okf-migration", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:marcela-prata-silverio", at: "2026-09-29T10:16:31Z" }
sources:
  - id: analysis-notebook
    resource: ../../notebooks/06_binance_hourly_open_price_correlation.ipynb
    title: Binance hourly open-price correlation notebook
---

# Exploratory hourly open-price correlation

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
