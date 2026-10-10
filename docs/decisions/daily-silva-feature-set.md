---
type: Methodology Decision
title: Daily Silva-derived feature set
description: Approved initial daily feature construction adapted from Silva 2026, with Parabolic SAR parameter verification pending.
tags: [features, daily, technical-indicators, volume]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-06T00:00:00Z" }
sources:
  - id: feature-config
    resource: ../../configs/binance_daily_features.json
    title: Binance daily feature configuration
  - id: silva-feature-reference
    resource: ../references/silva_2026_feature_code_excerpt.md
    title: Feature-engineering code excerpt from Silva 2026
---

# Daily Silva-derived feature set

Approved on 2026-10-06 as the first algorithm-development increment:

- use Binance daily (`1d`) spot candles aligned to UTC;
- adapt the 22-feature set documented in the Silva 2026 reference;
- use `quote_asset_volume`, denominated in USDT, as the volume input for the
  Chaikin Accumulation/Distribution Line and On-Balance Volume;
- activate `r1` through `r15`, 10-observation momentum, 14-observation RSI,
  Parabolic SAR, 14-observation ATR, True Range, Chaikin AD, and OBV;
- calculate Parabolic SAR provisionally with both `acceleration` and `maximum`
  equal to zero, reproducing the values in the Silva 2026 reference;
- keep the zero-valued Parabolic SAR parameters explicitly marked for later
  verification before the final experiment because they can leave the SAR
  unchanged for long intervals and may not represent the intended settings;
- preserve indicator warm-up values as missing rather than removing a fixed
  number of rows; and
- forward-fill missing UTC days strictly inside an asset's observed span in a
  derived dataset, retain an `is_imputed` audit marker, and never modify raw
  files or fill leading or trailing history.

The unusual Silva definitions of `r6` through `r8`, which divide the current
high by lagged opening prices, are preserved. Feature construction may use only
the current and earlier observations at each timestamp.

The missing-data rule was approved separately on 2026-10-09 and supersedes the
earlier temporary rejection of cross-gap feature construction. This decision
does not approve feature-selection thresholds or refresh frequency,
normalization, temporal window sizes, SVM hyperparameters, target holding
windows, or portfolio rules.
