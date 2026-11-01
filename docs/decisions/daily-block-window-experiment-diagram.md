---
type: Research Context
title: Daily block-window experiment diagram
description: Visual map of the revised data preparation, per-window SVM training, validation and audit outputs.
tags: [experiment-design, diagram, svm, temporal-validation]
status: draft
authority: research-context
generated: { by: "process:codex", at: "2026-10-31T12:00:00Z" }
sources:
  - id: block-protocol
    resource: daily-block-window-experiment.md
    title: Daily block-window SVM experiment
---

# Daily block-window experiment diagram

This diagram summarizes the [October 31 methodology revision](daily-block-window-experiment.md).
It describes the active classification implementation. All dates are UTC; the study calendar is 2019-07-01 to 2026-09-01.

```mermaid
flowchart TD
    A["Collect Binance daily candles"] --> B["Preserve raw data and validate complete candles"]
    B --> C["Raw availability CSV: dates x assets; valid = 1, otherwise = 0"]
    B --> D["Per asset: first to last valid candle; fill internal gaps from last valid observation"]
    D --> E["Validate treated data and retain filling audit"]
    E --> F["Calculate features and targets: 1%, 2%, 3%"]
    F --> G["Identify available feature/target period per asset"]
    G --> H["Consecutive blocks: W = 60, 75, 90 days"]
    H --> I["In-sample: exactly W days"]
    H --> J["Out-of-sample: next W days; last block may be shorter"]
    I --> K["GridSearchCV: TimeSeriesSplit, 5 splits, expanding training, gap 0"]
    K --> L["Each internal training subset: scaling, variance filter, correlation filter, SVC"]
    L --> M["Evaluate candidates on later internal subsets"]
    M --> N["Refit selected procedure on complete in-sample"]
    N --> O["In-sample daily predictions and actual labels"]
    N --> P["Apply fitted procedure without further fitting"]
    J --> P
    P --> Q["Out-of-sample daily predictions and actual labels"]
    O --> R["Binary CSV matrices; precision and recall per window and sample role"]
    Q --> R
    L --> S["Selection audit: variances, correlations, retained/discarded features and exceptions"]
    N --> S
    Q --> T["Advance W days: previous complete validation block becomes training"]
    T --> H
    R -.-> U["End of implemented scope: classification CSVs"]
```

For W = 60, the outer blocks are:

| Fit | In-sample | Out-of-sample |
| --- | --- | --- |
| 1 | Days 1-60 | Days 61-120 |
| 2 | Days 61-120 | Days 121-180 |
| 3 | Days 121-180 | Days 181-240, or the available terminal subset |

Day numbers refer to the available modeling calendar, not a common listing
date across all assets. There are no skipped days between outer blocks.
The outer out-of-sample never enters its own block's search or preprocessing fit.

Rows are dated by their features; targets refer to the following day. Training
uses known in-sample labels; validation labels are used only for later scoring.
Internal splits use the approved TimeSeriesSplit defaults documented in the
linked decision: five expanding training subsets and validation sizes of
10, 12 or 15 days for outer windows of 60, 75 or 90 days, respectively.
Target availability must be tested at each
fit; the formula and consecutive outer blocks remain unchanged.

The existing parameter grid, winner selection and single-class handling remain
unchanged. LUNAUSDT remains excluded from modeling and included in raw quality
evidence. All tabular artifacts use CSV, grouped by execution under the
[artifact organization decision](csv-artifact-organization.md). The diagram
describes implemented behavior; historical results remain evidence of the previous protocol.
