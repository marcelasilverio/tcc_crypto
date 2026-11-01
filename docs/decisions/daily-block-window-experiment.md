---
type: Methodology Decision
title: Daily block-window SVM experiment
description: October 31 revision defining raw availability, candle treatment, consecutive training and validation blocks, and integrated temporal SVM search.
tags: [daily, svm, temporal-validation, missing-data, feature-selection]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-31T12:00:00Z" }
sources:
  - id: researcher-revision
    resource: "source-artifact:researcher-conversation-2026-10-31"
    title: Researcher corrections following supervisor review and documentation discussion
  - id: feature-excerpt
    resource: ../references/silva_2026_feature_code_excerpt.md
    title: Feature-engineering code excerpt from Silva 2026
  - id: sklearn-search
    resource: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GridSearchCV.html
    title: GridSearchCV documentation
  - id: sklearn-temporal-validation
    resource: https://scikit-learn.org/stable/modules/cross_validation.html
    title: Cross-validation of time series data
---

# Daily block-window SVM experiment

## Authority and implementation status

On 2026-10-31 the researcher revised the experimental logic after supervisor
review. This document records the explicit decisions in that conversation.
It supersedes conflicting historical rules in the linked decisions below;
unchanged research choices are not implicitly revoked. Recommendations and
unresolved details are explicitly separated from approved choices.

The approved implementation is described in the
[implementation guide](daily-code-organization.md). Sources and results of the
previous protocol are archived. Small automated tests exercise this revision;
no complete production experiment has been executed as part of the refactor.

## Data period, availability and treatment

- The study calendar is 2019-07-01 through 2026-09-01, inclusive, in UTC.
- Build the availability CSV from collected raw candles, before filling
  gaps. Rows are every calendar day and columns are all study cryptocurrencies.
- Record 1 only for a complete, valid candle; record 0 for absent, incomplete
  or invalid candles. Validate all required candle fields, not only prices.
- Preserve raw files. Disregard invalid or incomplete candles in the derived
  base exactly as if no observation had arrived for that date.
- Within each asset's first-to-last valid candle span, fill internal missing
  days using the last valid observation's values. Preserve the missing day's
  calendar identity and the source observation date in audit metadata.
- Do not extend history before the first valid candle or after the last valid
  candle. Different assets can have different available periods.
- Record observed, invalid, incomplete and filled states separately. A filled
  derived candle never changes a raw-availability 0 to 1.
- Validate and treat candles before calculating any features or targets;
  verify the treated base before proceeding.

Existing pre-period warm-up history can support feature calculation but is not
part of the reported study calendar. Listing dates do not themselves disqualify
an asset. Insufficient raw collection must be investigated at the data stage,
not silently treated as model eligibility. Feature warm-up and unavailable
future labels remain distinct from missing candles.

## Features, targets and available modeling period

Calculate features and targets from the treated base before constructing
windows. Use three binary target thresholds: 1%, 2% and 3%.
The previously approved next-day D0 formula remains:

```text
D0(t + 1) = (high(t + 1) - open(t + 1)) / open(t + 1)
y_q(t) = 1 if D0(t + 1) >= q, otherwise 0
q in {0.01, 0.02, 0.03}
```

Future outcomes must never enter feature columns. A row without an observable
next-day outcome remains unlabeled, not automatically negative. Record feature
dates and outcome dates separately. The researcher clarified that each row and
window date refers to the feature day t; its supervised target refers to t + 1.
Training uses in-sample targets. Out-of-sample targets are withheld from fitting
and prediction and used afterward to calculate validation metrics.

This alignment requires checking information availability at execution time.
For example, with the last training feature day December 2 and the first
validation feature day December 3, fitting after the December 3 candle closes
can use the final training label and predict December 4 using December 3
features. This is a timing explanation, not a change to the target formula,
window length or consecutive-calendar rule. Persist fit/prediction timestamps
and test the same availability condition at internal CV boundaries.

Determine each asset's available modeling period from its feature/target
dataset. Do not concatenate nonconsecutive dates after dropping problematic
rows. Leading feature warm-up and terminal unavailable labels must be visible
in the data audit, rather than disguised as internal raw-data gaps.

