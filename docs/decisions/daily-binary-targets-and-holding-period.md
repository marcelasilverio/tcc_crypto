---
type: Methodology Decision
title: Daily binary targets and holding period
description: Approved target thresholds, daily high-to-open outcome source, and Silva-based holding period, with final temporal alignment pending.
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

# Daily binary targets and holding period

The researcher recorded the following decisions from the supervisor meeting on
2026-10-09:

- construct three independent binary targets with return thresholds of `2%`,
  `3%`, and `4%`, replacing the earlier proposed thresholds of `3%`, `4%`, and
  `5%`;
- use these thresholds because of the observed outcome asymmetry, the need for
  more useful class balance, and the methodological basis supplied by the
  Silva 2026 study;
- use only the `D0` outcome from the calculations represented by
  `binance_daily_future_high_returns`; and
- adopt the same four-daily-observation holding period used by Silva 2026.

In the current future-high return implementation, `D0` for date `t` is the
simple intraday high-to-open return:

```text
D0(t) = (high(t) - open(t)) / open(t)
```

For each threshold `q` in `{0.02, 0.03, 0.04}`, the corresponding binary label
derived from a selected outcome is `1` when the return is greater than or equal
to `q` and `0` otherwise. The maximum in this formula is the Binance daily
`high` field used by the existing future-high return calculation; it is not a
feature available before that candle has completed.

## Pending temporal alignment confirmation

The researcher also recorded that inputs are anchored on day 1 and the target
is based on day 2. The supervisor is being asked to confirm the exact alignment.
The two materially different interpretations are:

```text
features(t) -> D0(t + 1)
    = (high(t + 1) - open(t + 1)) / open(t + 1)
```

and:

```text
D1(t)
    = (high(t + 1) - open(t)) / open(t)
```

The first interpretation is consistent with selecting only `D0` and shifting
that outcome to the preceding feature row. The second uses the next day's high
but corresponds to `D1`, not `D0`, in the current implementation.

The final target configuration must also reconcile the selection of only `D0`
with the separately approved four-observation holding period. No target
pipeline should be described as final until the supervisor confirms whether
the four-day period belongs to label construction, trade accounting, or both.
The final observation and any row whose required future horizon is incomplete
must not be assigned a synthetic label.
