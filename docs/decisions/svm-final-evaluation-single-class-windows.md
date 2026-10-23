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
    resource: ../../configs/binance_daily_svm_final_evaluation.json
    title: Final daily SVM execution configuration
---

# Final SVM evaluation with single-class training windows

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
