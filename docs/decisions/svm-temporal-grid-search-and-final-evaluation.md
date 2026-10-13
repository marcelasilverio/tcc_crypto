---
type: Methodology Decision
title: Temporal SVM grid search and final evaluation
description: Approved conditional SVC search, nested temporal model-selection structure, frozen-parameter walk-forward test, and classifier performance reporting.
tags: [svm, grid-search, temporal-validation, walk-forward, classification-metrics, roc]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-13T00:00:00Z" }
sources:
  - id: grid-search-config
    resource: ../../configs/binance_daily_svm_grid_search.json
    title: Daily SVM temporal grid-search configuration
  - id: svm-pilot-decision
    resource: svm-pilot-and-hyperparameter-search.md
    title: SVM pilot and hyperparameter-search plan
  - id: daily-feature-selection-decision
    resource: daily-feature-selection.md
    title: Daily rolling feature selection
  - id: target-decision
    resource: daily-binary-targets-and-holding-period.md
    title: Daily next-day binary targets and same-day exit
  - id: asset-eligibility-decision
    resource: daily-svm-asset-eligibility.md
    title: Daily SVM asset eligibility
  - id: sklearn-svc
    resource: https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVC.html
    title: scikit-learn SVC documentation
  - id: sklearn-grid-search
    resource: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GridSearchCV.html
    title: scikit-learn GridSearchCV documentation
  - id: sklearn-time-series-split
    resource: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
    title: scikit-learn TimeSeriesSplit documentation
---

# Temporal SVM grid search and final evaluation

## Decision and scope

On 2026-10-13, the researcher approved a two-level temporal model-selection
and evaluation design for the daily SVM experiment. The supervisor additionally
required classifier accuracy, precision, and a receiver operating
characteristic (ROC) curve. The approved design retains recall and F1 from the
pilot, adds balanced accuracy, ROC area under the curve (ROC-AUC), and
precision-recall diagnostics, and uses F1 as the primary grid-search selection
metric.

This decision governs SVM hyperparameter selection and final classifier
evaluation. Asset eligibility is governed by the related
[Daily SVM asset eligibility](daily-svm-asset-eligibility.md) decision. Neither
decision approves portfolio construction, transaction costs, or the financial
backtest.

The completed BTCUSDT 2019H2 default-SVC run remains a pipeline pilot. Its
observed metrics demonstrate executable data preparation and training logic;
they are not the definitive performance estimate and must not be presented as
the result of the approved grid search.

## Temporal evaluation hierarchy

The definitive modeling procedure has two strictly ordered levels:

```text
development period                         final test period
--------------------------------------     ------------------------------
inner temporal grid search                 frozen-parameter walk-forward
training folds -> later validation folds   past window -> next observation
```

The development period is used to compare candidate hyperparameters. The final
test period must occur chronologically after the development period and must
remain untouched until the grid search has selected a configuration. Final
test observations must not influence feature selection, scaling, candidate
ranking, tie breaking, or any revision of the parameter grid.

Using validation observations to choose a model makes those observations part
of model development even when they are never passed directly to `fit` as
training rows. Consequently, reporting the same validation scores as final
out-of-sample evidence would be optimistically biased.

The approved feature-date boundaries are:

- development: 2019-07-01 through 2024-12-30;
- boundary gap: 2024-12-31; and
- final test: 2025-01-01 through 2026-08-31.

Because every feature row at `t` is labeled with D0 at `t + 1`, the final test
target dates run from 2025-01-02 through 2026-09-01. Dates refer to UTC daily
observations. The one-day boundary gap prevents the final development label
from sharing a candle with the first final-test feature row.

## Inner temporal validation

The approved inner search uses `TimeSeriesSplit` with three chronologically
ordered splits, `test_size=60`, `gap=1`, and no random shuffling. For every
split, all training observations precede the validation observations. The
search is executed separately for each combination of:

- eligible symbol;
- binary target: `target_2pct`, `target_3pct`, and `target_4pct`; and
- rolling training-window length: `60`, `75`, and `90` daily observations.

The applicable training-window length is passed as `max_train_size`, so each
fold uses at most that many immediately preceding training observations. Every
validation block contains 60 observations, and one observation at the end of
the available training side is excluded before validation. The gap matches the
one-observation next-day target horizon and provides a conservative separation
between labels used to fit the model and candles represented in validation
features.

With fixed `max_train_size`, `test_size`, and three splits, `TimeSeriesSplit`
places the validation blocks in the most recent eligible portion of the
development sample. Earlier development history remains relevant for data
availability and eligibility but is not silently added to a fixed-length
training fold.

