---
type: Methodology Decision
title: Daily rolling feature selection
description: Approved variance and correlation filters refitted within every daily rolling training window.
tags: [features, feature-selection, temporal-validation, daily]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-08T00:00:00Z" }
sources:
  - id: feature-config
    resource: ../../archive/pre_block_20261031/configs/binance_daily_features.json
    title: Binance daily feature configuration
  - id: silva-feature-reference
    resource: ../references/silva_2026_feature_code_excerpt.md
    title: Feature-engineering code excerpt from Silva 2026
---

# Daily rolling feature selection

## October 31 revision

The per-day refitting schedule below is historical. The current protocol fits selection within each internal training fold and on the complete outer in-sample, then applies it unchanged to the corresponding out-of-sample block. The researcher explicitly adopted the supplied recorte selection procedure. Its VarianceThreshold retains variance strictly greater than 0.01; audit values are variance and correlation diagnostics, not predictive importances.

The [Daily block-window SVM experiment](daily-block-window-experiment.md) is the
current authority for these changes. The active implementation is described in
the [implementation guide](daily-code-organization.md); the record below is historical.

## Historical decision record


Approved on 2026-10-08 for the daily feature pipeline:

- remove features whose training-window variance is below `0.01` using
  scikit-learn `VarianceThreshold`;
- after the variance filter, remove features whose absolute Pearson
  correlation exceeds `0.8` using Feature-engine `DropCorrelatedFeatures`;
- evaluate separate fixed-length rolling training windows of 60, 75, and 90
  daily observations;
- refit both selectors independently for every next-day prediction;
- fit selectors using the training window only; and
- apply the fitted selectors unchanged to the immediately following daily
  observation.

If no feature meets the variance threshold, retain the feature with the
highest sample variance in that training window, matching the fallback intent
of the Silva 2026 code excerpt. Indicator warm-up rows may be removed only from
the leading edge of a feature table. Missing values after the first complete
row remain an error and must not be silently discarded.

This decision does not approve feature scaling, target construction, SVM
hyperparameters, cross-validation boundaries, or the final train, validation,
and test period design.
