---
okf_version: "0.2"
---

# Cryptocurrency portfolio research knowledge

This directory is an Open Knowledge Format v0.2 bundle for the research
context, approved methodology decisions, external references, and generated
evidence used by this repository.

## Authority order

When documents differ, use this order of authority:

1. `AGENTS.md` for mandatory repository and research safeguards;
2. `docs/decisions/` for choices confirmed by the researcher;
3. the experiment configuration for parameters of a particular run;
4. `docs/tcc/` as background and evidence of intended design;
5. `docs/references/` for comparison and adaptation;
6. historical reports in Git as point-in-time evidence about executed work.

The OKF `verified` field records that a human reviewed the document against its
intended source and purpose. It does not make a proposal or external reference
an approved methodology decision. The local `authority` field carries that
distinction. Only documents with `authority: approved-methodology` record
approved experimental choices.

## Knowledge groups

- [Methodology decisions](decisions/) - Approved choices for data collection
  and exploratory analysis.
- [TCC I research context](tcc/) - Structured synopsis of the research proposal.
- [External references](references/) - Methodologies analyzed for comparison,
  not automatic adoption.
## Current experiment revision

The [daily portfolio allocation decision](decisions/daily-portfolio-allocation.md)
records the approved next stage and its separate portfolio configuration.
Its independent portfolio command reads saved training evidence and produces
CSV results for the dedicated metrics notebook.

The [daily block-window SVM decision](decisions/daily-block-window-experiment.md)
records the October 31 corrections and later confirmations. The
[CSV artifact organization](decisions/csv-artifact-organization.md) defines the
approved simplified folders and CSV-only tabular outputs. Its
[experiment diagram](decisions/daily-block-window-experiment-diagram.md) maps the
implemented workflow. The [implementation guide](decisions/daily-code-organization.md)
explains the active modules, commands and CSVs. Historical results belong to the
previous protocol; implementation tests do not constitute a production experiment.

Historical artifacts and reports are retained only in Git under the
[history retention decision](decisions/git-only-history-retention.md).

## Deprecated paths

- [Legacy methodology decision register](methodology_decisions.md) - Deprecated path retained for links created before the OKF migration.
