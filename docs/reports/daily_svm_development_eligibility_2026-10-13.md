---
type: Experiment Report
title: Daily SVM Development Eligibility Manifest
description: Development-only eligibility results for all 40 configured candidate symbols, targets, and training windows.
tags: [svm, asset-eligibility, development-period, generated-evidence]
status: draft
authority: generated-evidence
as_of: "2026-10-13T00:00:00Z"
generated: { by: "process:codex", at: "2026-10-13T00:00:00Z" }
sources:
  - id: eligibility-decision
    resource: ../decisions/daily-svm-asset-eligibility.md
    title: Daily SVM asset eligibility
  - id: eligibility-manifest
    resource: ../../outputs/binance_daily_svm_temporal_grid_search_v1/asset_eligibility_manifest.csv
    title: Consolidated development eligibility manifest
---

# Daily SVM Development Eligibility Manifest

## Scope

The development eligibility runner evaluated all 40 configured candidate
symbols in collection order. Each symbol was assessed independently for three
targets and three training windows, producing 360 symbol-target-window rows.
The assessment used only complete labeled rows available through the approved
development feature end of 2024-12-30.

Eligibility required at least 271 complete labeled rows and both target classes
inside every applicable inner training fold. The run did not fit SVC candidates
and did not use final-test feature rows.

## Result

- 331 of 360 symbol-target-window searches were eligible;
- 36 symbols were eligible for all nine searches;
- `TRXUSDT` was eligible for seven searches;
- `NEIROUSDT`, `LUNAUSDT`, and `ENAUSDT` were eligible for zero searches; and
- 29 symbol-target-window searches were ineligible with explicit reasons.

The non-eligible combinations were:

| Symbol | Affected combinations | Reason |
| --- | --- | --- |
| `TRXUSDT` | 3%/60 days and 4%/60 days | The last inner training fold contained one target class |
| `NEIROUSDT` | All targets and windows | 92 complete labeled rows, below 271 |
| `LUNAUSDT` | All targets and windows | Explicit economic-continuity exclusion |
| `ENAUSDT` | All targets and windows | 259 complete labeled rows, below 271 |

These results are combination-specific. In particular, the two ineligible
`TRXUSDT` searches do not remove its other seven eligible searches.

## Manifest fields

The generated manifest records symbol, target, window, status, reason, complete
row count, overall class counts, complete feature boundaries, raw observed
boundaries, observed and imputed row counts, per-fold training class counts,
and the fact that final-test eligibility has not yet been evaluated.

The final-test eligibility fields intentionally remain unavailable during this
development-only stage. They must be populated only by the later frozen-model
walk-forward implementation.
