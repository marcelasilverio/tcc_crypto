---
type: Experiment Report
title: Daily SVM execution walkthrough validation
description: Isolated BTCUSDT notebook execution and equivalence checks against historical evidence.
tags: [svm, reproducibility, notebooks, generated-evidence]
status: draft
authority: generated-evidence
as_of: "2026-10-29T00:00:00Z"
generated: { by: "process:codex", at: "2026-10-29T00:00:00Z" }
sources:
  - id: walkthrough
    resource: ../../notebooks/17_binance_daily_svm_experiment_walkthrough.ipynb
    title: Executed didactic experiment walkthrough
  - id: search-configuration
    resource: ../../configs/binance_daily_svm_grid_search.json
    title: Approved grid search protocol
  - id: previous-execution
    resource: daily-svm-complete-classification-2026-10-23.md
    title: Previous complete classification execution
---

# Daily SVM execution walkthrough validation

## Scope

Notebook 17 executed BTCUSDT with `RUN_ID=supervisor_20261029_btc_v1`, using
existing raw observations and the unchanged approved configurations. Notebook 16
remains the saved-results presentation. No collection or other-asset training was
performed. Portuguese explanations are authorized only for Notebook 17.

The walkthrough coordinates existing functions through
`workflows/experiment_walkthrough.py`. Its run mode persists each stage; load mode
requires saved inputs. First-fold preprocessing diagnostics are persisted during
run mode, so load mode does not fit even a selector or scaler. The command guide
is included beside each stage. CLI `--run-id` and `training-review` are new;
existing commands retain their default behavior without a run identifier.

## Evidence

| Artifact | Rows |
| --- | ---: |
| Development aligned data / features / dataset | 2,041 / 2,040 / 2,010 |
| Full-period aligned data / features / dataset | 2,650 / 2,649 / 2,619 |
| Grid fold evaluations | 5,022 |
| Candidate rankings across nine combinations | 1,674 |
| Selected configurations | 9 |
| Final dated model records | 21,888 |
| Final metric rows | 36 |
| Reconstructed selected training folds | 27 |

The grid used all 186 candidates, three folds, three targets and three training
windows. Final records cover 608 dates and four models per target/window.
In-sample values describe selected development training folds, not the training
windows of the final walk-forward. The fixed historical universe and provisional
SAR limitations remain unchanged; classifier scores are not financial returns.

All eight preparation tables, four grid tables, six final tables and the training
review were compared with their historical equivalents using pandas frame
assertions (`rtol=atol=1e-12`, excluding fit durations and frame attributes).
Values, ordering and types agreed. All 3,011 existing tracked research artifacts
under `data/` and `outputs/` retained their pre-execution SHA-256 checksums.
The notebook's five rendered figures were visually inspected.

## Locations and usage

Preparation uses contexts `binance_daily_svm_temporal_grid_search_v1` and
`binance_daily_svm_temporal_grid_search_v1_full_period`, each followed by
`runs/supervisor_20261029_btc_v1`. Final outputs use context
`binance_daily_svm_walk_forward_v1` with the same run suffix. The notebook's path
table lists every resolved file, including four Excel workbooks and saved
preprocessing diagnostics. Historical paths remain valid when `run_id` is absent.

To revisit the delivered execution, set `MODE="load"`. To execute again without
replacing it, choose a new `RUN_ID` and keep `MODE="run"`. Repeating existing stage
writes requires explicit overwrite. Workbook export reads saved tables without
collecting or fitting. The command guide documents optional all-symbol execution;
that expansion was not part of this validation.

## Automated validation

Small local fixtures execute every code cell in run mode and then load mode with
SVC/scaler fitting and network access blocked. Tests also cover workbook
regeneration, path overrides, legacy signatures, missing inputs, overwrite
protection, cross-run metadata rejection and CLI routing.

```sh
PYTHONPATH=src python -m pytest -q
python scripts/validate_okf_docs.py docs
python -m ruff check src/tcc_crypto tests scripts
python -m ruff format --check src/tcc_crypto tests scripts
```

Result: 202 tests passed, with two expected scikit-learn warnings from the existing
single-class metric test. OKF validation, Ruff lint, Ruff format checks and
`git diff --check` passed. Tests used `MPLBACKEND=Agg` and a temporary writable
Matplotlib cache. All four generated workbooks were opened and checked for sheet
sizes and Excel error cells; none were found.
