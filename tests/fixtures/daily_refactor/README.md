# Pre-refactor characterization tables

These small, synthetic tables were recorded from the original flat modules
before extracting the daily pipeline on 2026-10-22. They contain no downloaded
market data and are intentionally versioned as regression fixtures.

- `aligned`, `features`, `targets`: the existing daily-feature test's deterministic
  35-day OHLC/quote-volume sequence, with days at positions 16 and 17 removed and
  internally forward-filled before calculating the original 22 features/targets.
- `pilot_*`: the existing 12-row pilot test data, a four-row rolling window,
  variance threshold 0, correlation threshold 0.99, and its two synthetic features.
- `grid_*`: the existing 12-row grid test data, two linear candidates, two folds,
  three validation observations and a one-observation gap.
- `schema.json`: original dtypes and non-string object-cell types. pandas table
  JSON alone loses the distinction between all-null objects, `None`, and `pd.NA`.

Timing fields are excluded. JSON floating-point values retain 15 decimal places;
reference comparisons use 1e-12 tolerances. The independent CSV roundtrip and
in-memory-versus-staged integration tests require exact floating-point equality.
Do not regenerate these fixtures from the refactored code to make a test pass.
