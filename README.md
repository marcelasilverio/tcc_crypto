# Daily cryptocurrency classification experiment

The active workflow is **collect → validate and treat → build dataset → train and evaluate → inspect CSVs**.
Portfolio optimization and financial evaluation are outside the current scope.

Start with the [implementation and consultation guide](docs/decisions/daily-code-organization.md),
[experiment diagram](docs/decisions/daily-block-window-experiment-diagram.md), and
[presentation notebook](notebooks/17_binance_daily_svm_experiment_walkthrough.ipynb).
The [documentation index](docs/index.md) records research authority and methodology.

Install with `python -m pip install -e '.[dev]'`. Two JSONs configure the experiment:
[experiment.json](configs/experiment.json) and [svm_grid.json](configs/svm_grid.json).

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

The public command accepts these options:

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
Missing signals remain missing, distinct from zero. Standard readers restore UTC
and nullable types and reject stale inputs through source checksums.

Previous sources/configurations/notebooks/tests are reference-only under
`archive/pre_block_20261031/`; historical outputs are under `outputs/archive/`.
The [manifest](archive/pre_block_20261031/migration.json) resolves old paths.
Raw files and historical Excel bytes are preserved. No old entrypoint is supported.

Validation:

```sh
PYTHONPATH=src python -m pytest -q
python scripts/validate_okf_docs.py docs
python -m ruff check src/tcc_crypto tests scripts
python -m ruff format --check src/tcc_crypto tests scripts
```
