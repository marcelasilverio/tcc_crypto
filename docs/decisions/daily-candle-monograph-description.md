---
type: Methodology Decision
title: Daily candle descriptive report for the monograph
description: Approved extension of the descriptive analysis of the 40 Binance Spot USDT pairs.
tags: [binance, daily, descriptive-analysis, volatility, correlation, trading-activity]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-11-23T12:00:00Z" }
sources:
  - id: researcher-approval
    resource: "source-artifact:researcher-conversation-2026-11-23"
    title: Researcher authorization to implement the daily candle descriptive plan
  - id: approved-sample
    resource: daily-price-volume-descriptive-analysis.md
    title: Approved daily price and volume analysis
  - id: collection
    resource: daily-data-collection.md
    title: Canonical 40-pair daily collection
---

# Daily candle descriptive report for the monograph

Use the 40 canonical gzip CSVs and their JSON sidecars, in experiment
configuration order, for 2019-07-01 through 2026-09-01 inclusive in UTC. The
collection reader validates schema, clock alignment, ordering, uniqueness,
source identity and checksums. Observed valid candles are used without filling.
Localizable invalid and shortened rows are audited. Valid shortened candles
remain in the primary analysis, with a full-length-only comparison for
intraday amplitude and activity where affected.

Calendar coverage uses all study dates. Within-span coverage uses the first
through last valid dates inclusive for each pair, including invalid and
absent dates within that span. Distinguish calendar-short semesters,
asset-specific missing edges and internal gaps.

Prices and volume follow the earlier descriptive decision. The simple
return is 100 times the ratio of consecutive UTC-day closes minus 100.
Both dates must lie inside the study interval. The final date determines
the semester. Intraday amplitude is 100 times the difference between high
and low divided by the day's open. Use linear quartiles, P5 and P95,
sample variance and standard deviation, corrected sample skewness and
Fisher excess kurtosis. Volatility is the sample standard deviation of
daily returns in percentage points, at the overall, semester and 30
consecutive-return scales. Activity includes Binance trade counts and
quote volume per trade, undefined for a zero denominator. The weighted
period value is total USDT volume divided by total trades.

Compute Pearson and Spearman correlations with pair-specific date
intersection, and repeat on dates valid for all 40 assets. Use average
ranks for Spearman ties. Leave correlations undefined for constant series
or fewer than two observations. Mark support below 30 joint dates and
exclude such comparisons from narrative highlights. Always retain the
support counts and observed date bounds.

Show the two LUNAUSDT price segments around the measured gap individually.
The existing financial-continuity exclusion applies to the modeling stages.
All findings describe the selected historical Binance Spot universe.
Quote volume is an activity measure. The daily close-to-close return
and the experiment's next-day high-to-open target answer different questions.

## Reproduction

Install the project with its development dependencies and run from the repository
root. Choose a new execution identifier each time results are to be published.

```sh
TCC_DESCRIPTIVE_RUN_ID=daily_candles_reproduction PYTHONPATH="$PWD/src" python -m jupyter nbconvert --to notebook --execute notebooks/20_binance_daily_candle_descriptive_report.ipynb --output-dir /tmp
```

The notebook publishes CSV tables under `data/exploration/<run_id>/`
and figures and a manifest under `outputs/exploration/<run_id>/`.
CSV is UTF-8 with `__NULL__` for undefined or missing fields. The manifest
records ordered source identifiers, checksums, table schemas, project
revision, implementation hashes and runtime versions. It is published after
the evidence. For an interactive run, omitting the environment variable keeps
all calculations in memory.

For the editable report and its matching PDF, use Python with the
`report` optional dependencies and a LibreOffice `soffice` executable.
The builder reads the validated evidence from that one execution.

```sh
PYTHONPATH=src python scripts/build_daily_candle_report.py daily_candles_reproduction
```

Pass `--soffice /path/to/soffice` to choose a specific installation. The
builder creates a Word report, converts that same document to PDF, and
records both file checksums and the builder's checksum in the manifest.
