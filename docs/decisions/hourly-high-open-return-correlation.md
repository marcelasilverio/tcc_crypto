---
type: Methodology Decision
title: Hourly high-to-open return correlation
description: Approved parameters for exploratory correlation of hourly high-to-open returns.
tags: [binance, hourly, correlation, exploratory-analysis]
status: stable
authority: approved-methodology
decision_status: approved
generated: { by: "process:okf-migration", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:marcela-prata-silverio", at: "2026-09-29T10:16:31Z" }
sources:
  - id: analysis-notebook
    resource: ../../notebooks/07_binance_hourly_high_open_return_correlation.ipynb
    title: Binance hourly high-to-open return correlation notebook
---

# Exploratory hourly high-to-open return correlation

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
