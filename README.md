# Cryptocurrency portfolio research

This repository supports undergraduate research on cryptocurrency portfolio
selection using Support Vector Machines and Markowitz mean-variance optimization.
The implemented workflows cover Binance Spot data collection, exploratory
analysis, daily feature and target construction, a rolling SVM pilot, and temporal
grid search. Portfolio allocation, financial backtesting, and final walk-forward
evaluation remain separate stages outside the current implementation.

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
assemble dataset → pilot or grid search → inspect results.**

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

The 15 notebooks contain imports, execution choices, calls into the package and
result displays. Run their cells gradually to inspect each stage:

- **01–04:** initial market and collection explorations.
- **05 and 10:** hourly and daily canonical data collection.
- **06–09:** hourly correlations and descriptive analyses.
- **11–13:** daily descriptive analysis, future-high outcomes and feature selection.
- **14–15:** SVM pilot and development grid-search inspection.

Use the reload cells to inspect a saved execution without rerunning calculations
or training. Exploratory runs are identified by `RUN_ID`; daily modeling uses its
pilot or development context. Metric figures report classifier performance.

## Artifact locations and provenance

[paths.py](src/tcc_crypto/paths.py) is the source of directory and filename
constants. `ArtifactPaths` resolves daily artifacts; `ExplorationPaths` resolves
exploratory artifacts. Paths are rooted in the project, independently of the
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

`context_id` is the pilot's `dataset_id` or the development's `experiment_id`.
Result directories contain CSV tables, `svm_results.xlsx`, configuration snapshots
and run metadata. Exploratory tables use
`data/processed/binance/spot/{interval}/analyses/{analysis}/{analysis_id}/{run_id}/`;
workbooks use `data/exploration/binance/spot/{analysis}/{analysis_id}/{run_id}/`;
figures and manifests use `outputs/binance/spot/{analysis}/{analysis_id}/{run_id}/`.

Research data and generated outputs are kept out of Git. Saved stages record
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
