---
type: Methodology Decision
title: Daily minimum-variance and equal-weight portfolio comparison
description: Approved daily capital simulation from saved 60-day SVM predictions and shared random signals, with rolling R1 covariance and same-day exits.
tags: [portfolio, allocation, backtesting, minimum-variance, daily]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-11-07T12:00:00Z" }
sources:
  - id: researcher-confirmation
    resource: "source-artifact:researcher-conversation-2026-11-05-through-2026-11-07"
    title: Supervisor guidance and researcher confirmations for portfolio allocation
  - id: daily-blocks
    resource: daily-block-window-experiment.md
    title: Daily block-window SVM experiment
  - id: daily-targets
    resource: daily-binary-targets-and-holding-period.md
    title: Daily next-day binary targets and same-day exit
  - id: optimizer
    resource: https://pyportfolioopt.readthedocs.io/en/latest/MeanVariance.html
    title: PyPortfolioOpt mean-variance optimization
---

# Daily portfolio allocation

## Authority and implementation status

The researcher approved this specification and its configuration on November 7,
2026, following individual confirmations of the supervisor's proposal.
The declaration is stored in [portfolio.json](../../configs/portfolio.json).
The independent portfolio command implements allocation and backtesting from
saved inputs. The implementation plan also approves PCG64, CLARABEL and a
weight correction tolerance of 1e-8.
The current classification commands continue to consume experiment.json and
svm_grid.json. A separate portfolio declaration preserves the configuration
identity of saved upstream evidence needed by this simulation.

This decision defines the random baseline for this stage and limits its scope
to four strategies. Buy and Hold remains part of the historical proposal.
The classification protocol and its recorded failures remain the source evidence.
Forward-filled portfolio signals must retain their source prediction dates.

## Sources, calendar and signals

Use saved out-of-sample predictions from the previous training execution with
60-day outer blocks and its trained asset universe. The researcher confirmed
tuned_svc, the SVM with tuned hyperparameters, as the sole source model for
both SVM portfolio strategies. The existing LUNAUSDT
exclusion applies. The source contains the three targets 1%, 2% and 3%.
The common UTC calendar spans the first through last operation dates covered
by these predictions across the assets. Process every calendar day in this span.
Use outcome dates for operations; a prediction indexed by feature day t applies
to operation day t + 1. Prediction availability must precede its execution.

For each asset and target, select a positive SVM signal. Forward-fill an absent
prediction with the last available prediction for that asset and target,
including consecutive missing days and block transitions. Before the first
available prediction, exclude that asset from SVM selection. Preserve original
missing predictions and audit each reused signal separately.

For the random baseline, draw an independent binary signal with probability
0.5 of a positive value for each day, target and asset in the source universe.
Initialize the random generator once per simulation with seed 0. Share each
draw between minimum-variance and equal-weight allocation. Persist draws and
their ordering for reproducibility. SVM predictions do not determine the random
selection count or its cash days.

## Historical returns and allocation

For operation day D, use 60 consecutive daily values of the original feature
R1, from D - 60 through D - 1 inclusive. R1 is ln(close(t) / close(t - 1)).
Advance this window daily, including within each saved prediction block.
Use unstandardized feature values. Previously approved internally filled
candles may contribute R1 values, retaining their imputation markers.

After positive-signal selection, exclude an asset lacking the complete 60-day
R1 history. Apply this same filter to all four strategies. The matrix has one
row per day and one column per remaining selected asset.

Estimate its daily sample covariance with ddof=1, equivalent to pandas
DataFrame.cov() on the complete matrix. Use PyPortfolioOpt EfficientFrontier
with min_volatility(), minimizing w.T @ S @ w, with 0 <= w_i <= 1 and
sum(w_i) = 1. Covariance uses the daily scale without annualization.
The mean of R1 is unnecessary for this objective. Financial reporting beyond
the approved capital curves will require its own metric conventions.

