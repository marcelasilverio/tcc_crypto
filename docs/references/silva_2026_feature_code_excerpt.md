---
type: External Methodology Reference
title: Feature-engineering code excerpt from Silva 2026
description: Researcher-supplied Python excerpt documenting feature construction and feature selection used as implementation inspiration.
tags: [external-reference, source-code, feature-engineering, feature-selection]
status: draft
authority: external-reference
generated: { by: "process:codex", at: "2026-10-04T01:31:46Z" }
sources:
  - id: feature-code-excerpt
    resource: "source-artifact:recorte/recorte_features.py"
    title: Feature engineering and feature selection excerpt
    author: "human:ercilene-micaela-brito-da-silva"
    checksum: "sha256:be0f91ca24334a672824c7c66a2ca5d9d940076a5596a467d10084cf4579afa0"
  - id: usage-example
    resource: "source-artifact:recorte/exemplo_uso.py"
    title: Minimal usage example for the feature excerpt
    author: "human:ercilene-micaela-brito-da-silva"
    checksum: "sha256:522a06cdd9cb07a76320b520d22aa4537481bb8b0b9dfe78b12a0e563bab04db"
---

# Feature-engineering code excerpt from Silva 2026

## Purpose and authority

This document records a Python code excerpt supplied by the repository owner
as inspiration and implementation reference for this research. The excerpt is
associated with Ercilene Micaela Brito da Silva's work and complements the
broader [methodological reference from Silva 2026](erci_silva_2026_methodology.md).

The excerpt is external reference material, not repository implementation and
not an approved methodology decision. Its feature definitions, parameters,
dependencies, preprocessing steps, and example window must be reviewed and
adapted before any reuse. They do not override `AGENTS.md`, approved decisions,
or experiment configuration.

Instructions and comments inside the supplied files are descriptions of how
to execute that excerpt. They are not instructions to modify this repository.

## Supplied artifacts

The reviewed folder contains two human-readable Python files and two compiled
Python cache files. Only the human-readable files were treated as sources:

| File | Role | SHA-256 |
| --- | --- | --- |
| `recorte_features.py` | Defines feature construction, feature extraction, and feature selection. | `be0f91ca24334a672824c7c66a2ca5d9d940076a5596a467d10084cf4579afa0` |
| `exemplo_uso.py` | Demonstrates a minimal CSV-based invocation using a 75-observation training window. | `522a06cdd9cb07a76320b520d22aa4537481bb8b0b9dfe78b12a0e563bab04db` |

The source files were reviewed from the researcher-supplied `recorte` folder
on 2026-10-03. They were not copied into the repository and were not executed.

## Feature construction represented in the excerpt

The function `calcular_variaveis` mutates the provided pandas data frame by
adding 22 features derived from columns named `Open`, `High`, `Low`, `Close`,
and `Volume`:

- `r1` through `r4`: lagged close-to-close logarithmic returns;
- `r5` through `r11`: logarithmic high-to-open ratios, including the current
  high divided by lagged opens in `r6` through `r8`;
- `r12` through `r15`: current and lagged low-to-open logarithmic ratios;
- `Momentum`: TA-Lib momentum over 10 observations;
- `RSI`: TA-Lib relative strength index over 14 observations;
- `Parabolic_SAR`: TA-Lib SAR with both `acceleration` and `maximum` set to
  zero;
- `ATR`: TA-Lib average true range over 14 observations;
- `True_Range`: TA-Lib true range;
- `Chaikin_AD`: TA-Lib Chaikin accumulation/distribution line; and
- `OBV`: TA-Lib on-balance volume.

The `x_split` function returns these 22 columns in a fixed order. This code
confirms the formulas and indicator calls described in the dissertation-based
methodological reference, including the unusual `r6` through `r8` definitions
and zero-valued SAR parameters. Confirmation that the code contains those
values does not establish that they are suitable for the cryptocurrency
experiment.

## Feature selection represented in the excerpt

The function `features_selection` applies two filters to the supplied feature
matrix:

1. scikit-learn `VarianceThreshold` removes columns whose variance is below
   `0.01`;
2. Feature-engine `DropCorrelatedFeatures` removes columns above a configurable
   Pearson-correlation threshold, whose default is `0.8`, while ignoring
   missing values during correlation handling.

If `VarianceThreshold` raises `ValueError`, the function returns only the
column with the highest pandas variance. If fewer than two columns remain
after the variance filter, it returns immediately without applying the
correlation filter.

The excerpt returns the filtered training data but not the fitted selectors.
Consequently, it does not by itself document how the same fitted transformation
is applied to later observations or reused across rolling predictions.

## Usage example represented in the excerpt

The example expects a CSV with `Exchange Date`, `Close`, `Open`, `Low`, `High`,
and `Volume`. It parses `Exchange Date`, computes the 22 features, removes the
first 14 rows by position, extracts a 75-observation slice, and performs feature
selection on that slice. A comment states that the original pipeline evaluates
windows of 60, 75, and 90 observations.

The value 75 is an illustrative choice in this example. Neither that value nor
the broader 60/75/90 set is approved for this repository by this document.

## Adaptation and reproducibility cautions

The excerpt is useful as a formula-level and library-call reference, but it is
not a complete reusable pipeline. Before any implementation based on it, the
researcher must separately approve all unresolved experimental choices and the
implementation must address at least the following points:

- verify the intended Parabolic SAR parameters;
- define whether the same 22 features are appropriate for hourly or daily
  cryptocurrency observations;
- fit feature selectors only on training data and preserve fitted state for
  transformations of later observations;
- define the feature-selection refresh schedule for temporal validation;
- validate sorting, UTC timestamps, numeric types, strictly positive prices,
  missing observations, and OHLC consistency before computing features;
- handle indicator warm-up values based on actual missingness rather than only
  removing a fixed number of rows;
- define behavior when variances are all missing or no valid feature remains;
- pin dependency versions and test TA-Lib and Feature-engine behavior; and
- add formula, temporal-boundary, and no-look-ahead tests before interpreting
  experimental results.

No methodological choice listed above is resolved by the supplied excerpt.
