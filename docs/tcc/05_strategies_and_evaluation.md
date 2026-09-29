---
type: Research Context
title: Strategies and evaluation
description: Proposed portfolio strategies, evaluation metrics, and backtest timing requirements.
tags: [tcc-i, strategies, evaluation, backtesting]
status: stable
authority: research-context
generated: { by: "process:okf-migration", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:marcela-prata-silverio", at: "2026-09-29T10:16:31Z" }
sources:
  - id: tcc-i-manuscript
    resource: "source-artifact:tcc-corrigido-final.pdf"
    title: Machine Learning Applied to Cryptocurrency Portfolio Selection
    author: "human:marcela-prata-silverio"
    checksum: "sha256:f90b1cc54bc105e4eab96d8aed4ff7f9f16eb9545566ccd820fb7c4144c1da7a"
---

# Strategies and evaluation

## Required strategy comparison

The manuscript proposes five strategies. Their roles should remain distinct so
that selection and allocation effects can be interpreted separately.

| Strategy | Asset selection | Weight allocation | Interpretive purpose |
|---|---|---|---|
| Buy and Hold | Approved fixed universe | Initial allocation, then no rebalancing | Passive reference |
| SVM + 1/N | Positive SVM signals | Equal weights | Isolate the value of SVM selection |
| Naive + 1/N | Naive rule | Equal weights | Simple non-ML reference |
| Naive + Markowitz | Naive rule | Mean-variance weights | Isolate the value of optimization |
| SVM + Markowitz | Positive SVM signals | Mean-variance weights | Evaluate the combined proposal |

`1/N` means equal capital allocation across the `N` selected assets.

## Classification evaluation

The TCC I experiment diagram and methodology mention:

- accuracy;
- precision;
- recall;
- F1-score;
- ROC-AUC.

Metrics must be reported per target threshold and over temporally valid
out-of-sample predictions. Class balance and the confusion matrix should be
retained because accuracy alone may be misleading when positive targets are
rare.

## Financial evaluation

The prose explicitly mentions cumulative return and average return. The final
metric set remains unresolved. Any implemented financial metric must define:

- input return convention;
- observation and rebalance frequency;
- annualization factor, if used;
- transaction costs and slippage;
- risk-free rate, if required;
- missing-observation treatment.

Classification metrics and financial metrics must be stored and discussed
separately.

## Backtest timing

A valid backtest must distinguish at least:

1. the last timestamp used for model fitting;
2. the timestamp at which features and signals become available;
3. the execution price and timestamp;
4. the holding interval;
5. the exit or rebalance timestamp.

The manuscript proposes the next candle's open as the purchase price. The
implementation must enforce this delay rather than entering at a price already
used to create the signal.

## Unresolved baseline behavior

The source describes the naive strategies as non-predictive but does not define
how they choose eligible assets. The following must also be approved:

- behavior when the SVM selects no assets;
- behavior when too few assets are selected for optimization;
- whether Buy and Hold is equal-weighted initially;
- portfolio rebalance frequency;
- whether partial investment or a cash position is permitted;
- long-only, leverage, short-sale, and concentration constraints.

## Source coverage

Portfolio formation is described on PDF page 57. Strategies and evaluation are
described on PDF pages 58-60.