Every split must record its training start, training end, validation start,
validation end, target, window size, and positive and negative class counts.
Any fold that cannot calculate a requested metric because only one class is
present must be retained with an explicit diagnostic; it must not be silently
discarded or assigned a fabricated score.

## Leakage-safe preprocessing inside each fold

Preprocessing is part of model fitting and must be repeated inside every inner
training fold in this order:

1. take the chronologically earlier training rows;
2. fit the approved variance filter on those rows only;
3. fit the approved correlation filter on the variance-filtered training rows
   only;
4. transform the validation rows with the already fitted selectors;
5. fit `StandardScaler` on the selected training features only;
6. transform the validation rows with the already fitted scaler;
7. fit the candidate `SVC` on the transformed training rows; and
8. obtain predictions and decision scores for the later validation rows.

Feature selection or scaling performed once before temporal splitting would
allow validation-distribution information to affect model construction and is
prohibited. Target columns, future D0 values, target dates, imputation audit
markers, and any future-dependent outcome must never enter the feature matrix.

## Approved conditional SVC grid

Six SVC hyperparameters are included: `kernel`, `C`, `gamma`, `degree`,
`coef0`, and `class_weight`. The grid is conditional because some parameters
have no effect for particular kernels.

### Linear kernel

```text
kernel:       [linear]
C:            [0.1, 1, 10]
class_weight: [None, balanced]
```

This branch contains `3 x 2 = 6` candidates. `gamma`, `degree`, and `coef0` are
not included because they do not define the linear kernel.

### Radial basis function kernel

```text
kernel:       [rbf]
C:            [0.1, 1, 10]
gamma:        [scale, 0.01, 0.1]
class_weight: [None, balanced]
```

This branch contains `3 x 3 x 2 = 18` candidates.

### Polynomial kernel

```text
kernel:       [poly]
C:            [0.1, 1, 10]
gamma:        [scale, 0.01, 0.1]
degree:       [2, 3, 4]
coef0:        [0, 0.5, 1]
class_weight: [None, balanced]
```

This branch contains `3 x 3 x 3 x 3 x 2 = 162` candidates. Across all three
branches, each target-window search evaluates `186` configurations rather than
the `729` configurations produced by an indiscriminate six-dimensional grid
with three values per dimension.

With three inner splits, three targets, and three window lengths, the approved
design implies `186 x 3 x 3 x 3 = 5,022` inner candidate-fold fits per eligible
symbol before final refits. This count does not include the later walk-forward
final test.

`class_weight=None` preserves the unweighted estimator, while
`class_weight="balanced"` tests inverse-frequency class weighting calculated
from each training fold. No manually chosen positive-class multiplier is
approved. A learning rate is not an `SVC` parameter and must not be introduced.
Solver-oriented settings such as `tol`, `shrinking`, `cache_size`, `max_iter`,
and probability estimation remain at their documented defaults unless a later
decision explicitly expands the grid.

## Model-selection criterion

Mean inner-validation F1 is the approved primary ranking metric. F1 balances
precision and recall and prevents high accuracy caused by majority-negative
predictions from being treated as sufficient classifier performance.

The search must also calculate and persist, for every candidate and fold:

- accuracy;
- precision for the positive class;
- recall for the positive class;
- F1 for the positive class;
- balanced accuracy;
- ROC-AUC from continuous decision scores; and
- average precision for the positive class.

Candidate F1 values within `1e-12` are treated as tied. Ties are resolved in
this fixed order:

1. higher mean validation precision;
2. lower validation F1 standard deviation;
3. higher mean validation ROC-AUC;
4. simpler kernel in the order `linear`, `rbf`, then `poly`;
5. lower `C`; and
6. earlier deterministic position in the configured parameter grid.

The final grid-order fallback resolves parameters such as `gamma`, `degree`,
or `coef0` without consulting final-test outcomes. No secondary metric or
ordering may be changed after the final test is inspected.

## Hyperparameter freezing and final walk-forward test

After the inner search chooses one configuration for a symbol-target-window
combination, that configuration is frozen for the complete final test period.
The grid search is not rerun in response to final test errors, newly
accumulated history, or market regimes.

For each final test date, the system must:

1. exclude the observation immediately preceding the evaluated feature row as
   the approved one-observation gap;
2. take the preceding `60`, `75`, or `90` eligible daily training observations,
   according to the evaluated window;
3. refit feature selection on that trailing window;
4. refit `StandardScaler` on the selected training features;
5. fit a new `SVC` using the frozen symbol-target-window hyperparameters;
6. transform the evaluated feature row without fitting on it;
7. emit its binary prediction and continuous `decision_function` score; and
8. advance by one daily observation and repeat.

