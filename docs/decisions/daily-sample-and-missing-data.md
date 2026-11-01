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
    resource: https://github.com/marcelasilverio/tcc_crypto/blob/855e32eb9d248f1e36796bd09dd7233210d10d54/archive/pre_block_20261031/configs/binance_selected_usdt_daily_collection.json
    title: Binance selected USDT daily collection configuration
  - id: daily-feature-config
    resource: https://github.com/marcelasilverio/tcc_crypto/blob/855e32eb9d248f1e36796bd09dd7233210d10d54/archive/pre_block_20261031/configs/binance_daily_features.json
    title: Binance daily feature configuration
  - id: silva-methodology-reference
    resource: ../references/erci_silva_2026_methodology.md
    title: Methodological reference from Silva 2026
---

# Daily experiment period and internal-gap treatment

## October 31 revision

The revised calendar ends on 2026-09-01. Incomplete and invalid candles are treated as absent; fill only internal gaps between the first and last valid candles. Validate and treat candles before feature and target calculation, then construct windows from each asset's available modeling dataset. The raw availability CSV remains unchanged by filling. Earlier warm-up provenance below is retained.

The [Daily block-window SVM experiment](daily-block-window-experiment.md) is the
current authority for these changes. The active implementation is described in
the [implementation guide](daily-code-organization.md); the record below is historical.

## Historical decision record


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
