# AGENTS.md

## Project purpose

This repository supports an undergraduate research experiment on
cryptocurrency portfolio selection using Support Vector Machines and
Markowitz mean-variance optimization.

The repository is developed incrementally under direct human review. It is
not an autonomous product-development project.

## Research source context

Before making methodological or experimental changes, read
`docs/index.md`, `docs/tcc/index.md`, and the topic-specific documents they
link. They provide the authority map for the documentation bundle and an
English synopsis of the TCC I manuscript that defines the research motivation,
theoretical basis, and proposed experiment.

The TCC I documents are research context, not automatic approval for proposed
parameters. This file and explicitly recorded methodology decisions take
precedence whenever the source manuscript is ambiguous, incomplete, or
inconsistent.

## Language

All repository content must be written in English, including:

- source code;
- identifiers;
- comments and docstrings;
- configuration keys;
- documentation;
- commit messages;
- notebook titles and narrative cells;
- chart labels;
- filenames and directory names.

Conversation with the repository owner may be in Portuguese.

## Working principles

1. Work only on the task explicitly requested by the user.
2. Prefer small, reviewable changes over broad implementations.
3. Do not create unrelated abstractions, features, or infrastructure.
4. Inspect the existing implementation before proposing changes.
5. State assumptions whenever the research specification is incomplete.
6. Do not make methodological choices silently.
7. Do not modify the research design without explicit user approval.
8. Do not commit, push, delete data, or rewrite Git history unless requested.
9. Preserve user changes and avoid modifying unrelated files.
10. Explain material tradeoffs when more than one valid approach exists.

If a task would require a significant methodological decision, stop and
request direction before implementing that decision.

## Research protocol

The planned experiment contains the following stages:

1. Collect historical spot-market kline data from the Binance public API.
2. Validate, clean, align, and store the observations.
3. Build price-derived features and technical indicators.
4. Construct binary targets for return thresholds of 3%, 4%, and 5% over
   the approved holding window.
5. Perform feature selection using training data only.
6. Normalize features using training data only.
7. Train and evaluate an SVM classifier with temporal validation.
8. Use classification signals to select portfolio candidates.
9. Allocate capital using either equal weights or Markowitz optimization.
10. Backtest and compare the approved strategies.
11. Report classification and financial performance separately.

The planned strategy comparison includes:

- Buy and Hold;
- SVM plus equal weighting;
- Naive selection plus equal weighting;
- Naive selection plus Markowitz optimization;
- SVM plus Markowitz optimization.

These descriptions are research requirements, not permission to invent
missing implementation details.

## Decisions requiring explicit approval

Do not assume values for unresolved experimental choices, including:

- cryptocurrency universe and eligibility rules;
- sample start and end dates;
- candle interval;
- quote asset;
- training, validation, and test window sizes;
- rolling or expanding window behavior;
- rebalance frequency;
- SVM kernel and hyperparameter search space;
- feature-selection method;
- Markowitz objective and constraints;
- expected-return and covariance estimators;
- behavior when no asset receives a positive signal;
- transaction costs, slippage, and liquidity assumptions;
- risk-free rate;
- missing-data and asset-listing treatment;
- the exact definition of the naive baseline.

Document every approved choice as a `Methodology Decision` concept under
`docs/decisions/`, add it to `docs/decisions/index.md`, and record it in the
relevant experiment configuration.

## Open Knowledge Format documentation

The `docs/` directory is an Open Knowledge Format v0.2 bundle. When creating or
editing documentation:

- follow the local contract described in `docs/index.md`;
- include parseable YAML frontmatter in every concept document;
- use `index.md` and `log.md` only for their reserved OKF purposes;
- select the `authority` value that reflects the document's actual role;
- do not treat `verified` as methodological approval;
- do not add or update a human `verified` entry without that person's explicit
  review and approval;
- preserve source provenance and update the nearest `index.md`;
- run `python scripts/validate_okf_docs.py docs` after documentation changes.

## Prevention of look-ahead bias

Temporal integrity is mandatory.

