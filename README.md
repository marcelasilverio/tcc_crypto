# Cryptocurrency portfolio research

This repository supports undergraduate research on cryptocurrency portfolio
selection using Support Vector Machines and Markowitz mean-variance optimization.
The implemented workflows cover Binance Spot data collection, exploratory
analysis, daily feature and target construction, a rolling SVM pilot, and temporal
grid search and frozen-parameter final walk-forward classification. Portfolio
allocation and financial backtesting remain outside the current implementation.

## Setup

Use Python 3.11 or newer. From the repository root, install the package and its
development dependencies in your Python environment:

```sh
python -m pip install -e ".[dev]"
```

Experiment parameters live in `configs/`. The approved methodology is recorded in
[docs/decisions/](docs/decisions/index.md); start at [docs/index.md](docs/index.md)
for the documentation authority map and research context.

## Project structure

```text
configs/                   Collection and analysis configurations
src/tcc_crypto/
  collection/              Binance requests, pagination, checkpoints and raw storage
  data/                    Input loading, validation, gap treatment and dataset assembly
  features/                Price formulas, indicators and the 22-feature catalog
  targets/                 Next-day binary targets and exploratory future outcomes
  analysis/                Coverage, descriptive statistics, correlations and selection analysis
  modeling/                Training-only preprocessing, temporal splits, SVM and ranking
  visualization/           Figures and result presentation
  reporting/               Tables, Excel, provenance and artifact migration
  workflows/               Explicit stages shared by commands and notebooks
  paths.py                 Artifact constants and path resolution
  daily.py                 Daily pipeline command entrypoint
  explore.py               Exploratory analysis command entrypoint
  migrate.py               Historical artifact migration command entrypoint
notebooks/                 Step-by-step execution and result inspection
scripts/                   Documentation validation
tests/                     Automated tests and small reference fixtures
data/
  raw/                     Immutable source observations and collection evidence
  processed/               Derived tables and prepared datasets
  exploration/             Exploratory workbooks
outputs/                   Figures, classifier results and execution metadata
docs/                      Research context, approved decisions and reports
```

Reusable code belongs in its domain layer. The former flat compatibility modules
and forwarding scripts have been removed; import implementations directly from
the packages above. The root command modules coordinate execution through
`workflows/`.

## Daily research pipeline

**Collect → align internal gaps → calculate 22 features → construct targets →
assemble dataset → pilot or grid search → final walk-forward → inspect results.**

| Step | Implementation |
|---|---|
| Raw collection and resumption | [collection/pipeline.py](src/tcc_crypto/collection/pipeline.py) |
| Internal gaps and `is_imputed` | [data/gaps.py](src/tcc_crypto/data/gaps.py) |
| Explicit price formulas `r1`–`r15` | [features/price.py](src/tcc_crypto/features/price.py) |
| Technical indicators | [features/indicators.py](src/tcc_crypto/features/indicators.py) |
| Feature definitions and column order | [features/catalog.py](src/tcc_crypto/features/catalog.py) |
| Composition of the 22 features | [features/daily.py](src/tcc_crypto/features/daily.py) |
| Next-day D0 and 2%, 3%, 4% targets | [targets/daily.py](src/tcc_crypto/targets/daily.py) |
| Dataset assembly | [data/dataset.py](src/tcc_crypto/data/dataset.py) |
| Training-window selection and scaling | [modeling/preprocessing.py](src/tcc_crypto/modeling/preprocessing.py) |
| Rolling SVM pilot | [modeling/pilot.py](src/tcc_crypto/modeling/pilot.py) |
| Temporal grid search | [modeling/grid_search.py](src/tcc_crypto/modeling/grid_search.py) |
| Final walk-forward and baselines | [modeling/final_evaluation.py](src/tcc_crypto/modeling/final_evaluation.py) |

### Pilot

Display the resolved paths first. Collect or resume BTCUSDT observations, prepare
the pilot dataset, and then execute the classifier:

```sh
python -m tcc_crypto.daily paths --profile pilot
python -m tcc_crypto.daily collect --symbols BTCUSDT
python -m tcc_crypto.daily prepare --profile pilot
python -m tcc_crypto.daily pilot
```

`prepare` explicitly runs alignment, features, targets, and dataset assembly.
Those stages can also be executed separately:

