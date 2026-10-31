# Exploratory execution and notebook guide

All fifteen notebooks are step-by-step clients of the package. Cells contain
imports, execution choices, function calls and display statements. Calculations,
validation, figures, persistence and model diagnostics belong to the package.
Install with `python -m pip install -e ".[dev]"` before using notebooks or commands.
The Python environment supplies Excel generation through openpyxl; no Node runtime
or external artifact-tool installation is needed.

## Responsibility map

| Analysis / notebook | Calculation | Workflow / command name | Inputs | Results |
|---|---|---|---|---|
| First candles / 01 | `analysis.market_exploration.earliest_table` | `earliest` | Saved first-kline API responses | UTC timestamps and original OHLC text |
| BTC coverage / 02 | `analysis.market_exploration.coverage_table` | `coverage` | Current catalog and first candles | Interval coverage and status snapshot |
| Annual BTC activity / 03 | `analysis.market_exploration.annual_volume` | `annual-volume` | Monthly candles, including current partial month | Monthly observations, annual sums and reconciliation |
| USDT trade counts / 04 | `analysis.market_exploration.trade_counts` | `trade-counts` | Closed daily candles through previous UTC day | Trade-count ranking and coverage diagnostics |
| Hourly collection / 05 | `collection.pipeline.run_collection` | `workflows.collection_review` | Hourly collection JSON | Immutable CSV, review Excel and metadata |
| Open-price correlation / 06 | `analysis.correlation.calculate_correlations` | `open-correlation` | Approved 30-pair hourly observations | Pairwise coefficients, counts and BTC comparison |
| High/open correlation / 07 | `analysis.correlation.correlation_series` | `return-correlation` | Same frozen candidate universe | Pairwise high/open appreciation correlation |
| Hourly prices / 08 | `analysis.hourly_prices` | `hourly-prices` | Hourly OHLC | Statistics, coverage, extrema and figures |
| Hourly activity / 09 | `analysis.hourly_activity` | `hourly-activity` | Five hourly activity fields | Statistics, coverage, extrema and figures |
| Daily collection / 10 | `collection.pipeline.run_collection` | `workflows.collection_review` | Daily collection JSON | Immutable CSV, review Excel and metadata |
| Daily prices and volume / 11 | `analysis.daily_descriptive` | `daily-descriptive` | Observed daily OHLC and USDT volume | Overall and semester statistics, five-tab Excel and figures |
| Future highs / 12 | `targets.future_high.calculate_future_high_returns` | `future-high` | Exact observed daily dates | D0–D3 outcomes and selection evidence |
| Feature selection / 13 | `analysis.feature_selection` | `feature-selection` | Full observed daily histories | Features, blocking diagnostics and rolling selection |
| SVM pilot / 14 | `modeling.pilot` | `daily pilot` | Prepared pilot dataset | Rolling predictions and classification metrics |
| Development search / 15 | `modeling.grid_search` | `daily grid-search` | Prepared development dataset | Eligibility, folds, ranking and selected parameters |

The first thirteen analysis workflows use `workflows.exploration`, except the two
canonical collection notebooks, which use `workflows.collection_review`.
Notebooks 14–15 use `workflows.daily_review` and the existing daily workflows.

## Independent stages

```sh
python -m tcc_crypto.explore hourly-prices paths --run-id example
python -m tcc_crypto.explore hourly-prices calculate --run-id example
python -m tcc_crypto.explore hourly-prices plot --run-id example
python -m tcc_crypto.explore hourly-prices export --run-id example
```

For API explorations, collect before calculating:

```sh
python -m tcc_crypto.explore annual-volume collect --run-id example
python -m tcc_crypto.explore annual-volume calculate --run-id example
python -m tcc_crypto.explore annual-volume export --run-id example
```

`run` performs the complete applicable sequence. `paths` performs no I/O. `collect`
is available only for the first four API explorations; `plot` is available only
for analyses with defined figures. Independent operations require `--run-id`.
`run` generates a UTC identifier unless one is supplied and prints it with the
resolved output directories. `--config`, `--repository-root` and `--symbols`
select explicit inputs. Correlations do not accept a universe override.
`--overwrite` is required to replace derived artifacts. Raw request snapshots are
never overwritten; resuming a collection retains its original execution cutoff.