## Consecutive outer blocks

Run separate experiments with W equal to 60, 75 and 90 daily observations.
For each asset's available modeling period:

```text
fit 1: in-sample [1 .. W]       out-of-sample [W+1 .. 2W]
fit 2: in-sample [W+1 .. 2W]    out-of-sample [2W+1 .. 3W]
fit 3: in-sample [2W+1 .. 3W]   out-of-sample [3W+1 .. 4W]
```

The previous complete out-of-sample block becomes the next in-sample block.
Every in-sample has exactly W days. Only the final out-of-sample may be shorter;
an empty out-of-sample does not form an evaluation pair. A partial terminal
block cannot subsequently serve as a full in-sample. There are no skipped
calendar days between outer blocks. Asset-specific start dates are permitted.

The previous common 271-row eligibility minimum, fixed development/final-test
calendar split, excluded outer boundary day and daily one-step refitting are
not the revised protocol. The basic outer-window minimum is W training days
and at least one validation day; feasibility of internal CV is separate.

## Training and validation

For each asset, target, W and outer block, run a new integrated training/search
procedure using only that in-sample. Grid search is part of training, not a
separate historical stage whose hyperparameters remain frozen for all future
blocks. Use temporal internal validation following scikit-learn's
TimeSeriesSplit approach: training precedes internal validation, without random
shuffling. The researcher approved the documented TimeSeriesSplit defaults:
`n_splits=5`, `max_train_size=None`, `test_size=None`, `gap=0`.
These replace the earlier internal split settings for this block protocol.

Pass a TimeSeriesSplit instance to GridSearchCV's cv argument; leaving
GridSearchCV's cv unset would not select temporal validation automatically.
Internal training expands within the current outer in-sample only. Each internal
validation has floor(W / 6) days; the remainder belongs to the initial training
subset. The resulting sizes are:

| Outer in-sample | Training sizes in splits 1-5 | Validation size per split |
| --- | --- | --- |
| 60 days | 10, 20, 30, 40, 50 | 10 days |
| 75 days | 15, 27, 39, 51, 63 | 12 days |
| 90 days | 15, 30, 45, 60, 75 | 15 days |

For example, the 60-day case starts with days 1-10 training and 11-20
validation, then days 1-20 training and 21-30 validation, ending with
days 1-50 training and 51-60 validation. All these dates are in-sample.
After selection, refit uses the complete 60, 75 or 90 days. Internal subsets
are not required to have the full outer training-window length.

Source: [TimeSeriesSplit defaults](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html).
Persist these effective values explicitly during configuration migration so
future library default changes do not silently alter the experiment. No
historical results are converted into results of the revised preprocessing order.

Fit feature selection and scaling independently on each internal training
subset. With refit enabled, fit the selected procedure on the complete outer
in-sample. Apply its learned selector, scaler and model unchanged to the
corresponding outer out-of-sample. The out-of-sample must not influence tuning,
selection, scaling or refitting for that outer block. In the next block it is
historical training data, as expressly approved.

On 2026-11-01 the researcher explicitly revised preprocessing order: normalization
is the first operation on each training window, before feature selection. This
supersedes the previous selection-before-scaling order. The approved order is:

```text
features -> StandardScaler -> variance filter -> correlation filter -> SVC
```

The approved implementation uses a Pipeline inside GridSearchCV for enforcing
these boundaries; equivalent explicit coordination must preserve the same fit
scope. Normalizing an entire in-sample before internal CV is not equivalent.

StandardScaler is fitted on all configured features, using only each internal
training subset or the complete in-sample at refit. Selection audit variances
therefore describe standardized inputs; scaler audit covers every input feature
and records its original mean and variance. Nonconstant standardized features
generally have variance one, so the 0.01 variance filter will primarily remove
constant features. The threshold remains unchanged by this ordering decision.
The effective configuration records `pipeline_order`, including both
preprocessing and the SVC classifier, making old run
configurations incompatible with the revised pipeline.

## Exact feature-selection reference

The researcher explicitly chose the selection procedure in
`recorte/recorte_features.py`, demonstrated by `recorte/exemplo_uso.py`:

