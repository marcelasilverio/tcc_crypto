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

The pilot uses scikit-learn `StandardScaler` after feature selection. For every
one-step prediction, a new scaler is fitted on the selected training-window
features only and then applied unchanged to the immediately following feature
row. The prediction row never contributes to the fitted mean or standard
deviation.

The initial pilot uses `BTCUSDT` from 2019-07-01 through 2019-12-31, with June
2019 retained as feature warm-up history. It records accuracy, precision,
recall, and F1 as pilot diagnostics. In-sample metrics describe each fitted
rolling training window, while out-of-sample metrics aggregate the one-step
predictions for each target and window size. These diagnostics are pilot
evidence and are not the definitive performance estimate.

## Definitive grid-search decision

The provisional scope in the original meeting note was superseded on
2026-10-13 by the approved [Temporal SVM grid search and final evaluation](svm-temporal-grid-search-and-final-evaluation.md)
decision. That decision defines the conditional 186-candidate SVC grid, three
inner temporal splits, F1 model selection, frozen-parameter final walk-forward
evaluation, required classifier metrics, exact temporal boundaries, a one-day
gap, deterministic tie breaking, and exact baselines. Symbol eligibility and
the LUNAUSDT exclusion are recorded in the related
[Daily SVM asset eligibility](daily-svm-asset-eligibility.md) decision.
