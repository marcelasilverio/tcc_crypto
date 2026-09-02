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
docs/             Methodology and research documentation
notebooks/        Exploration, visualization, and interpretation
outputs/          Generated models, predictions, figures, tables, and metrics
src/tcc_crypto/   Reusable Python implementation
tests/            Automated tests
```

The structure is intentionally shallow. Add a subdirectory only when multiple
files with a shared, stable responsibility make the split useful. Research data
and generated outputs are ignored by Git; their `.gitkeep` files only preserve
the required directories.
