# Cryptocurrency portfolio research

This repository supports an undergraduate experiment combining Support Vector
Machines with mean-variance portfolio selection.

## Project structure

```text
configs/          Experiment configuration
data/
  exploration/   Local exploratory data and spreadsheets
  processed/     Cleaned and derived datasets
  raw/           Immutable source data
docs/             OKF research knowledge and methodology bundle
notebooks/        Exploration, visualization, and interpretation
outputs/          Generated models, predictions, figures, tables, and metrics
src/tcc_crypto/   Reusable Python implementation
tests/            Automated tests
```

The structure is intentionally shallow. Add a subdirectory only when multiple
files with a shared, stable responsibility make the split useful. Research data
and generated outputs are ignored by Git; their `.gitkeep` files only preserve
the required directories.

Documentation navigation begins at [`docs/index.md`](docs/index.md). The bundle
uses Open Knowledge Format v0.2 frontmatter, provenance, authority, and index
conventions.

## Daily pipeline

The daily workflow is organized into collection, data preparation, features,
targets, modeling, reporting, and workflow packages. See the
[implementation and execution guide](src/tcc_crypto/README.md) for the location
of each formula, independent stage commands, artifact constants, and compatibility.

```sh
python -m pip install -e ".[dev]"
python -m tcc_crypto.daily paths --profile pilot
python -m tcc_crypto.daily prepare --profile pilot
python -m tcc_crypto.daily pilot
```

The `paths` command is read-only. Preparation requires collected raw data; model
commands require a prepared dataset. Use `--overwrite` explicitly to replace
derived outputs. Historical artifacts remain in their original locations.