```sh
python -m tcc_crypto.daily align --profile pilot
python -m tcc_crypto.daily features --profile pilot
python -m tcc_crypto.daily targets --profile pilot
python -m tcc_crypto.daily dataset --profile pilot
```

Each independent stage requires its upstream artifacts. Model commands require a
prepared dataset. Existing derived outputs require `--overwrite`; the collector
retains its checkpoint and existing-output validation behavior.

### Development grid search

Preparation and model search use the development profile:

```sh
python -m tcc_crypto.daily paths --profile development --symbols BTCUSDT
python -m tcc_crypto.daily prepare --profile development --symbols BTCUSDT
python -m tcc_crypto.daily grid-search --symbols BTCUSDT
```

BTCUSDT is the default development asset. Use `--all-symbols` explicitly for the
configured universe. `grid-search --eligibility-only` records eligibility from
prepared datasets without fitting candidates. See the
[daily execution guide](src/tcc_crypto/README.md) for configuration overrides,
temporal boundaries, and the complete command reference.

### Prepare the full experiment without training

The `experiment` profile prepares all configured assets from the approved
development start through the final-test feature boundary. With the current
configuration, feature dates span 2019-07-01 through 2026-08-31, with June 2019
warm-up and next-day target inputs through 2026-09-01. Later-listed assets start
after their observed history and indicator warm-up; no pre-listing data is created.

```sh
python -m tcc_crypto.daily paths --profile experiment --all-symbols
python -m tcc_crypto.daily prepare --profile experiment --all-symbols
```

This profile reads existing raw files and never collects or fits models. It uses
the separate `{experiment_id}_full_period` artifact context, preserves all 40
assets for inspection (including LUNAUSDT, which remains excluded from modeling),
and exports one `features_and_targets.xlsx` per asset. Its sheets contain aligned
data, features, targets, the joined dataset, definitions and a summary.
The complete dataset includes the development/test boundary gap for inspection;
it is not a combined training sample. Model commands reject this profile. The
development and final-test boundaries and existing modeling outputs are unchanged.

### Final classifier evaluation

After all development searches have completed, run the approved frozen-parameter
walk-forward evaluation on 2025-01-01 through 2026-08-31:

```sh
python -m tcc_crypto.daily grid-search --all-symbols
python -m tcc_crypto.daily final-test --all-symbols
```

`final-test` requires saved development datasets/search evidence and the complete
`experiment` datasets. It checks exact equality on their shared development dates.
The stage never tunes on test data: selected parameters remain frozen, while
selectors, scalers and estimators are refitted on each trailing window with the
approved one-observation gap. Identical feature preprocessing can be shared across
targets for the same date/window because it does not use target labels.

Final results go to
`outputs/binance/spot/1d/svm_final/binance_daily_svm_walk_forward_v1/{symbol}/`:
dated predictions, metrics, eligibility, frozen configurations, ROC/PR points,
ROC/PR figures, metadata and `svm_results.xlsx`. The tuned SVC is compared with
default SVC, constant-zero dummy and prior dummy on common successful dates.
Single-class windows retain dated omissions rather than invented predictions.
LUNAUSDT and combinations lacking an eligible development search remain excluded.
These are classifier results for an ex-post fixed universe, not portfolio returns.

When all assets have completed, `universe/experiment_overview.xlsx` in that same
evaluation directory consolidates their metrics, eligibility and artifact paths.
It retains individual asset-target-window comparisons rather than inventing a
pooled classifier score.

Use `python -m tcc_crypto.daily export --kind final-results --all-symbols --overwrite`
to regenerate final Excel and figures from saved tables without fitting models.
`workflows.final_evaluation.export_figures` regenerates only ROC/PR images;
precision-recall figures use step rendering consistent with sklearn's display.

### Regenerate inspection workbooks

Export reads the saved artifacts and does not repeat feature calculations or
model training:

```sh
python -m tcc_crypto.daily export --profile pilot --kind dataset --overwrite
python -m tcc_crypto.daily export --profile pilot --kind results --overwrite
```

The per-asset `features_and_targets.xlsx` contains Summary, Aligned data, Features,
Targets, Modeling dataset, and Definitions. The `svm_results.xlsx` workbooks
contain pilot predictions and metrics, or grid eligibility, folds, candidate
ranking, selected configurations, and execution settings.

## Exploratory analyses

Use `python -m tcc_crypto.explore <analysis> <operation>`. Available analyses are:

