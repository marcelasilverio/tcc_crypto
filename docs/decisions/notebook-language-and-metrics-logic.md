---
type: Methodology Decision
title: Portuguese notebooks and local metrics visualization logic
description: Researcher-approved Portuguese notebook presentation and in-cell metrics visualization, preserving strict stage clients for other notebooks.
tags: [implementation, notebooks, visualization]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-11-04T00:00:00Z" }
sources:
  - id: researcher-approval
    resource: "source-artifact:researcher-notebook-policy-2026-11-04"
    title: Researcher request for Portuguese notebooks and local metrics chart logic
  - id: existing-architecture
    resource: daily-code-organization.md
    title: Daily experiment implementation and consultation guide
---

# Portuguese notebooks and local metrics visualization logic

On November 4, 2026, the researcher explicitly changed the notebook contract:
all notebooks use Portuguese presentation, and metrics notebooks keep chart
construction directly in their cells. This supersedes the earlier Portuguese
exception limited to notebook 17 and the universal prohibition on notebook logic.

## Scope

Notebook titles, explanations, comments, docstrings and presentation labels use
Portuguese. Technical identifiers, configuration keys, saved schemas, filenames
and package APIs remain in English for consistency with source data. Repository
documentation and reusable implementation remain in English.

Metrics notebooks may filter saved tables, aggregate descriptive statistics,
use loops and conditions, and construct charts directly in cells. Common local
presentation helpers are allowed, but each chart's data selection and aggregation
must remain visible beside its explanation. Non-metrics notebooks retain the
strict package-stage-client contract, including its restrictions on processing,
charting and direct training.

Saved-result loading continues through validated package APIs. This exception
does not authorize collection, feature/target reconstruction, model fitting,
scientific parameter changes or mixing runs in a metrics report. No experiment
configuration changes are required: this is a presentation and code-location
decision, not a change to the research design.

## Implementation

[Notebook 18](../../notebooks/18_binance_daily_svm_results_visual_report.ipynb)
contains the descriptive chart logic previously located in `results.py`.
`experiment.load_report` remains responsible for validated saved-run loading.
Notebook metadata identifies metrics clients; architecture tests explicitly
register the permitted notebooks and continue enforcing the old contract on
other notebooks. Tests execute the actual metric cell with small synthetic data
to verify target/window separation and missing-score treatment.


## Portfolio metrics notebook

The approved portfolio plan adds
[Notebook 19](../../notebooks/19_binance_daily_portfolio_results_visual_report.ipynb)
to the explicit metrics-notebook list. It reads `experiment.load_portfolio_report`,
constructs three capital charts locally and summarizes saved audit evidence.
Its guards prohibit allocation, simulation and experiment execution in cells.
