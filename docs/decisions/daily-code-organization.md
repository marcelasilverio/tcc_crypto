---
type: Methodology Decision
title: Daily experiment implementation and consultation guide
description: Approved eight-module implementation, two configurations, stage commands, CSV dictionary with the `__NULL__` missing-value marker and Git-based historical retention.
tags: [implementation, daily, csv, reproducibility]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-31T20:00:00Z" }
sources:
  - id: implementation-approval
    resource: "source-artifact:researcher-implementation-plan-2026-10-31"
    title: Researcher-approved simplification and implementation plan
  - id: protocol
    resource: daily-block-window-experiment.md
    title: Daily block-window SVM experiment
---

# Daily experiment implementation and consultation guide

The researcher authorized the eight-module architecture and historical migration
on October 31. The active implementation stops at classification. Automated tests
use small synthetic observations and a reduced test grid; they are not scientific
results. No complete collection or production experiment is triggered by this change.

## Where each step lives

| Module in src/tcc_crypto | Public responsibility |
| --- | --- |
| collection.py | collect_symbol: Binance requests, retries, pagination, resume, raw CSV |
| preparation.py | prepare_symbol: validate complete candles, availability, bounded filling |
| dataset.py | calculate_features and build_dataset: formulas, next-day labels and alignment |
| training.py | FeatureSelector, outer_blocks, fit_search, train_symbol: calculation only |
| results.py | write_table, read_table, binary_matrix: CSV schemas, provenance and consultation |
| experiment.py | collect, prepare, build_datasets, train, consolidate, run: explicit coordination |
| config.py | load_config and select_symbols: effective parameters and explicit asset choice |
| paths.py | Paths and raw_paths: standard directories and filenames |

Functions in preparation, dataset and training perform calculations without writing
files. The orchestrator writes their results. Export reads saved evidence without
recalculating features, selection, scaling or models.

## Configuration and execution

Install the project with `python -m pip install -e '.[dev]'`. The only active
configuration files are [experiment.json](../../configs/experiment.json) and
[svm_grid.json](../../configs/svm_grid.json). The first holds data, indicators,
targets, windows, pipeline order, selection, scaling, temporal splits and operational settings.
It references the second, which holds the unchanged 186 conditional candidates,
F1 tolerance and deterministic tie-break order. Production indicator periods and
USDT quote-volume convention remain unchanged. The zero-parameter Parabolic SAR
still requires the previously documented scientific review before final results.

Run a single asset explicitly, using existing saved inputs:

```sh
python -m tcc_crypto.experiment collect --symbols BTCUSDT
python -m tcc_crypto.experiment prepare --symbols BTCUSDT --run-id review_01
python -m tcc_crypto.experiment dataset --symbols BTCUSDT --run-id review_01
python -m tcc_crypto.experiment train --symbols BTCUSDT --run-id review_01
python -m tcc_crypto.experiment results --symbols BTCUSDT --run-id review_01 --overwrite
```

Preparation and training already consolidate their main tables. The final command
demonstrates rebuilding those tables from saved evidence; hence `--overwrite`.
Use `--symbols BTCUSDT ADAUSDT` for a subset or `--all-symbols` for the configured
universe. `run` explicitly chains collection, preparation, dataset and training.
Do not run it merely to inspect existing outputs. Every derived command requires
`--run-id`; every command requires an explicit asset choice. Missing inputs name
their prerequisite stage rather than running it silently.

Use a new run ID for a changed scientific configuration. `--overwrite` permits
replacing derived outputs within the same configuration. Upstream checksums are
validated recursively, so changing an earlier input makes downstream results stale.
Rebuild affected downstream stages explicitly. To add assets to a partial run,
use `--overwrite` because the shared consultation CSVs are regenerated; existing
per-asset evidence is retained and included. Unknown or repeated symbols fail.

## CSV dictionary and folders

Intermediate files live directly in `data/processed/daily_<run_id>/`:
`<SYMBOL>_treated.csv`, `_features.csv`, `_targets.csv`, `_dataset.csv`.
The dataset retains warm-up limitations, missing final labels, imputation flags,
feature and target timestamps, availability timestamps and `is_usable`.
Training reads only the configured feature list and complete consecutive rows.

