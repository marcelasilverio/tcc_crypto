---
type: Experiment Report
title: Complete daily SVM classification execution
description: Execution evidence for the 40-asset development search and frozen-parameter final classification evaluation.
tags: [svm, grid-search, walk-forward, classification, generated-evidence]
status: draft
authority: generated-evidence
as_of: "2026-10-23T00:00:00Z"
generated: { by: "process:codex", at: "2026-10-23T00:00:00Z" }
sources:
  - id: search-configuration
    resource: ../../configs/binance_daily_svm_grid_search.json
    title: Approved development and final-test protocol
  - id: final-configuration
    resource: ../../configs/binance_daily_svm_final_evaluation.json
    title: Final evaluation execution settings
  - id: omission-decision
    resource: ../decisions/svm-final-evaluation-single-class-windows.md
    title: Approved single-class omission and common-date comparison policy
  - id: universe-evidence
    resource: ../../outputs/binance/spot/1d/svm_final/binance_daily_svm_walk_forward_v1/universe/run_metadata.json
    title: Consolidated execution metadata and artifact checksums
---

# Complete daily SVM classification execution

## Scope and counts

The researcher explicitly authorized expansion to all configured assets and
implementation/execution of the approved final walk-forward evaluator. No raw
collection or financial backtest was executed.

| Evidence | Count or period |
| --- | --- |
| Requested assets | 40 |
| Assets with eligible searches and final comparisons | 37 |
| Eligible asset-target-window combinations | 331 |
| Grid candidate-fold fits | 184,698 |
| Development feature dates | 2019-07-01 through 2024-12-30 UTC |
| Final feature dates | 2025-01-01 through 2026-08-31 UTC |
| Final target dates | 2025-01-02 through 2026-09-01 UTC |
| Final dates per eligible combination | 608 |
| Dated model records across four classifiers | 804,992 |
| Common successful model observations | 803,440 |
| Omitted model observations | 1,552 |

NEIROUSDT and ENAUSDT lacked the required complete pre-test history. LUNAUSDT
remained explicitly excluded. TRXUSDT had seven eligible development searches;
the other fitted assets had nine each. Final single-class omissions occurred
for TRXUSDT: 388 date-target-window cases, represented once for each of the four
classifiers. These records retain actual labels and diagnostics, but no fabricated
prediction or decision score. No unexpected fit failures were found.

Every development dataset was checked for exact equality with the corresponding
date slice of the complete prepared dataset. Source checksums confirmed that
all 172 protected pre-existing raw and historical model files were unchanged.
An Excel temporary lock file created while a raw workbook was open was excluded
from the inventory comparison; no canonical raw artifact was added or changed.

## Execution and locations

Development preparation used `daily prepare --profile development --all-symbols`.
Four independent asset workers then called `workflows.svm.run` and
`workflows.final_evaluation.run`; parallel execution did not pool assets or
change candidate order, search settings or ranking. Two export workers regenerated
inspection workbooks without fitting models. Equivalent supported entrypoints are:

```sh
python -m tcc_crypto.daily prepare --profile development --all-symbols
python -m tcc_crypto.daily grid-search --all-symbols
python -m tcc_crypto.daily final-test --all-symbols
```

Outputs are stored beneath:

- development search: `outputs/binance/spot/1d/grid_search/binance_daily_svm_temporal_grid_search_v1/{symbol}/`;
- final evaluation: `outputs/binance/spot/1d/svm_final/binance_daily_svm_walk_forward_v1/{symbol}/`;
- complete-universe overview: `outputs/binance/spot/1d/svm_final/binance_daily_svm_walk_forward_v1/universe/experiment_overview.xlsx`.

Individual final folders contain dated predictions, metrics, eligibility, frozen
configurations, ROC/PR curve points and figures, configuration snapshots, checksums
and `svm_results.xlsx`. The overview preserves separate asset-target-window-model
metrics; it does not calculate a pooled performance score.

## Supervisor-review notebook and training-score reconstruction

[Notebook 16](../../notebooks/16_binance_daily_svm_experiment_results.ipynb)
collects the complete experiment into a read-only presentation with an individual
section for every configured coin. It separates training resubstitution,
development validation and final OOS, shows matched baselines, confusion counts,
ROC/PR curves, eligibility, frozen parameters and artifact locations. The selected
coin can be changed without fitting any model.

The completed full experiment had not recorded training scores. On 2026-10-23,
the researcher explicitly authorized reconstruction of the selected models for
this purpose. Only the 331 selected candidates were reconstructed on their three
original development folds: 993 fits across 37 eligible assets. The reconstruction
uses the original training-only selector and scaler, checks exact saved UTC
boundaries and selected features, and accepts each fit only when all seven
validation metrics reproduce the original saved scores (`rtol=1e-10`,
`atol=1e-12`, with matching undefined values). All 993 folds passed.

Training scores are saved under each final asset directory at
`supervisor_review/training_fold_metrics.csv`, with typed metadata, upstream
checksums, package versions and execution provenance. The explicit resumable
entrypoint is `workflows.experiment_review.reconstruct_in_sample()`. The notebook
only calls the read-only loader; reopening it does not repeat these fits.

In-sample means describe the selected candidate's development training folds;
they are not averages over final walk-forward training windows. Training and
validation means use overlapping folds, whereas final metrics use matched daily
predictions. Differences across these phases must not be interpreted as a
controlled estimate of overfitting. The reconstruction neither selects new
candidates nor changes original search tables, final predictions or metrics.

The review notebook was executed against the saved complete run with all four
figures embedded; representative figures were inspected visually. Read-only
views were also exercised for all three excluded assets. Checksums of 643 original
model-result artifacts matched their saved manifests. The expanded suite passed
198 tests, including temporal reconstruction, validation-drift rejection,
phase separation, omission counts, read-only reloads, excluded-asset views,
backend-independent figure embedding and notebook architecture checks. The Ruff,
OKF and whitespace checks listed below passed again after the review changes.

## Verification and interpretation

The audit checked temporal boundaries and gaps, actual next-day target dates,
matched baseline samples, confusion counts and derived metrics, sample scaler
means against their exact past training windows, all result checksums, workbook
row counts and numerical metric correspondence. Representative final and search
workbook ranges and final curve figures were visually inspected.

Executed verification commands:

```sh
PYTHONPATH=src MPLCONFIGDIR=/tmp/tcc_complete_experiment/matplotlib MPLBACKEND=Agg python -m pytest -q
python -m ruff check src/tcc_crypto tests scripts
python -m ruff format --check src/tcc_crypto tests scripts
python scripts/validate_okf_docs.py docs
git diff --check
```

All 190 tests passed. Two expected sklearn warnings arose from the synthetic
single-class evaluation test; undefined ROC/PR statistics remain explicitly
marked rather than receiving invented values.

After visual inspection, precision-recall figures were regenerated with
`steps-post` rendering, matching sklearn's display convention. The 10 final
evaluation tests passed again after that figure-export refactor. Checksums
confirmed that all 320 per-asset numeric tables, configuration snapshots and
workbooks remained unchanged; only images and their export metadata were updated.

This is classification evidence for the fixed ex-post 2026 candidate universe,
not an unbiased reconstruction of historical investability or a financial-return
backtest. Parabolic SAR parameters remain provisional as previously documented.
Omitted dates must be considered when interpreting matched-sample performance.
Execution metadata records the Git revision and a dirty working tree: the new
implementation had not been committed, so the revision alone does not identify
every executed source change. No human verification entry is asserted here.