| Analysis | Purpose |
|---|---|
| `earliest`, `coverage` | First available candles and BTC quote-pair interval coverage |
| `annual-volume`, `trade-counts` | Annual BTC quote-pair activity and USDT trade-count ranking |
| `open-correlation`, `return-correlation` | Hourly opening-price and high-to-open appreciation correlations |
| `hourly-prices`, `hourly-activity` | Hourly descriptive statistics and figures |
| `daily-descriptive` | Daily price/volume statistics, semesters and native Excel charts |
| `future-high` | Exploratory D0–D3 future-high outcomes |
| `feature-selection` | Full-history features and rolling-selection diagnostics |

For analyses that use collected observations:

```sh
python -m tcc_crypto.explore hourly-prices paths --run-id example
python -m tcc_crypto.explore hourly-prices calculate --run-id example
python -m tcc_crypto.explore hourly-prices plot --run-id example
python -m tcc_crypto.explore hourly-prices export --run-id example
```

For API explorations, run `collect` before `calculate`. `run` executes the complete
applicable sequence and generates a UTC run identifier unless one is supplied.
Independent operations require `--run-id`. `collect` and `plot` are offered only
where applicable; `paths` displays locations without creating output directories.
Excel generation uses openpyxl, including native charts where required.

See the [exploratory execution guide](src/tcc_crypto/EXPLORATION.md) for each
analysis's functions, configuration, commands, inputs and outputs.

## Notebooks

Start JupyterLab after installing the development dependencies:

```sh
jupyter lab
```

The 17 notebooks contain imports, execution choices, calls into the package and
result displays. Run their cells gradually to inspect each stage:

- **01–04:** initial market and collection explorations.
- **05 and 10:** hourly and daily canonical data collection.
- **06–09:** hourly correlations and descriptive analyses.
- **11–13:** daily descriptive analysis, future-high outcomes and feature selection.
- **14–15:** SVM pilot and development grid-search inspection.
- **16:** [complete experiment supervisor review](notebooks/16_binance_daily_svm_experiment_results.ipynb):
  per-coin training, development-validation and final out-of-sample results,
  matched baselines, confusion matrices, ROC/PR curves and exclusions. Change
  `SYMBOL` to inspect a coin; the appendix includes every configured asset.

- **17:** [complete execution walkthrough](notebooks/17_binance_daily_svm_experiment_walkthrough.ipynb):
  Portuguese didactic explanations and copyable commands for existing raw inputs,
  gap treatment, 22 features, targets, both datasets, eligibility, preprocessing,
  full grid search, final walk-forward, selected-fold training scores and export.
  Set `SYMBOL`, an explicit new `RUN_ID` and `MODE = "run"` to execute one asset.
  Use `MODE = "load"` with an existing identifier to inspect saved stages without
  fitting models. Inspection target/window choices never reduce the experiment.
  Workbook regeneration is explicit through `EXPORT_WORKBOOKS = True`.

Notebook 16 only reloads saved evidence. In-sample scores are reconstructed
resubstitution scores for the selected candidate's original development training
folds, averaged over folds. They are not final-test training-window averages.
The explicit, resumable `workflows.experiment_review.reconstruct_in_sample()`
operation fits only these selected candidates and verifies their validation
scores against the completed search before saving
`{final_asset_directory}/supervisor_review/training_fold_metrics.csv` and metadata.
It never repeats the grid search or replaces final predictions. Training and
validation fold means must be distinguished from final matched-date metrics.

Use the reload cells to inspect a saved execution without rerunning calculations
or training. Exploratory runs are identified by `RUN_ID`; daily modeling uses its
pilot or development context with an optional isolated `RUN_ID`. Metric figures
report classifier performance.

Daily commands now accept `--run-id`; omitting it preserves historical paths and
metadata signatures. Derived paths insert `runs/{run_id}` after the context,
including configured directory overrides. Raw inputs remain shared. The new
`training-review` command reconstructs only selected development training folds.
For example, after preparing both profiles and completing the search:

```sh
python -m tcc_crypto.daily final-test --symbols BTCUSDT --run-id supervisor_20261029_btc_v1
python -m tcc_crypto.daily training-review --symbols BTCUSDT --run-id supervisor_20261029_btc_v1
```

Notebook 17 contains the complete ordered command guide, including the optional
`--all-symbols` expansion. Existing derived files require explicit `--overwrite`
for replacement; saved training reviews are reused unless overwrite is requested.

## Artifact locations and provenance

