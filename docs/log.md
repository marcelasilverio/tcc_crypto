# Documentation update log

## 2026-10-09

- **Experiment period**: Recorded `2019-07-01` as the effective start and June
  2019 as feature-only warm-up history.
- **Missing data**: Approved forward filling from the immediately preceding
  daily observation for gaps strictly inside an asset's observed span, while
  preserving raw data and leaving leading and terminal gaps unresolved.
- **Targets**: Recorded binary thresholds of 2%, 3%, and 4% and use of the
  existing daily `D0` high-to-open outcome.
- **Target timing**: Recorded the supervisor's confirmation that features at
  date `t` map to `D0` at `t + 1`, with purchase and exit both occurring in the
  `t + 1` candle. This supersedes the earlier four-observation holding-period
  note for this experiment.
- **SVM experiment**: Recorded the default-parameter single-asset pilot,
  subsequent full expansion, in-sample and out-of-sample evaluation, and the
  provisional grid-search design. Exact pilot bounds, search space, metric,
  and temporal validation boundaries remain pending.
- **Pilot scope**: Approved `BTCUSDT` from 2019-07-01 through 2019-12-31, with
  June 2019 used only as feature warm-up history.
- **Pilot dataset implementation**: Added the configured preparation pipeline
  for audited internal-gap filling, daily features, and next-day D0 targets at
  2%, 3%, and 4%. Model training remains pending approval of scaling and
  reporting conventions.

## 2026-10-03

- **External reference**: Documented the researcher-supplied Silva 2026 Python
  excerpt for feature engineering and feature selection as inspiration and
  formula-level implementation evidence.
- **Authority**: Classified the new concept as an `external-reference` in
  draft status; no parameters or procedures from the excerpt were recorded as
  approved methodology.
- **Provenance**: Recorded the two readable source filenames and their SHA-256
  checksums. Compiled Python cache files were excluded from the review scope.

## 2026-09-29

- **Migration**: Converted `docs/` into an Open Knowledge Format v0.2 bundle.
- **OKF version**: `0.2`.
- **Verification**: Recorded the repository owner's confirmation that all
  documents existing before the migration were human-reviewed.
- **Structure**: Split `methodology_decisions.md` into the following concepts:
  - `decisions/exploratory-usdt-pair-trade-count-collection.md`;
  - `decisions/hourly-data-collection-universe.md`;
  - `decisions/daily-data-collection.md`;
  - `decisions/hourly-open-price-correlation.md`;
  - `decisions/hourly-high-open-return-correlation.md`;
  - `decisions/hourly-price-descriptive-analysis.md`;
  - `decisions/hourly-market-activity-descriptive-analysis.md`;
  - `decisions/daily-price-volume-descriptive-analysis.md`.
- **Compatibility**: Retained `methodology_decisions.md` and `tcc/README.md` as
  deprecated redirects to their canonical indexes.
- **Preservation**: Kept the approved document bodies unchanged except for
  promoted section headings and updated internal paths required by the split.

### Complete path map

| Pre-migration path | Canonical path after migration |
| --- | --- |
| `methodology_decisions.md` | `decisions/exploratory-usdt-pair-trade-count-collection.md` |
| `methodology_decisions.md` | `decisions/hourly-data-collection-universe.md` |
| `methodology_decisions.md` | `decisions/daily-data-collection.md` |
| `methodology_decisions.md` | `decisions/hourly-open-price-correlation.md` |
| `methodology_decisions.md` | `decisions/hourly-high-open-return-correlation.md` |
| `methodology_decisions.md` | `decisions/hourly-price-descriptive-analysis.md` |
| `methodology_decisions.md` | `decisions/hourly-market-activity-descriptive-analysis.md` |
| `methodology_decisions.md` | `decisions/daily-price-volume-descriptive-analysis.md` |
| `tcc/README.md` | `tcc/index.md` |
| `tcc/01_research_scope.md` | `tcc/01_research_scope.md` |
| `tcc/02_conceptual_foundations.md` | `tcc/02_conceptual_foundations.md` |
| `tcc/03_experimental_methodology.md` | `tcc/03_experimental_methodology.md` |
| `tcc/04_features_and_targets.md` | `tcc/04_features_and_targets.md` |
| `tcc/05_strategies_and_evaluation.md` | `tcc/05_strategies_and_evaluation.md` |
| `tcc/06_literature_context.md` | `tcc/06_literature_context.md` |
| `tcc/07_open_decisions_and_source_caveats.md` | `tcc/07_open_decisions_and_source_caveats.md` |
| `references/erci_silva_2026_methodology.md` | `references/erci_silva_2026_methodology.md` |
| `reports/binance_hourly_collection_quality_report_2026-09-03.md` | `reports/binance_hourly_collection_quality_report_2026-09-03.md` |
| `reports/binance_hourly_collection_quality_report_expansion_pairs_2026-09-05.md` | `reports/binance_hourly_collection_quality_report_expansion_pairs_2026-09-05.md` |

The former `methodology_decisions.md` and `tcc/README.md` paths remain as
deprecated redirect concepts. Entries whose path did not change were enriched
with OKF metadata without changing their approved bodies.