Main files live directly in `outputs/experiments/daily_<run_id>/`:

| CSV | Row identity and contents |
| --- | --- |
| availability.csv | date_utc, then configured symbols; raw valid candle = 1, invalid or absent = 0 |
| treatment.csv | symbol/date, observed or filled status, reason and source_date_utc |
| metrics.csv | symbol/target/window_size/block_id/role/model; metrics, sample counts, confusion counts and status |
| feature_selection.csv | symbol/target/window_size/block_id/feature; full-fit standardized variance, retained/discarded reason and correlation |
| predictions_in_sample.csv | feature_time_utc/target/window_size, then symbols; fitted SVM training predictions |
| actuals_in_sample.csv | same coordinates; actual next-day binary targets |
| predictions_out_of_sample.csv | same coordinates; SVM validation predictions |
| actuals_out_of_sample.csv | same coordinates; actual validation outcomes, used only for scoring |

Partial executions leave unprocessed symbol cells missing, not zero. Once all
assets are prepared, availability is binary for the complete study calendar.
LUNAUSDT remains in availability but has no model signals. A failed model produces
missing predictions, not invented negatives. Actual labels can remain present.
Precision and recall summarize each block and role, using common successful dates
across the four approved comparison models; attempted, evaluated and omitted
counts explain exclusions. Winner parameters apply only to tuned SVM rows.

`audit/<SYMBOL>_predictions.csv` maps every prediction and actual to its own
asset/block/target/window/role/model/status. A block number is local to its asset.
Other per-symbol audit tables hold blocks, inner folds, candidates, fold scores,
winners, selection, full correlation pairs, scaler parameters, failures and
preparation quality. Inner selection is audited once per division, independently
of the candidate grid. Variance and correlations describe these filters; they
are not SVM coefficient importance. Fallback records the original exception.

Each table uses UTF-8, commas and decimal points, with `__NULL__` for missing
values. Its `.metadata.json` records ordered columns, restored nullable types,
UTC timestamps, row count, SHA-256, sources and configuration identity. Use
`results.read_table` to restore types and verify provenance. Atomic temporary-file
replacement is used for writes. `configuration.json` preserves both effective
JSONs; `execution.json` records environment versions, UTC time and Git state.
No figure folder is created unless figures actually exist. New Excel export is
not supported.

## Timing and verification

The November 1 correction makes StandardScaler the first window operation,
followed by variance filtering, correlation filtering and SVC. Scaling audit
covers all input features; selection variances refer to standardized values.

Every complete in-sample is followed immediately by its out-of-sample. Each search
fits preprocessing only on the current inner training subset. Its callable refit
uses all approved tie-breaks and then fits the winner on the complete in-sample.
At both inner and outer boundaries, fit time is after the first validation
feature candle closes; the last training next-day label is then observable.
Predictions concern the following day. Validation outcomes never enter that fit.
Training predictions are retrospective fitted values and are labeled separately.

The [experiment diagram](daily-block-window-experiment-diagram.md) shows the flow.
The presentation client is
[notebook 17](../../notebooks/17_binance_daily_svm_experiment_walkthrough.ipynb).
The [November 4 notebook policy](notebook-language-and-metrics-logic.md) now
requires Portuguese presentation in all notebooks. Non-metrics notebooks remain
strict stage clients. Metrics notebook 18 keeps descriptive analysis and chart
construction in its own cells, while saved-result loading remains validated by
the package.

## Historical evidence

Superseded sources, configurations, notebooks, tests, outputs and reports are
available in the [pre-cleanup commit](https://github.com/marcelasilverio/tcc_crypto/tree/855e32eb9d248f1e36796bd09dd7233210d10d54). Historical artifacts have been
removed from the working tree under the
[history retention decision](git-only-history-retention.md). Raw files remain
at their original paths. The current experiment does not depend on the former
migration script or its manifest. Previous results describe their original
protocol and are not results of the revised experiment.
