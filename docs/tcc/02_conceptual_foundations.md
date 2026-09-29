---
type: Research Context
title: Conceptual foundations
description: Cryptocurrency, portfolio-theory, and SVM foundations for the proposed experiment.
tags: [tcc-i, cryptocurrency, markowitz, svm]
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

# Conceptual foundations

## Cryptocurrency markets

The manuscript presents Bitcoin as the starting point for decentralized,
cryptographically validated value transfer and describes the later expansion
to smart-contract platforms, stablecoins, decentralized applications, and
other cryptoassets. It distinguishes centralized exchanges from decentralized
exchanges and uses Binance as the planned source of spot-market observations.

The market is treated as distinct from traditional asset markets because it:

- trades continuously;
- exhibits high volatility and abrupt regime changes;
- responds rapidly to information;
- includes heterogeneous assets with different economic and technical roles;
- is influenced by investor behavior, regulation, technology, and spillovers
  from other markets;
- changes composition over time, creating listing and survivorship concerns.

These characteristics justify explicit data-quality checks, temporal
validation, and cautious interpretation of historical patterns.

## Modern Portfolio Theory

The portfolio component follows Markowitz's mean-variance framework. The
central idea is that portfolio risk depends not only on each asset's variance
but also on covariance across assets. Diversification therefore concerns the
joint behavior of holdings rather than the isolated attractiveness of each
asset.

For weights `w` and covariance matrix `Sigma`, portfolio variance is:

```text
variance_p = sum_i sum_j w_i * w_j * covariance_ij
```

For expected-return vector `mu`, expected portfolio return is:

```text
return_p = sum_i w_i * mu_i
```

The efficient frontier contains portfolios that maximize expected return for
a given risk level or minimize risk for a given expected return. The manuscript
gives special attention to the global minimum-variance portfolio, but it also
uses broader risk-return language. The exact optimization objective and
constraints remain unresolved and must not be inferred from theory alone.

## Machine learning and SVM

The manuscript surveys supervised, unsupervised, and reinforcement learning,
then selects supervised binary classification for the experiment. A Support
Vector Machine finds a separating hyperplane with the largest feasible margin
between classes. Support vectors are the observations that define that margin.
Kernel functions can represent nonlinear boundaries in a transformed feature
space.

The proposed role of the SVM is deliberately narrow: classify whether an asset
is expected to reach a specified return threshold within an approved holding
window. A positive signal makes an asset eligible for portfolio construction;
it does not determine the asset's weight.

## Combined decision architecture

The research combines two distinct decisions:

1. **Asset selection:** the SVM filters the eligible universe using a binary
   return-target signal.
2. **Capital allocation:** equal weighting or a Markowitz model assigns weights
   to the selected assets.

Classification quality and portfolio performance must remain separate in both
implementation and reporting. Strong predictive metrics do not guarantee
strong financial performance, and portfolio performance does not by itself
validate the classifier.

## Source coverage

This document summarizes the theoretical framework on PDF pages 14-31. The
core portfolio formulation appears on PDF pages 23-28, and the SVM discussion
appears on PDF pages 29-31.