- Never randomly shuffle time-series observations.
- Never use future data to construct features available at an earlier time.
- Fit scalers, selectors, models, and estimators on training data only.
- Construct portfolio weights only from information available at the
  rebalance timestamp.
- Keep target-horizon observations out of overlapping training boundaries
  when overlap would leak future information.
- Preserve timestamps and timezone information throughout the pipeline.
- Use UTC as the canonical timezone.
- Add tests for temporal boundaries and feature/target alignment.

Any possible source of data leakage must be reported before results are
interpreted.

## Data management

- Treat files under `data/raw/` as immutable.
- Store collection metadata such as symbol, interval, request time, source,
  and requested date range.
- Do not overwrite raw data with cleaned data.
- Keep exploratory spreadsheets under `data/exploration/`.
- Keep generated and large datasets out of Git.
- Version only small, non-sensitive samples needed for tests.
- Never commit API keys, credentials, tokens, or local environment files.
- Do not introduce a new external data source without approval.
- Validate schemas, timestamp uniqueness, chronological ordering, missing
  intervals, numeric types, and OHLC consistency.

Downloaded data must be reproducible from documented commands and
configuration whenever the upstream API permits it.

## Code organization

- Put reusable implementation in `src/tcc_crypto/`.
- Use notebooks for exploration, visualization, and result interpretation.
- Do not make notebooks the only location of experiment logic.
- Keep data collection, feature engineering, modeling, portfolio
  construction, backtesting, and evaluation as separate concerns.
- Prefer explicit functions with typed inputs and outputs.
- Avoid hidden global state and hard-coded local paths.
- Load experimental parameters from configuration files.
- Use `pathlib` for filesystem paths.
- Use logging instead of scattered `print` statements in library code.
- Add docstrings where behavior, assumptions, or formulas are not obvious.

## Financial calculations

Financial formulas must define:

- input price convention;
- return type, such as simple or logarithmic;
- observation frequency;
- annualization factor, when applicable;
- treatment of missing observations;
- portfolio-weight constraints;
- rebalance timing;
- cost assumptions.

Use numerically stable implementations and test formulas with small,
manually verifiable examples.

## Reproducibility

Each experiment must record at least:

- experiment identifier;
- configuration;
- execution timestamp;
- code revision when Git is available;
- data range and asset universe;
- random seed;
- package versions;
- feature list;
- model parameters;
- portfolio constraints;
- evaluation metrics;
- output artifact locations.

Random behavior must use an explicit seed. Do not claim reproducibility when
required inputs or environment details are missing.

## Testing and validation

Add tests in proportion to the requested change.

Priority test areas include:

- Binance pagination and response parsing;
- timestamp conversion and UTC handling;
- OHLCV validation;
- feature formulas;
- target construction and holding-window boundaries;
- prevention of look-ahead leakage;
- temporal train/test splits;
- portfolio weights summing to one;
- optimization constraints;
- strategy return calculations;
- transaction-cost application;
- behavior with missing data or no selected assets.

Run the relevant tests before declaring a task complete. Report the exact
commands executed and any tests that could not be run.

## Dependencies

- Declare runtime and development dependencies in `pyproject.toml`.
- Keep the lockfile synchronized.
- Do not add a dependency when the standard library or an existing dependency
  is sufficient.
- Explain the purpose of every newly introduced dependency.
- Do not upgrade unrelated dependencies as part of a scoped task.

## Generated outputs

Do not manually edit generated datasets, model artifacts, figures, or metric
files. Regenerate them through the corresponding pipeline.

Charts and tables must include clear English labels, units, date ranges, and
enough context to identify the experiment that produced them.

## Definition of done

A task is complete only when:

- the requested scope has been implemented;
- relevant tests pass;
- formatting and static checks pass when configured;
- no obvious data leakage has been introduced;
- documentation or configuration is updated when behavior changes;
- generated files are placed in their designated directories;
- assumptions and unresolved questions are reported;
- the final response summarizes changed files and verification performed.

## Agent response expectations

At the end of an implementation task, report:

1. what changed;
2. why it changed;
3. files affected;
4. checks or tests executed;
5. assumptions made;
6. remaining methodological decisions or risks.

Do not describe unimplemented work as complete.
