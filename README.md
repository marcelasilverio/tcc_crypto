# Daily cryptocurrency classification and portfolio experiment

The active workflow is **collect → validate and treat → build dataset → train and evaluate → inspect CSVs**.
An independent `portfolio` stage allocates capital and simulates daily portfolio
returns from saved classification evidence. Invoke this stage explicitly.

Start with the [implementation and consultation guide](docs/decisions/daily-code-organization.md),
[experiment diagram](docs/decisions/daily-block-window-experiment-diagram.md), and
[presentation notebook](notebooks/17_binance_daily_svm_experiment_walkthrough.ipynb).
The [documentation index](docs/index.md) records research authority and methodology.

Install with `python -m pip install -e '.[dev]'`. Classification uses
[experiment.json](configs/experiment.json) and [svm_grid.json](configs/svm_grid.json).
The independent portfolio stage uses [portfolio.json](configs/portfolio.json).
PyPortfolioOpt computes minimum-variance weights through the CVXPY/CLARABEL backend.

## Commands

Run one stage at a time for a single asset. Each stage after `collect` reads
the saved output of its predecessor; it does not run missing stages for you.

```sh
python -m tcc_crypto.experiment collect --symbols BTCUSDT
python -m tcc_crypto.experiment prepare --symbols BTCUSDT --run-id review_01
python -m tcc_crypto.experiment dataset --symbols BTCUSDT --run-id review_01
python -m tcc_crypto.experiment train --symbols BTCUSDT --run-id review_01
python -m tcc_crypto.experiment results --symbols BTCUSDT --run-id review_01 --overwrite
```

| Stage | What it does |
| --- | --- |
| `collect` | Collects or resumes Binance daily candles; preserves existing raw files. |
| `prepare` | Validates raw candles, records availability, and fills internal gaps. |
| `dataset` | Builds and saves features, next-day targets, and the modeling dataset. |
| `train` | Runs the temporal searches, evaluates models, and writes audit and main CSVs. |
| `results` | Rebuilds consultation CSVs from saved preparation and training evidence. |
| `run` | Explicitly runs `collect`, `prepare`, `dataset`, and `train` in order. |
| `portfolio` | Independently allocates and simulates capital using the latest saved classification execution. |

For the complete sequence on one asset, use:

```sh
python -m tcc_crypto.experiment run --symbols BTCUSDT --run-id review_02
```

To choose several assets, replace `--symbols BTCUSDT` with, for example,
`--symbols BTCUSDT ADAUSDT`. To use the entire configured universe, replace
it with `--all-symbols`:

```sh
python -m tcc_crypto.experiment run --all-symbols --run-id full_01
```

The classification commands accept these options:

| Option | Use |
| --- | --- |
| `--symbols BTCUSDT ADAUSDT` | Explicit asset subset; required unless `--all-symbols` is used. |
| `--all-symbols` | Use all configured assets; cannot be combined with `--symbols`. |
| `--run-id ID` | Name the derived execution; required for every stage except `collect`. |
| `--config PATH` | Read an alternative main experiment JSON; its grid path is resolved alongside it. |
| `--overwrite` | Replace existing derived outputs for the same run configuration. Raw collection remains immutable. |
| `-h`, `--help` | Show the command help. |

For example, this repeats training with an explicit configuration and replaces
that run's derived results:

```sh
python -m tcc_crypto.experiment train --config configs/experiment.json --symbols BTCUSDT --run-id review_01 --overwrite
```

The `results` example above uses `--overwrite` because `train` already creates
the main CSVs.
Production training uses the full approved grid and can take substantial time.
The refactor was tested with small local fixtures, not a full scientific run.

Intermediate tables: `data/processed/daily_<run_id>/`.
Main CSVs and detailed audit: `outputs/experiments/daily_<run_id>/`.
Saved classification signals preserve missing values, distinct from zero. Standard readers restore UTC
and nullable types and reject stale inputs through source checksums.

## Independent portfolio simulation

Run the portfolio stage explicitly after the classification inputs have been saved:

