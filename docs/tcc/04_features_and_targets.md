---
type: Research Context
title: Features and targets
description: Proposed feature definitions, decision variables, and binary return targets.
tags: [tcc-i, features, targets, technical-indicators]
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

# Features and targets

## Feature set proposed in TCC I

The manuscript adapts the feature design of Silva (2025), drawing on Paiva et
al. (2019). Subscript `t` denotes the decision candle and `ln` denotes the
natural logarithm.

| ID | Definition |
|---|---|
| `r1` | `ln(close_t / close_{t-1})` |
| `r2` | `ln(close_{t-1} / close_{t-2})` |
| `r3` | `ln(close_{t-2} / close_{t-3})` |
| `r4` | `ln(close_{t-3} / close_{t-4})` |
| `r5` | `ln(high_t / open_t)` |
| `r6` | `ln(high_t / open_{t-1})` |
| `r7` | `ln(high_t / open_{t-2})` |
| `r8` | `ln(high_t / open_{t-3})` |
| `r9` | `ln(high_{t-1} / open_{t-1})` |
| `r10` | `ln(high_{t-2} / open_{t-2})` |
| `r11` | `ln(high_{t-3} / open_{t-3})` |
| `r12` | `ln(low_t / open_t)` |
| `r13` | `ln(low_{t-1} / open_{t-1})` |
| `r14` | `ln(low_{t-2} / open_{t-2})` |
| `r15` | `ln(low_{t-3} / open_{t-3})` |
| `r16` | Momentum on close, period 10 |
| `r17` | Relative Strength Index on close, period 14 |
| `r18` | Parabolic SAR on high and low; parameters unresolved |
| `r19` | Average True Range on high, low, and close, period 14 |
| `r20` | True Range on high, low, and close |
| `r21` | Chaikin Accumulation/Distribution Line on high, low, close, and volume |
| `r22` | On-Balance Volume on close and volume |

The formulas above preserve the table as written. In particular, `r6` through
`r8` use the current high with earlier opens, while `r9` through `r11` use
matched lags. Agents must test these formulas against manually calculated
examples and must not silently “correct” them.

## Decision variables proposed in TCC I

For a decision made after candle `t`:

- **purchase price:** the open of the next candle;
- **maximum reached:** the highest price inside the holding window;
- **sale price:** the price associated with reaching the return target, or the
  closing price at the end of the window if the target is not reached;
- **realized result:** the return implied by the sale and purchase prices.

These are future-dependent outcome variables. They belong to target generation
and backtest accounting, not to the features available at time `t`.

## Binary targets

The manuscript proposes three independent thresholds: 3%, 4%, and 5%. For
threshold `q`, the conceptual target is:

```text
y_q(t) = 1 if the eligible future price reaches purchase_price(t) * (1 + q)
         within the approved holding window;
         0 otherwise.
```

The precise convention for a threshold reached within a candle, the sale price,
fees, and the final observation of an incomplete window must be explicitly
defined and tested before implementation.

## Feature selection and scaling

The source proposes feature selection before SVM training to reduce redundancy,
noise, and overfitting. It does not select a feature-selection algorithm.
Selection and scaling must be fitted independently inside each training window
and then applied unchanged to validation and test observations.

## Important unresolved details

- TCC I mentions a **proposed** four-day holding window but says it may change.
  `AGENTS.md` therefore correctly keeps the exact holding window unresolved.
- The source table prints Parabolic SAR acceleration and maximum as zero. Those
  values are likely incomplete or erroneous and require explicit confirmation.
- The candle interval is unresolved, so a period of 10 or 14 means observations,
  not automatically days.
- Indicator warm-up behavior and missing-value treatment are unresolved.

## Source coverage

Decision variables and proposed thresholds are described on PDF pages 54-55.
The 22-feature table and feature-selection discussion appear on PDF pages 55-57.
