# Daily research pipeline

The package separates the research steps from persistence and presentation.
All timestamps use UTC. Raw Binance CSVs remain immutable. The development
workflow implements model selection only; it does not run the reserved final test.

## Where each step lives

| Step | Implementation | Input | Output |
| --- | --- | --- | --- |
| Collect raw data | `collection/pipeline.py`, `client.py`, `pagination.py`, `checkpoints.py` | Approved collection JSON and Binance pages | Immutable CSV.gz, metadata and review workbook |
| Treat internal gaps | `data/gaps.py:fill_internal_daily_gaps` | Observed daily OHLC and quote volume | Forward-filled bounded gaps and `is_imputed` |
| Calculate price features | `features/price.py:calculate_price_features` | Aligned daily candles | Explicit formulas r1-r15 |
| Calculate indicators | `features/indicators.py` | Aligned daily candles | Momentum, RSI, SAR, ATR, TR, AD and OBV |
| Compose 22 features | `features/daily.py:calculate_daily_features` | Calculation period including warm-up | Ordered feature table retaining warm-up NaNs |
| Inspect definitions | `features/catalog.py:feature_definitions` | Approved feature definitions | Formula, inputs, units, parameters and function references |
| Build targets | `targets/daily.py:build_next_day_d0_targets` | Aligned candles and sample feature dates | Next-day D0 and 2%, 3%, 4% binary labels |
| Assemble dataset | `data/dataset.py:assemble_dataset` | Features, targets and imputation flags | Joined dataset, without recalculating features |
| Select and normalize | `modeling/preprocessing.py:prepare_window` | One training window and later evaluation rows | Training-fitted selector/scaler and transformed arrays |
| Pilot | `modeling/pilot.py:run_default_svc_rolling_pilot` | Prepared pilot dataset | Rolling predictions and metrics |
| Grid search | `modeling/grid_search.py:run_temporal_grid_search` | Prepared development dataset | Eligibility, fold scores, ranked candidates and selections |
| Export Excel | `reporting/workbooks.py` | Existing tables and metadata | Human-readable inspection workbooks |

`workflows/daily_data.py` coordinates independent preparation stages.
`workflows/svm.py` coordinates training and export. Pure calculations do not
read configuration files or write artifacts. `DailyDataConfig` contains only
data preparation settings; legacy JSON adapters retain their existing validation.

## Setup and independent execution

From the repository root, install the editable package:

```sh
python -m pip install -e ".[dev]"
```

The module command then works from other directories. An explicit
`--repository-root` can select another checkout. `--config` paths and nested
configuration references are interpreted relative to that root.

```sh
python -m tcc_crypto.daily paths --profile pilot
python -m tcc_crypto.daily collect --symbols BTCUSDT
python -m tcc_crypto.daily align --profile pilot
python -m tcc_crypto.daily features --profile pilot
python -m tcc_crypto.daily targets --profile pilot
python -m tcc_crypto.daily dataset --profile pilot
python -m tcc_crypto.daily pilot
```

`prepare` is the explicit shortcut for align, features, targets and dataset.
It does not collect data or fit models. Each independent command requires its
upstream files; missing or incompatible inputs produce an actionable error.

```sh
python -m tcc_crypto.daily prepare --profile development --symbols BTCUSDT
python -m tcc_crypto.daily grid-search --symbols BTCUSDT
python -m tcc_crypto.daily export --profile development --kind dataset
python -m tcc_crypto.daily export --profile development --kind results --overwrite
```

Development defaults to BTCUSDT. `--all-symbols` explicitly selects the configured
universe. `grid-search --eligibility-only` saves eligibility for already prepared
data without fitting candidates. Ineligible searches are recorded in normal grid
outputs; entirely ineligible assets have empty result tables, not invented models.

`--overwrite` is required to replace derived artifacts, including workbooks.
Collection retains its existing checkpoint/reuse behavior and raw immutability.
Use the module commands above directly; the three legacy forwarding scripts
have been removed. Model commands require preparation first.

## Artifact locations

Every path is resolved by `paths.py:ArtifactPaths`. `daily paths` displays the
complete inventory without creating directories. Defaults are declared once as
named constants in `paths.py`; filenames are centralized there too.

