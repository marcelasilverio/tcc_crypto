---
type: Methodology Decision
title: CSV artifact organization by execution
description: Approved shallow data and result layout using CSV tables without parallel Excel exports, with preserved historical evidence.
tags: [artifacts, csv, organization, reproducibility, migration]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-31T12:00:00Z" }
sources:
  - id: researcher-organization
    resource: "source-artifact:researcher-conversation-2026-10-31"
    title: Researcher approval of simplified folders and CSV-only tabular artifacts
  - id: current-paths
    resource: ../../src/tcc_crypto/paths.py
    title: Active artifact path implementation
---

# CSV artifact organization by execution

## Decision and scope

The researcher approved simplifying data/result folders and retaining CSV as
the sole tabular artifact format. Do not generate both Excel workbooks and CSV
versions of the same results. This applies to new collection, preparation,
exploratory and experiment tabular outputs, including audit tables. CSV files
are the tables actually consumed by the experiment and inspected by the user.

The [implementation guide](daily-code-organization.md) records the implemented
layout and historical migration. Existing raw data and historical Excel files
are preserved byte-for-byte. New derived tables use CSV only.

## Directory layout

Group artifacts by execution rather than repeating source/market, stage, coin,
window and target as directory levels. Keep identifiers in columns or filenames
where possible. Preserve the distinction between independent executions.

```text
data/
  raw/                              Existing immutable collection layout
  processed/
    daily_<execution_id>/           Treated candles, features, targets, datasets
  exploration/
    <analysis_execution>/           Exploratory CSV tables
outputs/
  experiments/
    daily_<execution_id>/           Main experiment CSVs
      figures/                      Figures when needed
      audit/                        Detailed search and provenance evidence
  exploration/
    <analysis_execution>/           Exploratory figures and execution metadata
  reports/                          Human-readable research reports
  archive/
    <historical_execution>/         Previous protocol results and migration evidence
```

Angle-bracket components are placeholders, not literal directory names. Resolve
all actual paths in paths.py. Use the same execution identifier across processed
data and corresponding outputs; retain the scientific context identifier in
metadata. Do not share mutable outputs between incompatible contexts.

Keep the existing raw collection hierarchy initially because it supports
collection/resume and immutability. New exploratory tables belong under data/exploration. Historical exploratory
tables are preserved under outputs/archive and mapped by the migration manifest. Avoid coin, target, window, grid-search and final-evaluation
subdirectories for the revised experiment. Optional folders are created only
when artifacts are written. Do not retain the empty functional distinction
between output and outputs for new results; outputs is the result root.

## CSV files for direct consultation

The following filenames are a concrete proposed naming scheme; the approved
requirements are CSV-only tables, a shallow layout and clear responsibilities.

| File | Purpose |
| --- | --- |
| availability.csv | Every study calendar day by asset; 1 for valid complete raw candles, otherwise 0 |
| treatment.csv | Missing/invalid dates, reasons, carried-forward source dates and treatment status |
| metrics.csv | Metrics per symbol, target, window, block and in/out-of-sample role, with winning parameters and status |
| feature_selection.csv | Feature-level variance, selection/discard decision, reason and relevant correlation |
| predictions_in_sample.csv | Daily binary training predictions |
| actuals_in_sample.csv | Corresponding observed binary targets |
| predictions_out_of_sample.csv | Daily binary validation predictions |
| actuals_out_of_sample.csv | Corresponding observed binary targets |

A CSV has one table and no worksheet tabs. Do not recreate workbook sheets as a
large collection of deeply nested folders. Use identifiers and filters in the
main tables instead of creating a file for every coin, block or candidate.

Binary matrices retain dates as rows and cryptocurrencies as value columns.
Identify target, window size and sample role explicitly. Asset-specific block
boundaries require an auditable mapping from each cell to its fitted block;
keep that mapping in audit records. Preserve all identities when a day appears
in different experiments. Do not collapse distinct predictions or replace
unavailable labels/predictions with zero. The raw availability matrix's zeros
have a different meaning from valid negative classification labels.

Detailed candidate/fold scores, full correlation evidence, exception records,
scaler parameters and execution mappings belong in audit, not separate Excel
exports. Main files can be views of computed evidence but must not introduce a
second calculation of metrics, features or model results.

## Persistence and reproducibility

CSV is a format decision, not a requirement to flatten all experiment data into
one enormous file. Prepared data may use clear names such as
BTCUSDT_features.csv or consolidated tables with an explicit symbol column.
Choose practical partitions without reintroducing directories per combination.
Existing compressed CSV (.csv.gz) remains CSV storage, not an additional
spreadsheet format; choose one representation per table rather than writing
both compressed and uncompressed copies. No new compression policy is imposed.

Preserve UTC dates, column order, numeric precision, nullable values, imputation
markers and explicit schemas. CSV does not preserve types like a typed table;
readers must restore and validate them. Define encoding, missing-value convention
and schema in the implementation contract and test round trips.

JSON remains permitted for configuration snapshots, schemas, source checksums,
package versions, execution/revision identifiers and metadata. This is not a
second tabular export. Figures and research reports remain separate non-tabular
artifacts when useful. Do not retain workbook-generation packets as a new stage.

## Migration requirements

- Inventory existing artifacts and retain their original bytes and provenance.
- Keep prior scientific protocols distinct from the revised block experiment.
- Map old paths to new paths with checksums and execution/context identifiers.
- Reduce redundant historical nesting rather than wrapping the complete old
  tree in another folder. Resolve filename collisions without overwriting.
- Update paths.py, loaders, writers, collection resume paths where applicable,
  configurations, commands, notebooks, documentation and path/schema tests
  together. Merely moving folders would recreate old paths on the next run.
- Keep valid saved upstream inputs usable without automatic recollection,
  feature recomputation or model fitting. Existing overwrite rules remain.
- Preserve the complete-project publishing policy; historical research evidence
  is not disposable merely because the new exporter no longer creates Excel.

This decision changes storage and consultation, not the scientific calculations.
