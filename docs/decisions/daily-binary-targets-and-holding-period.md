---
type: Methodology Decision
title: Daily next-day binary targets and same-day exit
description: Approved target thresholds and alignment from day-t inputs to the next day's D0 high-to-open outcome and same-day exit.
tags: [daily, targets, classification, holding-period, temporal-validation]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-10-09T00:00:00Z" }
sources:
  - id: silva-methodology-reference
    resource: ../references/erci_silva_2026_methodology.md
    title: Methodological reference from Silva 2026
---

# Daily next-day binary targets and same-day exit

## October 31 revision

The current target thresholds are 1%, 2% and 3%. The next-day D0 formula and same-day exit below remain applicable. Each row is dated by its features at t and labeled by the outcome at t + 1. In-sample labels support supervised fitting; out-of-sample labels are used only for later scoring. The implementation must check when training labels become known; no outer gap or target-formula change is approved.

The [Daily block-window SVM experiment](daily-block-window-experiment.md) is the
current authority for these changes. The active implementation is described in
the [implementation guide](daily-code-organization.md); the record below is historical.

## Historical decision record


The researcher recorded the following decisions from the supervisor meeting on
2026-10-09:

- construct three independent binary targets with return thresholds of `2%`,
  `3%`, and `4%` (historical; revised to 1%, 2%, and 3% on 2026-10-31), replacing the earlier proposed thresholds of `3%`, `4%`, and
  `5%`;
- use these thresholds because of the observed outcome asymmetry, the need for
  more useful class balance, and the methodological basis supplied by the
  Silva 2026 study;
- use only the `D0` outcome from the calculations represented by
  `binance_daily_future_high_returns`;
- anchor the input features on date `t` and the target on the immediately
  following daily observation, `t + 1`; and
- buy at the open of `t + 1` and evaluate the sale on that same date.

In the current future-high return implementation, `D0` for date `t` is the
simple intraday high-to-open return:

```text
D0(t) = (high(t) - open(t)) / open(t)
```

The supervisor confirmed the temporal mapping as:

```text
features(t) -> D0(t + 1)
    = (high(t + 1) - open(t + 1)) / open(t + 1)
```

For each threshold `q` in `{0.02, 0.03, 0.04}`, the label attached to the input
row at `t` is therefore:

```text
y_q(t) = 1 if D0(t + 1) >= q
         0 otherwise
```

The maximum is the Binance daily `high` field for `t + 1`, not the maximum
across a multi-day interval. The opening-price denominator is also from
`t + 1`. The label does not use `D1`, `D2`, or `D3` from the future-high return
workbook.

The purchase and exit both belong to the `t + 1` candle. This same-day D0 rule
supersedes the earlier note that the Silva 2026 four-observation holding period
would be reused for this experiment. The target is a future outcome and must
never be exposed as a feature at `t`. An input row without the required next
daily observation must remain unlabeled rather than receiving a synthetic
target.
