# Daily cryptocurrency classification experiment

The active workflow is **collect → validate and treat → build dataset → train and evaluate → inspect CSVs**.
Portfolio optimization and financial evaluation are outside the current scope.

Start with the [implementation and consultation guide](docs/decisions/daily-code-organization.md),
[experiment diagram](docs/decisions/daily-block-window-experiment-diagram.md), and
[presentation notebook](notebooks/17_binance_daily_svm_experiment_walkthrough.ipynb).
The [documentation index](docs/index.md) records research authority and methodology.

Install with `python -m pip install -e '.[dev]'`. Two JSONs configure the experiment:
[experiment.json](configs/experiment.json) and [svm_grid.json](configs/svm_grid.json).

```sh
python -m tcc_crypto.experiment prepare --symbols BTCUSDT --run-id review_01
python -m tcc_crypto.experiment dataset --symbols BTCUSDT --run-id review_01
python -m tcc_crypto.experiment train --symbols BTCUSDT --run-id review_01
python -m tcc_crypto.experiment results --symbols BTCUSDT --run-id review_01 --overwrite
```

These commands require saved upstream inputs; preparation requires collected raw
candles. Use `collect` explicitly to collect/resume, or `run` to explicitly chain
all stages. Choose `--symbols` or `--all-symbols`; derived stages require a run ID.
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