[paths.py](src/tcc_crypto/paths.py) is the source of directory and filename
constants. `ArtifactPaths` resolves daily artifacts; `FinalArtifactPaths` resolves
final classifier evidence; `ExplorationPaths` resolves exploratory artifacts.
Paths are rooted in the project, independently of the
command's working directory. Use `--repository-root` to select another checkout.

| Daily artifact | Default location |
|---|---|
| Raw observations | `data/raw/binance/spot/1d/{symbol}/` |
| Aligned observations | `data/processed/binance/spot/1d/aligned/{context_id}/{symbol}.csv.gz` |
| Features | `data/processed/binance/spot/1d/features/{context_id}/{symbol}.csv.gz` |
| Targets | `data/processed/binance/spot/1d/targets/{context_id}/{symbol}.csv.gz` |
| Modeling dataset | `data/processed/binance/spot/1d/datasets/{context_id}/{symbol}.csv.gz` |
| Dataset workbook | `outputs/binance/spot/1d/datasets/{context_id}/{symbol}/features_and_targets.xlsx` |
| Pilot results | `outputs/binance/spot/1d/svm_pilot/{context_id}/{symbol}/` |
| Grid-search results | `outputs/binance/spot/1d/grid_search/{context_id}/{symbol}/` |
| Final classifier results | `outputs/binance/spot/1d/svm_final/{evaluation_id}/{symbol}/` |
| Complete-universe overview | `outputs/binance/spot/1d/svm_final/{evaluation_id}/universe/experiment_overview.xlsx` |

`context_id` is the pilot's `dataset_id` or the development's `experiment_id`.
Result directories contain CSV tables, `svm_results.xlsx`, configuration snapshots
and run metadata. Exploratory tables use
`data/processed/binance/spot/{interval}/analyses/{analysis}/{analysis_id}/{run_id}/`;
workbooks use `data/exploration/binance/spot/{analysis}/{analysis_id}/{run_id}/`;
figures and manifests use `outputs/binance/spot/{analysis}/{analysis_id}/{run_id}/`.

Research data and generated outputs are versioned with the project, as explicitly
authorized by the researcher on 2026-10-23. This includes raw and processed data,
spreadsheets, figures, historical migration artifacts and model results. Local
environments, caches, credentials and temporary application lock files remain
excluded. Saved stages record
configuration and source checksums, schema, UTC timestamps, code revision and
package versions. Incompatible or modified inputs must be rebuilt before reuse.

### Historical migration

Historical artifacts are stored separately under `history/legacy...` directories.
The migration manifest maps original paths to preserved files. On checkouts that
still contain recognized legacy artifacts, inspect the migration before applying:

```sh
python -m tcc_crypto.migrate
python -m tcc_crypto.migrate --apply
```

Migration verifies checksums before removing old copies and records its progress
in `outputs/migrations/exploration-v1.json`. Canonical raw data is not moved.

## Scientific safeguards

- UTC timestamps and chronological order are preserved throughout the pipeline.
- Modeling fills only internal daily gaps and marks imputed observations.
  Descriptive analyses retain gaps; the full-history feature analysis blocks
  gapped series.
- Features use information available at their timestamp. Future-high outcomes
  belong to target or exploratory outcome construction.
- Feature selection and scaling are fitted on training rows within each window.
  Pilot and grid search retain their distinct temporal protocols.
- Correlations use the explicitly approved initial 30-pair candidate universe,
  independently of the expanded collection universe.
- Parabolic SAR remains provisional and identified in the exported definitions.

## Verification

```sh
PYTHONPATH=src python -m pytest -q
python scripts/validate_okf_docs.py docs
python -m ruff check src/tcc_crypto tests scripts
python -m ruff format --check src/tcc_crypto tests scripts
```

Tests cover formulas, UTC and gap handling, temporal boundaries, saved-stage
roundtrips, workbook contents, migration, and the package's layer boundaries.
Notebook cells are exercised with small local inputs and simulated API responses.
The suite does not require a full collection or full research experiment.

[AGENTS.md](AGENTS.md) defines layer responsibilities, notebook restrictions,
artifact contracts and the approved-methodology authority. Architecture tests
guard imports and notebook processing; Ruff settings live in `pyproject.toml`.
The same four checks run on pushes and pull requests through
[Repository quality](.github/workflows/quality.yml). CI reports failures; requiring
the check before merging also requires a GitHub branch-protection setting.