```sh
python -m tcc_crypto.experiment portfolio --run-id portfolio_01
```

By default, this command selects the most recent classification execution by its saved UTC
execution timestamp, using `tuned_svc` out-of-sample predictions from 60-day
training blocks. It validates saved provenance and reads the historical universe.
The portfolio ID identifies its own outputs. The classification commands,
including `run`, have no portfolio execution step.

The four strategies combine SVM or shared random signals with minimum-variance
or equal-weight allocation. Each target (1%, 2% and 3%) has four independent
capital trajectories starting at 10,000 USDT and compounding across days and
blocks. Allocation uses the preceding 60 daily R1 values. Missing SVM predictions
reuse the last available signal for the same asset and target, with provenance
recorded. Insufficient-history assets are excluded. Empty selections and failed
optimizations hold cash under the approved rules. See the
[portfolio methodology](docs/decisions/daily-portfolio-allocation.md) for execution,
imputation and return assumptions.

Results are saved in `outputs/portfolios/<run_id>/` as `capital.csv`, `signals.csv`
and `operations.csv`, together with schemas, configuration, source checksums and
execution metadata. A completion manifest and directory lock protect publication.
`--overwrite` requires matching portfolio configuration and source identity.
Use `--portfolio-config PATH` to select another portfolio configuration file.
The command derives its universe from saved training; asset-selection flags apply
to classification commands.

Open [Notebook 19](notebooks/19_binance_daily_portfolio_results_visual_report.ipynb)
and select the portfolio run ID to inspect final capital and audit counts and
construct three charts, one per target with four strategy curves. Its report
loader validates the saved portfolio and original source evidence.

Historical sources, configurations, notebooks, outputs and reports are available
in [Git history](https://github.com/marcelasilverio/tcc_crypto/tree/855e32eb9d248f1e36796bd09dd7233210d10d54). The working tree contains the current experiment and
its supporting documentation. All raw files remain at their original paths.
See the [history retention decision](docs/decisions/git-only-history-retention.md).

Validation:

```sh
PYTHONPATH=src python -m pytest -q
python scripts/validate_okf_docs.py docs
python -m ruff check src/tcc_crypto tests scripts
python -m ruff format --check src/tcc_crypto tests scripts
```

## Rights and academic access

Copyright (c) 2026 Marcela Prata Silvério. All rights reserved.

This repository is available for reading and academic review, including review
by the research advisor. It is not released under an open-source license.
Reuse of original copyrighted material requires prior written permission,
except as permitted by applicable law or the GitHub Terms of Service.
Third-party materials retain their respective rights and terms.
See [LICENSE](LICENSE) for the complete notice.

## Saved results visual report

[Notebook 18](notebooks/18_binance_daily_svm_results_visual_report.ipynb) reads the
saved `full_01` execution and plots data coverage, treatment, classification
metrics, confusion counts, class balance, signals, feature retention and selected
parameters. Run it in the project environment; change the target/window display
filters to inspect other saved settings. It validates saved provenance and does
not collect data or fit models. Scores are descriptive means of nonmissing block
metrics, with training and validation shown separately.

Notebook presentation is written in Portuguese. Metrics notebooks keep filtering,
descriptive aggregation and chart construction directly in their cells; other
notebooks remain strict clients of package stages. See the
[notebook policy](docs/decisions/notebook-language-and-metrics-logic.md).


## Explicit portfolio source selection

Select a saved classification execution with `--source-run-id`:

```sh
python -m tcc_crypto.experiment portfolio --run-id portfolio_01 --source-run-id full_01
```

`--source-run-id` identifies the input training execution, while `--run-id`
identifies the output portfolio execution. When the source option is omitted,
the configured latest-execution policy applies. An explicit source takes
precedence over that default and is validated under its saved configuration.
Missing or incompatible inputs produce an error without falling back to another
execution. The resolved source and selection mode are recorded in metadata.
This option is exclusive to the portfolio command. The Python API accepts the
same choice as `execute_portfolio(..., source_run_id="full_01")`.
