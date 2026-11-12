---
type: Methodology Decision
title: Daily experiment implementation and consultation guide
description: Approved classification and independent portfolio implementation, configuration contracts, stage commands, CSV schemas and Git-based historical retention.
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
on October 31 and the separate portfolio and backtesting modules in the approved
portfolio implementation plan. Automated tests
use small synthetic observations and a reduced test grid; they are not scientific
results. No complete collection or production experiment is triggered by this change.

## Where each step lives

| Module in src/tcc_crypto | Public responsibility |
| --- | --- |
| collection.py | collect_symbol: Binance requests, retries, pagination, resume, raw CSV |
| preparation.py | prepare_symbol: validate complete candles, availability, bounded filling |
| dataset.py | calculate_features and build_dataset: formulas, next-day labels and alignment |
| training.py | FeatureSelector, outer_blocks, fit_search, train_symbol: calculation only |
| portfolio.py | effective_signals, allocate_portfolios: historical eligibility and weights |
| backtesting.py | realized_trade, simulate_capital: execution and capital compounding |
| results.py | write_table, read_table, binary_matrix, portfolio publication: schemas and provenance |
| experiment.py | classification stages, execute_portfolio and load_portfolio_report: explicit coordination |
| config.py | load_config, load_portfolio_config and select_symbols: validated parameters |
| paths.py | Paths, PortfolioPaths and raw_paths: standard artifact locations |

Functions in preparation, dataset, training, portfolio and backtesting calculate without writing
files. The orchestrator writes their results. Export reads saved evidence without
recalculating features, selection, scaling or models.

## Configuration and execution

Install the project with `python -m pip install -e '.[dev]'`. The classification
configuration files are [experiment.json](../../configs/experiment.json) and
[svm_grid.json](../../configs/svm_grid.json). The first holds data, indicators,
targets, windows, pipeline order, selection, scaling, temporal splits and operational settings.
It references the second, which holds the unchanged 186 conditional candidates,
F1 tolerance and deterministic tie-break order. Production indicator periods and
USDT quote-volume convention remain unchanged. The zero-parameter Parabolic SAR
still requires the previously documented scientific review before final results.

The [portfolio allocation decision](daily-portfolio-allocation.md) adds
[portfolio.json](../../configs/portfolio.json) for the independent downstream
stage. Keeping this configuration separate preserves saved classification
identities. The architecture inventory includes all three JSONs.

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


## Independent portfolio execution

Install the declared PyPortfolioOpt dependency and its CVXPY/CLARABEL backend
through the project dependency command above. Invoke the portfolio explicitly:

```sh
python -m tcc_crypto.experiment portfolio --run-id portfolio_01
```

`--portfolio-config` optionally selects another configuration file. The output
ID identifies the portfolio execution. By default, the newest classification execution is
resolved from its saved UTC execution timestamp, and its source ID and hashes
are recorded separately. The source must provide tuned_svc out-of-sample
predictions with window_size 60 and the required historical inputs. The command
uses the saved universe, including exclusions; symbol subset flags are rejected.
The existing classification commands have no portfolio execution path.

Outputs are grouped in `outputs/portfolios/<run_id>/`. The three CSV tables are
`capital.csv`, `signals.csv` and `operations.csv`, each with schema metadata.
Capital records opening/closing balance, simple daily return and cash reason.
Absent portfolio predictions have effective value zero under the November 10
revision, with the original absence preserved and no previous signal reused.
Signals record original and effective predictions, signal source dates/blocks,
random draws, eligible history counts and exclusions. Operations record fixed
weights, optimizer diagnostics, allocated amounts, fractional units, execution
prices, realized outcomes and imputation provenance. Cash portfolios retain
an operation diagnostic row with zero weight and nullable execution fields.

Configuration, source provenance and execution JSONs accompany a completion
manifest. A directory lock protects calculations and publication. Interrupted
staging is never a readable result. `--overwrite` requires the same configuration
and source identity/checksums. Changing either requires a new portfolio ID.
A hard process termination can leave a lock or hidden staging directory; inspect
that execution before removing its stale lock and retrying. Normal exceptions
clean staging and preserve the previous committed generation.

`experiment.load_portfolio_report(run_id)` validates completion, all recorded
hashes and the original classification dependency graph before restoring tables.
The reader refuses active locks and incomplete generations.
[Notebook 19](../../notebooks/19_binance_daily_portfolio_results_visual_report.ipynb)
reads that API and constructs three Portuguese charts directly in cells. It also
shows final capital, cash days, absent predictions and imputed operations.


## Explicit portfolio source selection

Select a saved classification execution with `--source-run-id`:

```sh
python -m tcc_crypto.experiment portfolio --run-id portfolio_01 --source-run-id full_01
```

`--source-run-id` identifies the input training execution, while `--run-id`
identifies the output portfolio execution. When the source option is omitted,
the configured latest-execution policy applies. An explicit source takes
precedence over that default and is validated under its saved configuration.
Missing or incompatible inputs produce an error without falling back to another
execution. The resolved source and selection mode are recorded in metadata.
This option is exclusive to the portfolio command. The Python API accepts the
same choice as `execute_portfolio(..., source_run_id="full_01")`.