| Constant | Default relative directory |
| --- | --- |
| `RAW_DAILY_DIR` | `data/raw/binance/spot/1d` |
| `ALIGNED_DAILY_DIR` | `data/processed/binance/spot/1d/aligned` |
| `DAILY_FEATURES_DIR` | `data/processed/binance/spot/1d/features` |
| `DAILY_TARGETS_DIR` | `data/processed/binance/spot/1d/targets` |
| `DAILY_DATASETS_DIR` | `data/processed/binance/spot/1d/datasets` |
| `DATASET_WORKBOOKS_DIR` | `outputs/binance/spot/1d/datasets` |
| `SVM_PILOT_RESULTS_DIR` | `outputs/binance/spot/1d/svm_pilot` |
| `SVM_GRID_SEARCH_RESULTS_DIR` | `outputs/binance/spot/1d/grid_search` |

Intermediate tables append `{context_id}/{symbol}.csv.gz`. Workbook and model
result directories append `{context_id}/{symbol}/`. The context is the pilot's
`dataset_id` or development's `experiment_id`; their periods and warm-up histories
must never be mixed. The original raw filename convention is preserved.

For custom legacy configurations, `output_directory` overrides the model-result
base directory (with a symbol subdirectory), `feature_output_directory` overrides
the feature base (with context and symbol), and `raw_directory` overrides the pilot
raw input directory. Development gets its raw location from the collection config.
Checked-in experiment configs use centralized defaults. Recognized historical
artifacts are relocated by the audited migration described in the
[exploratory guide](EXPLORATION.md). Notebook 13 retains its full-history
exploratory behavior through the new analysis workflow, separately from modeling.

Every table has a `.metadata.json` sidecar containing schema, dtypes, UTC index,
configuration, period, warm-up, raw/upstream checksums, execution time, revision
and package versions. CSV reading restores nullable `Int8` labels and `boolean`
markers, float precision and object scalar types. `__TCC_NULL__` is the reserved
CSV missing-value token; empty diagnostic strings remain empty strings.
A modified input or configuration invalidates downstream artifacts. Rebuild the
affected stages with explicit overwrite. Metadata signatures include all referenced
configurations, so configuration changes conservatively require rebuilding data.

`features_and_targets.xlsx` contains Summary, Aligned data, Features, Targets,
Modeling dataset and Definitions. `svm_results.xlsx` contains pilot predictions
and metrics, or grid eligibility, folds, ranking and selections, plus configuration.
Dates are ISO UTC text; missing values appear as blank cells. Excel contains copies
of Python results, not a second implementation of the formulas. Export can be
repeated independently of calculations and model training.

## Scientific invariants and public imports

Internal gaps are filled before restricting the calculation period, matching the
original builders. Leading/trailing dates are never synthesized. June 2019 remains
warm-up; indicators retain their original initialization, including cumulative AD
and OBV. The extra next-day outcome is retained in aligned data for the last target,
while the persisted feature table ends at the approved sample boundary.

Targets are `high[t+1] / open[t+1] - 1` compared with 2%, 3%, 4%. A missing next day
stays unlabeled. Training accesses only the 22 named feature columns. Selection and
scaling are fitted inside each training window/fold. The pilot's original rolling
schedule and the grid's one-observation gap remain distinct. Zero-valued SAR
parameters remain provisional and explicitly marked for later verification.

Import implementations from their owning layer, for example:

```python
from tcc_crypto.collection.pipeline import run_collection
from tcc_crypto.features.daily import calculate_daily_features
from tcc_crypto.targets.daily import build_next_day_d0_targets
from tcc_crypto.modeling.pilot import run_default_svc_rolling_pilot
```

The historical flat modules, forwarding scripts, compatibility aliases and
old descriptive packet/workflow wrappers have been removed. External code that
used those imports must switch to the corresponding layer. Tests exercise the
owning modules directly.

Notebooks 14 and 15 call the shared stages and show intermediate results. Their
outputs are cleared after migration; metadata and user kernel preferences are
preserved. No expensive experiment was executed to regenerate notebook outputs.

## Verification

```sh
PYTHONPATH=src python -m pytest -q
python scripts/validate_okf_docs.py docs
```

Small synthetic characterization fixtures were recorded from the original code
before extraction. They cover features, targets, pilot predictions/metrics and
candidate ranking. Integration tests compare in-memory and persisted workflows,
including exact float roundtrips, nullable values, raw immutability, stale inputs,
workbook contents, independent export and invocation outside the checkout.
