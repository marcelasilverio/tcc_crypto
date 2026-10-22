---
type: Experiment Report
title: Exploratory refactor and historical artifact migration
description: Implementation boundaries, correlation-universe correction, and provenance rules for the exploratory pipeline refactor.
tags: [refactoring, exploratory-analysis, reproducibility, migration]
status: draft
authority: generated-evidence
generated: { by: "process:exploratory-refactor", at: "2026-10-22T00:00:00Z" }
sources:
  - id: implementation-guide
    resource: ../../src/tcc_crypto/EXPLORATION.md
    title: Exploratory execution and migration guide
  - id: approved-open-correlation
    resource: ../decisions/hourly-open-price-correlation.md
    title: Approved hourly open-price correlation
  - id: approved-return-correlation
    resource: ../decisions/hourly-high-open-return-correlation.md
    title: Approved hourly high-to-open return correlation
---

# Exploratory refactor and historical artifact migration

The refactor moves collection, calculations, visualization, exports and notebook
orchestration into separate reusable functions. Every notebook remains an
interactive sequence of explicit calls and result displays. Excel generation
uses Python and preserves native charts in the daily descriptive workbooks.

## Correlation-universe correction

The approved correlations use the initial 30-pair candidate universe. The former
notebooks read the mutable collection JSON, which was later expanded to 40 pairs.
Their defaults therefore no longer represented the explicitly approved universe.
The researcher confirmed restoration of the 30 pairs during the refactor plan.
Dedicated configurations now list those exact pairs. The original 2021 eligibility
cutoff, Pearson correlation and pairwise-complete UTC alignment remain unchanged.
This is a specification correction, not an equivalence claim against coefficients
previously calculated with the expanded universe.

## Historical evidence

Recognized historical artifacts are relocated with their original filenames and
bytes. A local manifest at `outputs/migrations/exploration-v1.json` records original
and destination paths, SHA-256 and per-file migration status. Historical report
links and metadata may contain original paths; the manifest is the translation
map. Relocation does not imply that legacy outputs satisfy new stage schemas.
Canonical raw data and unrelated personal documents are excluded.

No methodological approval or human verification record is created by this report.
The refactor does not implement portfolio construction, backtesting or final
walk-forward evaluation. Parabolic SAR remains subject to its recorded caveat.
