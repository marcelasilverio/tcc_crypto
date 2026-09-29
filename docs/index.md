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
6. `docs/reports/` as point-in-time evidence about executed work.

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
- [Generated reports](reports/) - Point-in-time evidence from collection and
  validation work.

## Deprecated paths

- [Legacy methodology decision register](methodology_decisions.md) - Deprecated path retained for links created before the OKF migration.