The Python API exposes `open_exploration`, `load_inputs` / `collect_inputs`,
`calculate`, `build_figures`, `save_inputs`, `save_results`, `load_saved_inputs`,
`load_results` and `export_workbooks`. Feature analysis additionally exposes
`inspect_features` and `select_features` so its expensive selection stage can be
inspected separately. Calculating does not save; exporting does not calculate.
To inspect a saved run without processing, set `RUN_ID`, create its context, and
call the notebook's reload cell; calculation cells need not be run first.

`daily_review.load_model` independently restores the daily SVM result. Window
inspection shares the real selector, scaler, temporal split and candidate
functions. Performance plots report classifier evidence, never portfolio returns.

## Artifact locations

`paths.ExplorationPaths` resolves the following from the repository root:

| Artifact | Location |
|---|---|
| New API response evidence | `data/raw/binance/spot/exploration/{analysis}/{run_id}/` |
| Typed derived tables | `data/processed/binance/spot/{interval}/analyses/{analysis}/{analysis_id}/{run_id}/` |
| Exploratory Excel | `data/exploration/binance/spot/{analysis}/{analysis_id}/{run_id}/` |
| Figures and stage manifests | `outputs/binance/spot/{analysis}/{analysis_id}/{run_id}/` |

`ANALYSIS_INPUTS_NAME` and `ANALYSIS_RESULTS_NAME` identify the stage manifests;
`ANALYSIS_WORKBOOK_NAME` and `ANALYSIS_TABLE_SUFFIX` identify standard outputs.
Per-asset workbooks use the symbol filename. API queries retain original decimal
strings and request provenance. Large per-symbol histories are loaded lazily.
Tables retain typed UTC columns and index, nullable fields, checksums and source
integrity. Metadata records settings, universe, revision, execution timestamp,
versions and the random seed where used. Changing a source or configuration
invalidates the saved execution.

Operational legacy output keys in exploratory JSONs are rejected with a migration
message. Daily modeling retains its explicit custom-path compatibility. Standard
new executions use only the centralized locations. Import implementations directly
from their domain packages. Flat compatibility modules, legacy forwarding scripts
and the old JSON packet export/workflow wrappers have been removed. The supported
command entrypoints are `python -m tcc_crypto.daily`, `python -m tcc_crypto.explore`
and `python -m tcc_crypto.migrate`.

## Historical migration

```sh
python -m tcc_crypto.migrate
python -m tcc_crypto.migrate --apply
```

The default is a read-only inventory. Application preflights collisions, copies
recognized research artifacts, verifies SHA-256, journals each verified item,
and removes only the identical old copy. Repeating application resumes the
journal in `outputs/migrations/exploration-v1.json`. Historical outputs go into
`history/legacy...` directories beside the corresponding new analysis or SVM
context, retaining filenames and bytes. Original provenance is not rewritten;
the journal maps old paths to their destinations. Historical files do not become
new validated-stage artifacts simply because they were relocated.

Canonical `data/raw` files are never moved. Personal PDFs and unrecognized
folders are excluded. Directory names associated with historical chat executions
are recognized only through explicit research-artifact mappings. Unknown assets
are left untouched rather than guessed. Historical documentation may retain
original paths as evidence; consult the migration manifest to locate them now.

## Scientific boundaries and checks

The 30-pair correlation universe is frozen in its own JSONs, independently of the
expanded 40-pair collection. Corrected outputs can differ from historical
notebooks that accidentally read the expanded universe. The original eligibility
cutoff, Pearson method, exact UTC pairing and absence of imputation are preserved.

Descriptive analyses do not fill gaps. The full-history feature analysis blocks
gapped input, while the modeling preparation retains its separately approved
internal-gap treatment. D0–D3 intentionally use future highs and must never enter
features. Parabolic SAR remains provisional. Sample estimators, CV units,
partial-month/year/semester labels and original random selection remain explicit.

Run `PYTHONPATH=src python -m pytest -q`, `python scripts/validate_okf_docs.py docs`,
`python -m ruff check src/tcc_crypto tests scripts`, and
`python -m ruff format --check src/tcc_crypto tests scripts`.
The tests execute actual notebook code cells on local synthetic data and mocked
network responses, compare pre-extraction fixtures, and exercise migration and
native chart exports. They do not repeat the full API collection or full search.
