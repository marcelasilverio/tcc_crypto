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
    resource: ../../configs/binance_daily_features.json
    title: Binance daily feature configuration
  - id: silva-feature-reference
    resource: ../references/silva_2026_feature_code_excerpt.md
    title: Feature-engineering code excerpt from Silva 2026
---

# Daily rolling feature selection

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
