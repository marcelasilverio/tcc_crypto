# Documentation update log

## 2026-10-13

- **Temporal model selection**: Approved a two-level design with an inner
  three-split temporal grid search and a chronologically later, untouched final
  test evaluated one step at a time.
- **Conditional SVC grid**: Approved 186 compatible configurations over
  `kernel`, `C`, `gamma`, `degree`, `coef0`, and `class_weight`, evaluated
  independently for every target and 60-, 75-, and 90-day training window.
- **Preprocessing integrity**: Required feature selection and
  `StandardScaler` to be fitted inside each temporal training fold and refitted
  inside each final walk-forward training window.
- **Model selection and reporting**: Approved mean validation F1 as the primary
  grid-search criterion and required accuracy, precision, recall, F1, balanced
  accuracy, ROC-AUC, average precision, ROC curves, precision-recall curves,
  confusion matrices, dated predictions, and decision scores.
- **Final evaluation**: Required selected hyperparameters to remain frozen
  throughout the final test and required comparison with an always-negative
  classifier, a training-class-frequency baseline, and the default SVC.
- **Approved temporal boundaries**: Set development feature dates to
  2019-07-01 through 2024-12-30, reserved 2024-12-31 as a one-observation gap,
  and set final-test feature dates to 2025-01-01 through 2026-08-31, whose
  targets extend through 2026-09-01.
- **Validation blocks and gap**: Set each of the three inner validation blocks
  to 60 observations, capped inner training by the evaluated 60-, 75-, or
  90-day window, and applied a one-observation gap before validation and final
  prediction.
- **Tie breaking and baselines**: Approved deterministic F1 tie breaking by
  precision, F1 stability, ROC-AUC, model simplicity, lower `C`, and grid order;
  fixed the comparison baselines as constant-zero dummy, prior dummy, and
  default SVC.
- **Asset eligibility**: Approved separate searches by symbol, target, and
  window; a common minimum of 271 complete labeled rows; dynamic entry within
  the fixed ex-post 40-pair pool; an eligibility manifest; and exclusion of
  LUNAUSDT until economic continuity is resolved.
- **Development grid-search implementation**: Added a development-only temporal
  SVC search runner with strict configuration validation, per-combination
  eligibility, leakage-safe fold preprocessing, complete fold and candidate
  evidence, deterministic tie breaking, and reproducibility metadata.
- **BTCUSDT operational validation**: Completed all nine eligible searches and
  5,022 candidate-fold fits without fit errors. The last validation observation
  was 2024-12-30, and the run did not use final-test feature rows.
- **Development eligibility manifest**: Evaluated all 360 combinations from 40
  symbols, three targets, and three windows. Recorded 331 eligible searches, 36
  fully eligible symbols, seven eligible TRXUSDT searches, and zero eligible
  searches for NEIROUSDT, excluded LUNAUSDT, and ENAUSDT.
- **Grid-search walkthrough**: Added and executed a didactic notebook that
  exposes configuration validation, conditional-grid expansion, development
  data, eligibility, temporal splits, fold-local preprocessing, candidate
  metrics, deterministic ranking, selected configurations, and persisted
  reproducibility evidence for BTCUSDT.

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
  2%, 3%, and 4%.
- **Pilot scaling and execution**: Approved `StandardScaler` after feature
  selection, refitted on each training window only, and enabled the rolling
  default-SVC pilot with separate in-sample diagnostics and out-of-sample
  one-step prediction metrics.

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
