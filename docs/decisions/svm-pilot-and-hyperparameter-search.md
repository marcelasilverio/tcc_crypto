---
type: Methodology Decision
title: SVM pilot and hyperparameter-search plan
description: Approved staged SVM experiment using a BTCUSDT 2019H2 default pilot before temporally valid hyperparameter search and full expansion.
tags: [svm, grid-search, pilot, in-sample, out-of-sample, temporal-validation]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-09T00:00:00Z" }
sources:
  - id: pilot-dataset-config
    resource: ../../configs/binance_daily_svm_pilot_dataset.json
    title: BTCUSDT daily SVM pilot dataset configuration
  - id: silva-methodology-reference
    resource: ../references/erci_silva_2026_methodology.md
    title: Methodological reference from Silva 2026
---

# SVM pilot and hyperparameter-search plan

The researcher recorded the following staged experiment plan from the
supervisor meeting on 2026-10-09:

1. implement the initial SVM using the estimator's documented default
   parameters;
2. validate the end-to-end algorithm with one cryptocurrency and a shorter
   time interval;
3. retain both in-sample and temporally subsequent out-of-sample results;
4. once the pilot is correct, expand to the approved asset universe and the
   full effective period beginning on 2019-07-01; and
5. perform a grid search over approved SVM hyperparameters and persist the
   output of every evaluated configuration.

The rolling training-window lengths are the same as in Silva 2026: `60`, `75`,
and `90` daily observations. Every preprocessing step, including feature
selection and scaling, must be fitted with training observations only and
applied unchanged to later observations.

The initial pilot uses `BTCUSDT` from 2019-07-01 through 2019-12-31, with June
2019 retained as feature warm-up history. The exact in-sample/out-of-sample
reporting convention, validation splitter, purge or embargo at the target
horizon, optimization metric, scaling procedure, and parameter-reuse scope
remain unresolved and require approval before model training or the definitive
experiment.

## Provisional grid-search scope

The researcher plans to consult the scikit-learn SVM documentation, propose the
grid to the supervisor, and vary approximately six hyperparameters, with three
candidate values per varying dimension where appropriate. This is a planning
bound, not an approved search space. A full Cartesian grid with six dimensions
and three values each contains up to `729` configurations before temporal
validation folds, assets, targets, and training-window lengths are included.

Candidate `SVC` parameters include `C`, `kernel`, `gamma`, `degree`, `coef0`,
`class_weight`, and `tol`, subject to estimator compatibility and supervisor
approval. A learning rate is not an `SVC` hyperparameter and must not be added
to its grid. Conditional parameters such as `degree` and `coef0` should be
evaluated only for kernels that use them.

Random shuffling and ordinary cross-validation that trains on observations
later than their validation observations are prohibited. The definitive
configuration must identify the scikit-learn version, estimator defaults,
time-aware validation procedure, candidate grid, selection metric, random
seed where applicable, and persisted per-configuration results.