Equal weighting assigns 1/N to each remaining selected asset. A single asset
receives weight 1. Each strategy invests all its available capital when its
allocation succeeds. With no remaining assets, hold all capital in cash with
zero daily return. On optimization failure or invalid weights, the affected
minimum-variance strategy holds cash for that day and retries on the next day.
Record the date, assets and failure reason.

## Execution and accumulated capital

Run independent portfolios for each strategy and target, producing 12 capital
trajectories. Each starts with 10,000 USDT. Reinvest accumulated capital each
day and carry it across prediction blocks.

Buy at the operation day's opening price, allowing fractional quantities.
Use zero transaction fees and zero slippage. If high / open - 1 >= q, sell
at open * (1 + q) and realize simple return q. Otherwise sell at that day's
close and realize close / open - 1. Every position exits on its entry day.
A target miss can produce a positive, zero or negative realized return.

For allocated capital C_i = C_previous * w_i, its end-of-day value is
C_i * (1 + r_i). The next capital balance is the sum of these values, or
the unchanged balance on a cash day. Realized labels and operation-day prices
enter only this subsequent evaluation, after signals and weights are fixed.

Use the treated opening, high and closing prices even on imputed candle days.
Retain imputation markers in operation records. These returns rely on the
approved filled-data execution assumption and must remain identifiable when
interpreting results. Preserve all upstream timestamps and source checksums.

## Outputs and source execution selection

Produce three capital-versus-time charts, one per target, each with the four
curves SVM plus minimum variance, random plus minimum variance, SVM plus equal
weights and random plus equal weights. Preserve strategy and target identities,
daily balances, signals, exclusions, weights, realized returns, cash reasons
and provenance in CSV evidence under the existing artifact policy.

The researcher approved latest-execution selection by default and subsequently
authorized explicit selection through --source-run-id.
Use execution_time_utc from execution.json to order executions. The portfolio
configuration records this dynamic selection policy, while each future portfolio
execution must record the resolved source run identifier, timestamp and checksums
so that its results remain traceable after newer training runs are created.
At specification time, the project contains one saved execution, full_01, in
outputs/experiments/daily_full_01. The source model is fixed to tuned_svc and
the source training window to 60 days. Validate the newest execution against
these requirements and report incompatible or missing inputs. An older run
must not be silently substituted. Ambiguous equal timestamps require explicit
resolution before execution.
The command validates source configuration, schemas and availability and
reports missing required inputs with their prerequisite stage.

## Execution and reporting contract

Invoke `python -m tcc_crypto.experiment portfolio --run-id portfolio_01`.
The explicit portfolio stage is independent of every classification command,
including run. The source run is selected once, either explicitly or by the default recency
policy, and recorded in its manifest.
Its UTC execution timestamp defines recency; equal timestamps are an error.

The approved implementation uses separate portfolio and backtesting calculation
modules. PCG64 is initialized once with the configured seed, drawing in ascending
operation-date order, then configured target order and historical symbol order.
Draws occur before history filtering and are shared by both allocation methods.
CLARABEL solves the sample-covariance minimum-variance problem. Raw weights are
checked for finiteness, bounds and unit sum. Residues within 1e-8 may be clipped
to the bounds and normalized, with correction recorded. Larger violations use
the approved cash rule. Configuration and input integrity errors stop execution.

An invested operation requires an observable saved target and treated candle,
including its imputation provenance. Inconsistent or absent required operation
data stop execution. The simulation performs no additional candle filling.

CSV results and their schema metadata are committed as a complete generation
under outputs/portfolios/<run_id>, protected by a directory lock. Overwrite is
explicit and requires matching configuration and source hashes. Each generation
records its environment, source context, timestamps and paths. The report loader
validates the portfolio and source graphs under their respective contexts.

[Notebook 19](../../notebooks/19_binance_daily_portfolio_results_visual_report.ipynb)
loads the saved portfolio report and constructs the three charts directly in
Portuguese cells, including the initial capital point. It displays audit counts
for cash days, repeated predictions and imputed execution candles.


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