1. Preserve the supplied 22-feature order and apply VarianceThreshold with
   threshold 0.01 to standardized training features. Features must exceed the
   threshold to survive.
2. If that call raises ValueError, the excerpt computes pandas sample variances
   and returns only the feature with the largest variance.
3. If fewer than two features survive, return without correlation filtering.
4. Otherwise use DropCorrelatedFeatures with Pearson correlation, threshold
   0.8 and missing_values="ignore".

This approval concerns selection; it does not automatically approve every
feature-engineering parameter or the example's fixed 14-row warm-up removal.
Retain fitted selectors for applying the same feature subset to validation.
Variance and correlation are selection diagnostics, not predictive importances.
Do not substitute supervised importance ranking, RFE or a different selector.

The excerpt catches all ValueError instances. Its broad fallback must be visible
in diagnostics; do not silently equate every exception with low variance. The
fallback's pandas sample variance and the selector's variance use different
conventions and must be identified separately.

## Required outputs and recommended audit structure

The researcher requires daily binary predictions and actual labels for both
in-sample and out-of-sample, persisted as CSV matrices. Precision and
recall are calculated per window and separately for the two sets, not per day.
Other classification metrics may also be retained. In-sample results describe
training fit and are not out-of-sample evidence.

Preserve asset, target, W, outer-block identifier, sample role, feature date and
outcome date. The same day can have different predictions as out-of-sample in
one block and in-sample in the next; exports must not overwrite these records.
An unavailable prediction or label must never become a fabricated binary 0.

The researcher also requires displayed and saved feature-selection diagnostics,
including every selected and discarded feature. Use one concise selection CSV
with original feature order, variance, selected status, discard stage/reason,
and related feature/correlation where relevant. Keep full correlations, fold
boundaries, exception details and fallback variances in technical audit CSVs.
Distinguish internal-fold fits from the final full-in-sample refit.

The [CSV artifact organization decision](csv-artifact-organization.md) replaces
all earlier workbook/tab proposals. Group results by execution, avoid directories
per coin/window/target, and use the same CSV tables for computation and inspection.
JSON remains appropriate for configuration, schemas and provenance, not duplicate
tabular exports. Preserve source checksums, package versions, effective parameters
and raw-to-treated data audit.

## Confirmed continuities after the initial revision

- Keep the previously approved 186-candidate conditional SVC grid unchanged.
  Keep mean inner-validation F1 as the primary selection criterion and the
  existing deterministic tie-breaking rules, specified in the historical
  [grid-search decision](svm-temporal-grid-search-and-final-evaluation.md).
  Only the placement and repetition of search change: search runs anew in
  every outer in-sample.
- Keep the existing single-class training behavior unchanged. Record the
  failure/status and class counts; do not fabricate a prediction, shorten the
  window, or substitute a different model. Preserve existing failed-fold
  eligibility and common-successful-date comparison policies. The
  [single-class decision](svm-final-evaluation-single-class-windows.md) remains
  the authority for that behavior; its old calendar/frozen-search context
  does not return with it.
- Preserve current metric conventions: precision, recall and F1 use
  zero_division=0; single-class evaluation ranking metrics remain unavailable
  with diagnostics, following the existing metric implementation. Audit
  missing outputs separately from valid negative signals.
- Keep LUNAUSDT excluded from model fitting, classifier evaluation and downstream
  portfolio signals. Retain its raw observations in availability and quality
  evidence. This economic-continuity exclusion is independent of gap treatment.

## Execution prerequisites and scope

Target availability, validation, schemas and migration are covered by the active
implementation and its tests. The existing Parabolic SAR verification caveat is
preserved; its formula was not silently changed. Portfolio optimization, costs
and no-positive-signal behavior are outside the implemented classification scope.

## Related documents

- [Experiment diagram](daily-block-window-experiment-diagram.md)
- [Daily feature selection](daily-feature-selection.md)
- [Sample and gap treatment](daily-sample-and-missing-data.md)
- [Targets and holding timing](daily-binary-targets-and-holding-period.md)
- [Historical temporal grid search](svm-temporal-grid-search-and-final-evaluation.md)
- [Asset eligibility](daily-svm-asset-eligibility.md)
