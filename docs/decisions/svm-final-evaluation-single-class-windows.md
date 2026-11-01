---
type: Methodology Decision
title: Final SVM evaluation with single-class training windows
description: Approved omission and common-date comparison policy when a final walk-forward training window cannot fit an SVC.
tags: [svm, walk-forward, eligibility, baselines, single-class]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-23T00:00:00Z" }
sources:
  - id: final-evaluation-protocol
    resource: svm-temporal-grid-search-and-final-evaluation.md
    title: Temporal SVM grid search and final evaluation
  - id: final-evaluation-config
    resource: https://github.com/marcelasilverio/tcc_crypto/blob/855e32eb9d248f1e36796bd09dd7233210d10d54/archive/pre_block_20261031/configs/binance_daily_svm_final_evaluation.json
    title: Final daily SVM execution configuration
---

# Final SVM evaluation with single-class training windows

## October 31 revision

The fixed final-test and frozen-hyperparameter execution context below is historical. The researcher explicitly confirmed that the existing single-class handling remains unchanged, including failure diagnostics, no fabricated predictions, and common-successful-date comparisons. No replacement classifier or shortened training window is authorized.

The [Daily block-window SVM experiment](daily-block-window-experiment.md) is the
current authority for these changes. The active implementation is described in
the [implementation guide](daily-code-organization.md); the record below is historical.

## Historical decision record


On 2026-10-23, the researcher explicitly requested execution of the complete
classification experiment, including implementation and execution of the
previously approved final walk-forward evaluator after the complete universe
development search. This authorizes the final stage in this execution without
changing the approved development/test boundaries, search grid or ranking.

In the same conversation, the researcher approved this handling of trailing
training windows containing only one target class:

- retain the dated observation and its class counts;
- record `single_class_training`, with no invented prediction or decision score;
- do not shorten the training window, change the selected parameters or invent
  a replacement SVC signal;
- calculate comparisons for the tuned SVC, default SVC, constant-zero dummy and
  prior dummy on the same dates where all four models produced valid outputs;
- report attempted dates, common successful dates and omitted observations
  separately from classifier metrics.

Other fitting failures must also remain auditable and must not be replaced by
fabricated predictions. Shared-date comparison excludes dates lacking a valid
output from any comparison model, while preserving their individual diagnostics.

Hyperparameters remain frozen from each asset-target-window development search.
Assets lacking an eligible pre-test search do not enter later by using test
observations for tuning. LUNAUSDT remains excluded. Portfolio construction and
financial backtesting remain outside this authorization.
