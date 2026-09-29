---
type: Research Context
title: Experimental methodology
description: Proposed experimental pipeline and temporal safeguards from the TCC I manuscript.
tags: [tcc-i, methodology, temporal-validation, reproducibility]
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

# Experimental methodology

## Proposed pipeline

The TCC I experiment follows this conceptual sequence:

1. collect historical cryptocurrency market data;
2. standardize, clean, validate, and align observations;
3. calculate price transformations and technical indicators;
4. construct binary targets for multiple return thresholds;
5. select relevant features;
6. normalize features;
7. train and evaluate an SVM using temporal windows;
8. use positive classifications to define portfolio candidates;
9. assign capital using equal weights or Markowitz optimization;
10. backtest the strategies;
11. evaluate classification and financial performance separately.

This sequence is conceptual. Concrete parameters must come from approved
methodology decisions and experiment configuration.

## Data source

The proposed source is the public Binance Spot API, using `/api/v3/klines`.
Each kline response is a positional array containing timestamps, OHLC prices,
volume, and other exchange fields. Collection must be paginated because the
endpoint limits records per request.

The manuscript identifies the following core observations:

- opening time;
- open price;
- high price;
- low price;
- close price;
- traded volume.

UTC is the canonical timezone. The source states that timestamps are expressed
in milliseconds. Repository safeguards additionally require schema validation,
timestamp uniqueness, chronological ordering, missing-interval checks, numeric
typing, and OHLC consistency.

## Temporal design

The manuscript proposes sliding windows so that older observations train the
model and newer observations evaluate it. Data must never be randomly shuffled.
For every window:

- feature selection is fitted on training data only;
- normalization is fitted on training data only;
- SVM hyperparameter tuning uses only temporally valid training and validation
  observations;
- target-horizon overlap is purged when it would expose future information;
- classification and portfolio weights use only information available at the
  decision timestamp.

The manuscript does not specify the training, validation, and test window
lengths. It also does not resolve whether the production experiment uses a
fixed-length rolling window or an expanding window.

## Portfolio construction

Positive SVM predictions form a candidate set. Portfolio weights are then
assigned either equally or by a mean-variance procedure based on historical
returns and a covariance matrix estimated inside the valid temporal window.
Future observations must not enter expected-return estimates, covariance
estimates, eligibility rules, or weights.

## Reproducibility requirements

Each implemented experiment must record at least:

- experiment identifier and execution timestamp;
- code revision;
- configuration and random seed;
- data range and asset universe;
- package versions;
- selected features and model parameters;
- portfolio objective and constraints;
- evaluation metrics and output locations.

## Source coverage

This document is based on the methodology on PDF pages 51-59, especially the
experiment diagram and data description on PDF pages 52-54. Temporal safeguards
also incorporate the stricter requirements already established in `AGENTS.md`.
