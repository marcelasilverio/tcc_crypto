---
type: Experiment Report
title: BTCUSDT Development Grid-Search Validation
description: Operational validation of the approved development-only temporal SVC search without access to final-test feature rows.
tags: [btc, svm, grid-search, temporal-validation, generated-evidence]
status: draft
authority: generated-evidence
as_of: "2026-10-13T00:00:00Z"
generated: { by: "process:codex", at: "2026-10-13T00:00:00Z" }
sources:
  - id: grid-search-config
    resource: ../../configs/binance_daily_svm_grid_search.json
    title: Daily SVM temporal grid-search configuration
  - id: grid-search-implementation
    resource: ../../src/tcc_crypto/daily_svm_grid_search.py
    title: Daily temporal SVC grid-search implementation
  - id: run-metadata
    resource: ../../outputs/binance_daily_svm_temporal_grid_search_v1/BTCUSDT/run_metadata.json
    title: BTCUSDT development grid-search run metadata
---

# BTCUSDT Development Grid-Search Validation

## Scope

This report records an operational validation of the approved temporal SVC
grid-search implementation using `BTCUSDT`. It is implementation evidence, not
the definitive classifier evaluation and not a financial-performance result.

The run used feature dates from 2019-07-01 through 2024-12-30. The 2024-12-31
candle was used only to construct the next-day target attached to the final
development feature row. No final-test feature observation from 2025-01-01
onward was retained, calculated, or used by the development-dataset builder.

The run was made from Git revision
`161dca0a36efc99632e4710dc83de131271b559d` with an intentionally dirty working
tree containing the new implementation and tests. Generated artifacts remain
outside Git under
`outputs/binance_daily_svm_temporal_grid_search_v1/BTCUSDT/`.

## Eligibility result

All nine configured BTCUSDT searches were eligible:

| Target | Complete labeled rows | Negative | Positive | Windows |
| --- | ---: | ---: | ---: | --- |
| 2% | 2,010 | 1,179 | 831 | 60, 75, 90 |
| 3% | 2,010 | 1,474 | 536 | 60, 75, 90 |
| 4% | 2,010 | 1,663 | 347 | 60, 75, 90 |

Every applicable inner training fold contained both target classes. The
eligibility threshold was 271 complete labeled rows.

## Execution result

The implementation produced:

- 9 eligible symbol-target-window searches;
- 186 compatible candidates per search;
- 3 temporal folds per candidate;
- 5,022 candidate-fold fits;
- 1,674 aggregate candidate results;
- 9 deterministically selected configurations; and
- zero estimator fit errors.

The latest recorded training observation was 2024-10-30. The corresponding
one-observation gap was 2024-10-31, and the final validation block ran from
2024-11-01 through 2024-12-30. This confirms the intended chronological order
and separation at the last inner boundary.

## Selected development configurations

The run selected the following configurations using mean inner-validation F1
and the approved tie-breaking rule:

| Target | Window | Kernel | C | Gamma | Degree | Coef0 | Class weight | Mean F1 |
| --- | ---: | --- | ---: | --- | ---: | ---: | --- | ---: |
| 2% | 60 | poly | 1.0 | scale | 3 | 0.0 | balanced | 0.483127 |
| 2% | 75 | poly | 0.1 | 0.1 | 2 | 0.0 | balanced | 0.560044 |
| 2% | 90 | poly | 10.0 | 0.1 | 2 | 0.0 | balanced | 0.416659 |
| 3% | 60 | poly | 0.1 | scale | 2 | 0.5 | balanced | 0.388654 |
| 3% | 75 | poly | 0.1 | 0.01 | 2 | 0.0 | balanced | 0.390992 |
| 3% | 90 | poly | 10.0 | 0.01 | 2 | 1.0 | balanced | 0.398589 |
| 4% | 60 | poly | 1.0 | scale | 3 | 0.5 | balanced | 0.282065 |
| 4% | 75 | poly | 10.0 | 0.1 | 4 | 0.5 | balanced | 0.267977 |
| 4% | 90 | poly | 1.0 | 0.1 | 3 | 1.0 | balanced | 0.360234 |

These selections validate the mechanics and persistence of the grid search.
They must not be interpreted as final out-of-sample performance. The reserved
final period remains untouched by model selection.

## Generated artifacts

The run generated:

- `asset_eligibility.csv`;
- `fold_results.csv.gz`;
- `candidate_results.csv.gz`;
- `selected_configurations.csv`; and
- `configuration_snapshot.json`; and
- `run_metadata.json`.

The metadata records the configuration snapshot and checksum, raw-data
checksum, Git state, package versions, artifact checksums, development
boundaries, and the explicit fact that final-test feature rows were not used.

## Remaining boundary

This validation does not implement or authorize the final walk-forward test.
The next implementation stage is the frozen-parameter final evaluator and its
required baseline comparisons. It must not be executed until the development
implementation and selected configurations are reviewed.
