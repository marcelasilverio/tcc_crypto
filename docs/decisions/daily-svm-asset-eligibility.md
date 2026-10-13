---
type: Methodology Decision
title: Daily SVM asset eligibility
description: Approved ex-post candidate universe, dynamic history requirement, per-asset model search, and LUNAUSDT exclusion for the daily SVM classification experiment.
tags: [svm, asset-universe, eligibility, listing-history, survivorship-bias, luna]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-13T00:00:00Z" }
sources:
  - id: daily-collection-config
    resource: ../../configs/binance_selected_usdt_daily_collection.json
    title: Binance selected USDT daily collection configuration
  - id: daily-collection-decision
    resource: daily-data-collection.md
    title: Daily data collection
  - id: hourly-universe-decision
    resource: hourly-data-collection-universe.md
    title: Hourly data-collection universe
  - id: grid-search-config
    resource: ../../configs/binance_daily_svm_grid_search.json
    title: Daily SVM temporal grid-search configuration
  - id: temporal-grid-decision
    resource: svm-temporal-grid-search-and-final-evaluation.md
    title: Temporal SVM grid search and final evaluation
---

# Daily SVM asset eligibility

## Approved classification universe

On 2026-10-13, the researcher approved the 40 Binance Spot USDT pairs in
`configs/binance_selected_usdt_daily_collection.json` as the candidate pool for
the daily SVM classification experiment. The pool is fixed from the collection
snapshot that ends on 2026-09-01, but individual assets enter the modeling
sample only after satisfying the history and data-quality requirements below.

The grid search is executed separately for every eligible combination of
symbol, binary target, and training-window length. Hyperparameters are not
pooled across cryptocurrencies. A complete symbol therefore has nine searches:
three targets multiplied by three training-window lengths.

This decision defines classifier eligibility. It does not by itself approve
portfolio membership, liquidity thresholds, capital allocation, or the
behavior when no asset receives a positive signal.

## Ex-post-universe limitation

The 40-pair pool was selected using cumulative Binance activity and trading
status observed through the 2026 snapshot. Applying that list to dates from
2019 onward is therefore an ex-post fixed-universe experiment. It is not a
historically reconstructed investable universe and does not eliminate
survivorship or future-selection bias.

All reports, tables, and conclusions must state this limitation. Results may
describe classifier behavior within the selected 2026-snapshot sample, but
must not claim to represent an unbiased historical selection from every asset
that was investable at each earlier date.

Reconstructing a point-in-time market universe would require a separate rule
and evidence based only on information available at every historical decision
date. That broader reconstruction is outside this decision.

## Dynamic entry and minimum history

No observation may be synthesized before an asset's first Binance candle. An
asset enters the classification experiment only when all required history
exists in derived, chronologically ordered data.

The common minimum is `271` complete, labeled modeling rows before the search:

```text
90 maximum training observations
+ 1 excluded gap observation
+ 3 validation blocks x 60 observations
= 271 complete labeled rows
```

Using the maximum 90-day training window as the eligibility basis keeps the
eligible symbol set comparable across the 60-, 75-, and 90-day experiments.
The requirement applies after internal-gap treatment, feature calculation,
leading indicator warm-up removal, and next-day target construction. Raw
candle count alone is not sufficient.

For each symbol-target-window search:

- every inner training fold must contain both target classes so that `SVC` can
  be fitted;
- validation folds with a single observed class must be retained and marked
  when a metric such as ROC-AUC is undefined;
- all active feature values and target values must be complete;
- timestamps must be unique, chronological, daily, and UTC;
- dates before listing must remain absent; and
- carried-forward internal-gap rows must retain their audit marker.

Failure at one target or window does not justify silently removing other valid
symbol-target-window results. Every included or excluded combination must
appear in an asset-eligibility manifest with its first observation, complete
row count, class counts, status, and reason.

## LUNAUSDT exclusion

`LUNAUSDT` is excluded from the definitive classification experiment. Its
approved 17-day internal-gap forward fill addresses missing daily observations
but does not establish economic continuity across the Terra ecosystem collapse
and migration.

These are separate concerns:

```text
technical continuity: internal missing dates can be represented and audited
economic continuity: the pre- and post-migration asset series may not represent
                     the same investable object
```

Until a later methodology decision establishes an interpretable continuity or
series-break rule, LUNAUSDT must remain in collection and data-quality evidence
but outside SVM fitting, tuning, final classifier metrics, and downstream
portfolio signals.

## Final-test eligibility

The approved final test uses feature dates from 2025-01-01 through 2026-08-31.
An otherwise eligible asset participates only on dates for which the complete
trailing window and approved one-observation gap are available. Missing
eligibility on an earlier test date does not authorize backfilling or using a
shorter training window.

The selected hyperparameters are specific to the same symbol, target, and
window used in the final test. They remain frozen during the final walk-forward
evaluation. New assets that lack the required pre-test search history do not
enter merely because they accumulate enough observations after the final test
has started; admitting them would require hyperparameter selection using the
reserved test period.

## Required evidence

The eligibility output must record at least:

- the 40 requested candidate symbols in their configured order;
- the explicit LUNAUSDT exclusion;
- first and last available observations;
- observed and imputed row counts;
- first complete feature row;
- complete labeled row count before the search;
- class counts by target and inner training fold;
- eligibility by symbol, target, and window;
- first and last permitted final-test feature dates;
- exclusion or delayed-entry reason; and
- the source-data and configuration identifiers used to produce the manifest.

Generated manifests remain outside Git, while this decision and its small
configuration remain versioned.