Refitting the selector, scaler, and estimator is required because the rolling
training sample changes. Refitting or revising the hyperparameter search is
prohibited during final evaluation. This distinction preserves a realistic
walk-forward simulation while keeping model-selection information isolated
from the test period.

## Required classifier evaluation

Final performance must be reported independently for every target-window pair.
At minimum, each result includes:

- observation count and evaluation dates;
- actual and predicted class counts;
- true negatives, false positives, false negatives, and true positives;
- accuracy;
- precision;
- recall;
- F1;
- balanced accuracy;
- ROC curve points and ROC-AUC;
- precision-recall curve points and average precision; and
- all dated predictions and decision scores used to reproduce the metrics.

The supervisor-requested ROC curve must use `SVC.decision_function` scores,
not binary class predictions. The persisted curve table must contain false
positive rate, true positive rate, and threshold. ROC-AUC summarizes ranking
across thresholds but does not identify an operational trading threshold.

Because positive targets become rarer as the return threshold increases, the
precision-recall curve and average precision are retained as complementary
diagnostics. They do not replace the required ROC curve.

If the final evaluation subset contains only one observed class, ROC-AUC and
the ROC curve are undefined. The system must store an unavailable value and an
explicit reason rather than inventing a curve or score.

## Required comparisons

The tuned model must not be interpreted in isolation. Results must be compared
with these exact baselines:

- `DummyClassifier(strategy="constant", constant=0)` as an always-negative
  classifier, exposing accuracy attributable solely to class imbalance;
- `DummyClassifier(strategy="prior")` as the deterministic
  training-class-frequency baseline, using the positive-class probability for
  its ROC score; and
- the already approved default-parameter SVC under the same temporal test
  boundaries and preprocessing safeguards.

The comparison must use identical symbol-target-window observations so that
metric differences are not caused by different evaluation samples. The
always-negative classifier may have a constant ROC score; when both observed
classes exist its expected discriminative AUC is 0.5.

## Reproducibility and persisted evidence

Every search execution must preserve enough information to reconstruct model
selection without rerunning the experiment. Required evidence includes:

- experiment identifier and execution timestamp;
- Git revision and dirty-working-tree status;
- configuration snapshot and checksum;
- source-data identifiers, symbols, date ranges, and checksums where available;
- Python and package versions;
- target and training-window length;
- all candidate parameters;
- all temporal fold boundaries and class counts;
- selected features per fitted fold;
- scaler and estimator parameter snapshots;
- per-fold and aggregate metrics for every candidate;
- candidate rank and selected configuration;
- fit and scoring durations;
- failures or undefined metrics with explicit diagnostics;
- final dated predictions and decision scores;
- final metric tables and curve points; and
- paths and checksums for generated artifacts.

Generated model data and metric artifacts remain outside Git. The small JSON
configuration and methodology documentation are versioned.

## Approved choices and remaining scope boundaries

| Topic | Status | Rule |
| --- | --- | --- |
| Validation hierarchy | Approved | Inner temporal grid search followed by an untouched final test |
| Inner split count | Approved | Three chronological splits without shuffling |
| Development feature dates | Approved | 2019-07-01 through 2024-12-30 UTC |
| Final-test feature dates | Approved | 2025-01-01 through 2026-08-31 UTC |
| Final-test target dates | Approved | 2025-01-02 through 2026-09-01 UTC |
| Inner validation blocks | Approved | Three blocks of 60 observations |
| Gap | Approved | One excluded observation before inner validation and final prediction |
| Search separation | Approved | Independent search for each symbol-target-window combination |
| Conditional SVC grid | Approved | 186 candidates per symbol-target-window combination |
| Primary selection metric | Approved | Mean validation F1 |
| Tie breaking | Approved | Precision, F1 stability, ROC-AUC, kernel simplicity, lower C, then grid order |
| Required supervisor metrics | Approved | Accuracy, precision, and ROC curve |
| Complementary metrics | Approved | Recall, F1, balanced accuracy, ROC-AUC, PR curve, and average precision |
| Final evaluation | Approved | One-step walk-forward with frozen hyperparameters |
| Baselines | Approved | Constant-zero dummy, prior dummy, and default SVC |
| Classification universe | Approved separately | 40-pair ex-post pool with dynamic eligibility and LUNAUSDT excluded |
| Portfolio construction | Outside this decision | Requires later approval |
| Transaction costs and allocation | Outside this decision | Requires later approval |

The classifier grid-search protocol is approved for implementation. Later
portfolio and financial-backtest decisions remain independent and must not be
inferred from this approval.
