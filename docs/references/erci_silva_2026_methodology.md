---
type: External Methodology Reference
title: Methodological reference from Silva 2026
description: Process from Silva's equity-portfolio dissertation documented for comparison and adaptation.
tags: [external-reference, machine-learning, portfolio-selection, temporal-validation]
status: stable
authority: external-reference
generated: { by: "process:okf-migration", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:marcela-prata-silverio", at: "2026-09-29T10:16:31Z" }
sources:
  - id: silva-2026-dissertation
    resource: "source-artifact:dissertacao-mestrado-erci.docx"
    title: Tomada de decisao em selecao de portfolio de acoes do Ibovespa com o uso de machine learning
    author: "human:ercilene-micaela-brito-da-silva"
    checksum: "sha256:be3b2e8debe8c52b1d7ac8cc3ab75ae23f284064142c96627b1c614c12e7f014"
---

# Methodological reference from Silva 2026

## Purpose and status

This document records the process described in the methodology chapter of
Ercilene Micaela Brito da Silva's master's dissertation, *Decision-making in
Ibovespa stock portfolio selection using machine learning*. The dissertation
is a methodological reference for this repository. It is not an approved
experimental specification, and none of its parameter values override
`AGENTS.md`, `docs/decisions/`, or an experiment configuration.

The source studies Brazilian equities, while this repository studies Binance
spot cryptocurrencies. Its procedures therefore require both methodological
review and domain adaptation before reuse.

## Source provenance and review scope

- Author: Ercilene Micaela Brito da Silva.
- Institution: Centro Federal de Educacao Tecnologica de Minas Gerais.
- Program: Master's Program in Administration.
- Dissertation title in the source: *Tomada de decisao em selecao de portfolio
  de acoes do Ibovespa com o uso de machine learning*.
- Year: 2026.
- Reviewed source file: `dissertacao-mestrado-erci.docx`.
- Source SHA-256:
  `be3b2e8debe8c52b1d7ac8cc3ab75ae23f284064142c96627b1c614c12e7f014`.
- Reviewed chapter: Chapter 3, Methodology, source pages 32 through 46.
- Review date: 2026-09-29.

The chapter was reviewed from extracted text and rendered pages. The source
contains visible colored highlighting but no Word comments or tracked changes.
The highlighting was treated as source markup, not as an instruction to this
repository. Descriptive statements in the dissertation were also treated as
claims about that study rather than instructions for our experiment.

## Research design

The dissertation characterizes the study as quantitative, descriptive, and
ex-post-facto. It uses historical secondary data to evaluate a decision-support
process with two main stages:

1. supervised models classify whether each asset is likely to reach a return
   target within a fixed holding window;
2. portfolio rules allocate capital among assets with positive signals.

The complete process is:

1. assemble the historical investable universe;
2. clean and temporally align daily OHLCV series;
3. construct entry, exit, maximum-price, and realized-result variables;
4. create binary targets for three return thresholds;
5. calculate 22 price and technical-indicator features;
6. remove nearly constant and highly correlated features;
7. scale the retained features;
8. train three classifiers with rolling windows and tuned hyperparameters;
9. generate individual and combined classification signals;
10. form portfolios from positive signals;
11. allocate capital using equal weights, maximum Sharpe, or minimum variance;
12. build capital series and compare them with market and random benchmarks;
13. analyze return, risk, consistency, portfolio size, and operational activity;
14. repeat one selected configuration without feature selection as a
    sensitivity analysis.

## Data and investable universe

The study uses daily adjusted open, high, low, close, and volume observations
from January 2005 through April 2025. The investable universe is intended to
follow the companies that belonged to the Ibovespa in each analyzed month,
rather than using only the index membership observed at the end of the sample.
The methodology chapter does not identify the price-data provider or fully
document how historical index membership was sourced and dated.

The preprocessing procedure creates a common trading calendar containing each
date on which at least one asset traded. Every asset is aligned to this union
calendar. Missing values are filled with the last available observation using
forward fill. The chapter does not specify:

- which fields are filled, especially whether volume is carried forward;
- how dates before listing and after delisting are distinguished from isolated
  missing observations;
- whether a maximum gap length is enforced;
- how adjusted OHLC values are made internally consistent after corporate
  actions;
- whether the historical constituents are effective at the start or end of a
  month.

## Decision variables and target construction

For a decision associated with observation `t`, the dissertation defines:

- `purchase_price(t)` as the next trading day's opening price;
- `maximum_reached(t)` as the highest price during the holding window;
- `sale_price(t)` as the first target price reached, or the closing price on
  the last day of the holding window when the target is not reached;
- `realized_result(t)` as the return from the purchase price to the sale price.

The holding window is four trading days. Three targets are tested independently:
1%, 1.5%, and 2%. For threshold `q`, the binary label is conceptually:

```text
y_q(t) = 1 if max(high_{t+1}, ..., high_{t+4})
              >= open_{t+1} * (1 + q)
         0 otherwise
```

When the threshold is reached, the source assigns the target price as the exit
price. Otherwise, it exits at the close of the fourth day. The realized simple
return is therefore conceptually:

```text
realized_return_q(t) = sale_price_q(t) / open_{t+1} - 1
```

These variables use future observations and belong only to label construction
and backtest accounting. They cannot be features available at `t`.

The chapter does not define how to handle gaps through the target, the ordering
of intraday high and low values, suspended trading during the window, an
incomplete final window, transaction costs, taxes, or slippage.

## Feature construction

The study calculates 22 features adapted from Paiva et al. (2019). With `i`
representing the current observation and `ln` the natural logarithm, the first
15 features are:

| ID | Definition |
|---|---|
| `r1` | `ln(close_i / close_{i-1})` |
| `r2` | `ln(close_{i-1} / close_{i-2})` |
| `r3` | `ln(close_{i-2} / close_{i-3})` |
| `r4` | `ln(close_{i-3} / close_{i-4})` |
| `r5` | `ln(high_i / open_i)` |
| `r6` | `ln(high_i / open_{i-1})` |
| `r7` | `ln(high_i / open_{i-2})` |
| `r8` | `ln(high_i / open_{i-3})` |
| `r9` | `ln(high_{i-1} / open_{i-1})` |
| `r10` | `ln(high_{i-2} / open_{i-2})` |
| `r11` | `ln(high_{i-3} / open_{i-3})` |
| `r12` | `ln(low_i / open_i)` |
| `r13` | `ln(low_{i-1} / open_{i-1})` |
| `r14` | `ln(low_{i-2} / open_{i-2})` |
| `r15` | `ln(low_{i-3} / open_{i-3})` |

The remaining features are technical indicators calculated with TA-Lib:

| ID | Definition in the source |
|---|---|
| `r16` | Momentum on close, period 10 |
| `r17` | Relative Strength Index on close, period 14 |
| `r18` | Parabolic SAR on high and low, acceleration 0 and maximum 0 |
| `r19` | Average True Range on high, low, and close, period 14 |
| `r20` | True Range on high, low, and close |
| `r21` | Chaikin Accumulation Distribution Line on high, low, close, and volume |
| `r22` | On-Balance Volume on close and volume |

The unusual definitions of `r6` through `r8` use the current high with lagged
open prices and should not be silently replaced by matched-lag ratios. The
printed Parabolic SAR parameters of zero also require verification because they
may be incomplete or invalid for the intended implementation.

## Feature selection and scaling

Feature selection has two sequential filters:

1. `VarianceThreshold` from scikit-learn removes features with variance below
   a threshold of `0.01`;
2. `DropCorrelatedFeatures` from Feature-engine removes features whose
   correlation exceeds `0.8`.

For each combination of year and training-window length, the filters are fitted
on the first iteration and the selected feature set is reused for the other
predictions in that year and window configuration. The source presents this as
a compromise between a stable annual input set and computational cost.

Before each training step, `StandardScaler` transforms the selected features to
zero mean and unit variance based on the training data. The fitted transformation
is then applied to the following observation.

The chapter does not state whether feature selection is fitted separately for
each asset and target, how correlation ties determine which feature is removed,
or whether the scaler and filters are included inside every hyperparameter
validation fold. These details affect both reproducibility and leakage control.

## Model training and rolling prediction

The experiment trains three supervised classifiers:

- artificial neural network;
- Random Forest;
- Support Vector Classifier.

Each classifier is evaluated with rolling training windows of 60, 75, and 90
daily observations. At every iteration, the model trains on the selected window
and predicts the immediately following observation. The window then advances
by one observation, dropping the oldest record and adding the newest available
record.

Hyperparameters are selected with `GridSearchCV`, three-fold cross-validation,
and training accuracy as the optimization score. The search is performed for
each asset, classifier, year, and training-window length. The chosen parameters
are reused for equivalent iterations during that year. The chapter does not
report the search spaces, estimator seeds, class-weight treatment, or the exact
cross-validation splitter.

The dissertation records precision in two forms:

- in-sample precision from the training context;
- out-of-sample precision from the recursive one-step-ahead predictions.

The results are aggregated by classifier and target. Precision is emphasized
because a false positive creates a purchase signal for an asset that does not
reach the target.

## Signal construction

For every asset, target, and date, the three classifiers and three training
windows produce nine individual binary predictions. The study then adds three
combined signals:

| Signal | Rule |
|---|---|
| Ensemble 1, originally total ensemble | Positive only when all classifier-window predictions are positive |
| Ensemble 2, originally partial ensemble | Positive with a minimum majority across all predictions and at least one positive prediction from each classifier family |
| Ensemble 3, originally precision ensemble | Use the prediction from the classifier-window configuration with the highest recent in-sample precision |

The source does not express the partial-ensemble majority as an explicit count.
With nine component predictions, a strict majority would normally mean at least
five, but that value must be confirmed rather than inferred.

For Ensemble 3, ties in maximum in-sample precision are resolved by comparing
the tied predictions. A common prediction becomes the final signal. If the tied
predictions disagree, the record is not consolidated as a positive signal.

## Portfolio formation and allocation

Assets with positive signals form the eligible set for each date. Three
allocation rules are applied:

| Allocation | Procedure |
|---|---|
| Equal weight | Allocate `1/N` to each of the `N` eligible assets |
| Maximum Sharpe | Maximize the estimated return-to-risk ratio |
| Minimum variance | Minimize estimated portfolio variance without explicitly maximizing return |

Both optimized portfolios constrain each weight to the interval `[0, 1]`, so
short sales are prohibited. The chapter appears to assume full investment but
does not explicitly state the sum-of-weights constraint or define a cash asset.

The optimization inputs use a rolling history of 60 closing-price observations.
Maximum Sharpe uses historical mean returns and the covariance matrix; minimum
variance uses the covariance matrix from the same window. Portfolio eligibility
uses the prior period's signals, and parameter estimates use information
available before the allocation decision.

A position-locking rule prevents a new entry in an asset while its earlier
position remains open, either until it reaches the target or until its four-day
holding window ends.

The following fallbacks are described:

- no eligible assets: no portfolio is formed at that instant;
- one eligible asset: assign weight 1 to that asset;
- insufficient history or optimizer failure: allocate equal weights among the
  available assets.

The source does not define the return earned when no portfolio is formed, how
capital is reserved among positions with different exit dates, whether weights
are rebalanced daily, or how turnover and overlapping positions across assets
affect the capital series.

## Experimental combinations and capital series

The methodology reports 108 capital series. The internally consistent count is:

```text
(9 individual classifier-window signals + 3 ensemble signals)
* 3 return targets
* 3 allocation rules
= 108 capital series
```

The prose instead attributes 108 series to three classifiers, three windows,
three targets, and three allocation rules. That multiplication produces 81,
so the prose omits the ensemble dimension even though the reported total is
consistent when the three ensembles are included.

## Evaluation and comparison

### Classification evaluation

The chapter focuses on precision for both training and recursive out-of-sample
predictions. It does not specify recall, F1-score, ROC-AUC, class prevalence,
confusion matrices, probability calibration, or uncertainty intervals.

### Strategy ranking

All capital series are ranked by terminal accumulated capital over the complete
study period. The six highest-ranked strategies form the `top 6`, which receives
the detailed downstream analysis.

### Descriptive and operational analysis

For the top six strategies, the study reports:

- total transactions and average transactions per day;
- mean, standard deviation, coefficient of variation, minimum, and maximum of
  daily returns;
- portfolio cardinality and its monthly evolution;
- monthly returns and accumulated capital curves;
- monthly and annual consistency;
- months with non-negative and negative returns;
- drawdown magnitude, timing, duration, and recovery.

### Benchmarks and statistical comparison

The comparison uses:

- CDI as a conservative investment reference;
- Ibovespa as a Brazilian equity-market proxy;
- a random asset-selection strategy as a non-predictive baseline.

Monthly spread is the strategy return minus the corresponding CDI or Ibovespa
return, expressed in percentage points. A Friedman test compares the monthly
returns of the top six strategies as related samples, using a 5% significance
level. The null hypothesis states that the strategies do not differ; the
alternative states that at least one differs.

The random-selection mechanism, number of repetitions, random seed, allocation
rule, and uncertainty around the random baseline are not defined in the
methodology chapter.

### Sensitivity analysis

One selected configuration is rerun with and without feature selection while
keeping the classifier, training window, target, training process, and other
settings fixed. The comparison is performed for minimum-variance and equal-weight
allocation. Terminal capital and the percentage difference between the two
versions are used to describe sensitivity to feature selection.

## Temporal interpretation

The intended event sequence can be reconstructed as follows:

1. use information available through observation `t` to calculate features;
2. train or update the model using an earlier rolling window;
3. issue a binary prediction for the next decision;
4. enter at the opening price of `t+1`;
5. observe the next four daily highs to determine whether the target is reached;
6. exit at the target price on the first success or at the close of the fourth
   day otherwise;
7. prevent another entry in the same asset until that position has exited;
8. use signals known in the prior period and historical estimates to construct
   the next portfolio.

This ordering is useful, but the chapter does not state a purge or embargo rule.
Because each label uses four future observations, the last labeled training
records can overlap the prediction or evaluation horizon unless they are
explicitly removed.

## Methodological risks and unresolved details

The following issues should be treated as cautions, not copied as defaults:

1. **Cross-validation may violate temporal order.** `GridSearchCV` with three
   folds is named, but the time-aware splitter is not. Ordinary folds can train
   on observations later than their validation observations.
2. **Target overlap is not purged.** Four-day future labels require a boundary
   gap when a training label would use prices from the evaluation period.
3. **Preprocessing placement is incomplete.** Scaling and feature selection
   must be fitted within each valid training fold, not before cross-validation.
4. **Annual parameter reuse is underspecified.** The exact fitting sample and
   whether reuse is separated by asset and target are unclear.
5. **Forward fill can create artificial market observations.** Carrying prices
   or volume across non-trading, pre-listing, suspended, or delisted periods can
   distort features, covariance, labels, and eligibility.
6. **The universe can still contain survivorship bias.** The conclusion itself
   acknowledges survivorship bias, despite the intended use of historical
   Ibovespa membership.
7. **The execution model is optimistic.** Exiting exactly at a target inferred
   from the daily high omits gaps, intraday path ambiguity, liquidity, slippage,
   fees, and taxes.
8. **Portfolio accounting is incomplete.** Cash behavior, simultaneous
   positions, capital reservation, rebalance timing, turnover, and failed-order
   behavior are not fully specified.
9. **Maximum Sharpe is incomplete.** The risk-free rate, return convention,
   annualization, covariance estimator, numerical solver, and convergence
   tolerances are not stated.
10. **The final test set is not separated from strategy selection.** Ranking all
    strategies by full-period terminal capital and then analyzing the top six on
    that same period creates selection and multiple-testing bias.
11. **The Friedman test is post-selection.** Its nominal 5% level does not
    account for choosing the six strategies because they performed best on the
    same returns, and no post-hoc procedure is specified.
12. **The random baseline is not reproducible.** Its selection distribution,
    repetition count, seed, and confidence interval are missing.
13. **The reported series count is explained inconsistently.** The stated total
    of 108 requires the three ensembles, which are absent from the prose's
    multiplication.
14. **The sliding-window figure and daily procedure are not fully reconciled.**
    The figure shows 122 windows across the period but does not explain how that
    number relates to one-step daily windows of 60, 75, and 90 observations.
15. **Some feature definitions require confirmation.** The lag structure of
    `r6` through `r8` and the zero Parabolic SAR parameters may be intentional,
    transcription artifacts, or implementation errors.
16. **The coefficient of variation can be unstable.** Daily mean returns near
    zero make this ratio very large or difficult to interpret.

## Relevance to the cryptocurrency experiment

### Ideas that can serve as design references

- separate asset selection from capital allocation;
- preserve the timestamp sequence from feature availability through execution
  and exit;
- use rolling or expanding out-of-sample evaluation rather than random splits;
- fit feature selection, scaling, tuning, expected returns, and covariance only
  on temporally valid training data;
- compare equal weighting with an approved Markowitz formulation;
- define explicit fallbacks for empty sets, one asset, insufficient history,
  and optimizer failure;
- report classification performance separately from financial performance;
- include non-predictive baselines and controlled ablation studies;
- analyze portfolio cardinality, turnover, consistency, and drawdown in addition
  to terminal return.

### Elements that require cryptocurrency-specific adaptation

- replace the Ibovespa constituent history with timestamp-valid Binance symbol
  eligibility and listing rules;
- replace the equity trading calendar with continuous UTC cryptocurrency
  candles and preserve actual missing intervals rather than forward-filling
  them by default;
- use Binance spot OHLCV fields rather than adjusted equity prices;
- define target and holding periods in candles for the approved interval;
- model fees, slippage, liquidity, minimum order sizes, and exchange filters;
- define how simultaneous positions and continuously available trading affect
  capital allocation and rebalancing;
- choose cryptocurrency-appropriate benchmarks and risk-free-rate treatment.

### Parameters that this reference does not approve

The following values belong to the dissertation and must not be imported into
this repository without an explicit methodology decision:

- targets of 1%, 1.5%, and 2%;
- a four-day holding window;
- training windows of 60, 75, and 90 observations;
- a 60-observation Markowitz estimation window;
- variance and correlation thresholds of `0.01` and `0.8`;
- artificial neural network and Random Forest classifiers;
- three-fold cross-validation and accuracy-based tuning;
- any ensemble rule;
- maximum-Sharpe optimization;
- long-only bounds, full-investment behavior, and all fallback rules;
- ranking by terminal capital and selecting a top six;
- the CDI, Ibovespa, and random-selection benchmarks;
- the feature-selection sensitivity configuration.

## Decisions required before reuse

An adaptation should not be implemented until the researcher approves the
items required by `AGENTS.md`, including the asset universe, sample dates,
candle interval, holding window, temporal splits, purge gap, feature-selection
method, SVM tuning design, portfolio objective and constraints, estimators,
rebalance timing, empty-signal behavior, trading frictions, benchmarks, and
missing-data treatment. Each approved choice must be recorded in
`docs/decisions/` and in the relevant experiment configuration.
