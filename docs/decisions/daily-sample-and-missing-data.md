---
type: Methodology Decision
title: Daily experiment period and internal-gap treatment
description: Approved experiment start, feature warm-up period, and forward-fill rule for internal daily gaps.
tags: [daily, sample-period, warm-up, missing-data, temporal-validation]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-09T00:00:00Z" }
sources:
  - id: daily-collection-config
    resource: ../../configs/binance_selected_usdt_daily_collection.json
    title: Binance selected USDT daily collection configuration
  - id: daily-feature-config
    resource: ../../configs/binance_daily_features.json
    title: Binance daily feature configuration
  - id: silva-methodology-reference
    resource: ../references/erci_silva_2026_methodology.md
    title: Methodological reference from Silva 2026
---

# Daily experiment period and internal-gap treatment

The researcher recorded the following decisions from the supervisor meeting on
2026-10-09:

- the effective feature, simulation, and evaluation period starts on
  `2019-07-01T00:00:00Z`, the first day of the second half of 2019;
- daily observations from June 2019 must be loaded as feature warm-up history
  so that lagged formulas and technical indicators can produce values at the
  start of the effective period;
- June 2019 warm-up observations are inputs to feature construction only and
  must not be reported as simulation or evaluation observations; and
- a missing UTC day strictly inside an asset's observed span must be filled in
  the derived aligned data by carrying forward the complete preceding daily
  observation to every missing day until the next observed candle.

The forward-fill rule is a preprocessing decision. Files under `data/raw/`
remain immutable and must not be overwritten. Derived data and experiment
metadata must distinguish observed candles from carried-forward observations
so that the treatment remains auditable.

The `LUNAUSDT` daily series provides the currently identified case. It has an
internal 17-day gap from 2022-05-14 through 2022-05-30. The last observed daily
candle before the gap is 2022-05-13, and observations resume on 2022-05-31.
The approved rule therefore carries the 2022-05-13 values through all 17
missing dates in the derived data.

This decision applies only to gaps bounded by observed candles on both sides.
It does not approve backward filling before an asset's first observation,
synthetic pre-listing history, or a rule for missing observations after an
asset's final observed candle. Asset eligibility and terminal-gap behavior
remain separate methodology decisions.
