# TCC I research context

This directory translates and restructures the research proposal in
`tcc-corrigido-final.pdf` into concise Markdown context for repository agents.
The source is a 69-page TCC I manuscript titled *Machine Learning Applied to
Cryptocurrency Portfolio Selection*, authored by Marcela Prata Silverio at
CEFET-MG in 2026.

These files are a faithful research synopsis, not a replacement for the source
manuscript and not evidence that the proposed experiment has already been run.
The manuscript is predominantly written in the future tense and contains no
empirical results.

## Reading order

1. [Research scope](01_research_scope.md) - Scope, objectives, contribution, and boundaries of the TCC I proposal.
2. [Conceptual foundations](02_conceptual_foundations.md) - Cryptocurrency, portfolio-theory, and SVM foundations for the proposed experiment.
3. [Experimental methodology](03_experimental_methodology.md) - Proposed experimental pipeline and temporal safeguards from the TCC I manuscript.
4. [Features and targets](04_features_and_targets.md) - Proposed feature definitions, decision variables, and binary return targets.
5. [Strategies and evaluation](05_strategies_and_evaluation.md) - Proposed portfolio strategies, evaluation metrics, and backtest timing requirements.
6. [Literature context](06_literature_context.md) - Related-work themes and methodological anchors identified in the TCC I review.
7. [Open decisions and source caveats](07_open_decisions_and_source_caveats.md) - Unresolved experimental choices and inconsistencies in the TCC I source.

## Authority and interpretation

When sources differ, agents must apply this order of authority:

1. `AGENTS.md` for mandatory repository and research safeguards;
2. `docs/decisions/index.md` for choices explicitly approved by the researcher;
3. the experiment configuration for the parameters of a particular run;
4. this TCC I synopsis as background and evidence of the intended design;
5. the source PDF for wording, citations, and details not reproduced here.

Statements marked **proposed** describe the manuscript's intended design but
are not automatically approved implementation parameters. Statements marked
**unresolved** require an explicit researcher decision before implementation.

## Provenance

- Source filename: `tcc-corrigido-final.pdf`
- Source length: 69 PDF pages
- Source creation date: June 10, 2026
- SHA-256: `f90b1cc54bc105e4eab96d8aed4ff7f9f16eb9545566ccd820fb7c4144c1da7a`
- Conversion date: September 2, 2026
- Conversion language: English, as required for repository content

Page references in these documents refer to PDF pages, not the printed page
numbers. Reviewer comments visible in the PDF were treated as annotations, not
as instructions.

## Related methodological reference

The repository also contains an analysis of the completed process described in
Ercilene Micaela Brito da Silva's 2026 master's dissertation:
[Methodological reference from Silva 2026](../references/erci_silva_2026_methodology.md).
It is a reference for comparison and adaptation, not an approved specification
for the cryptocurrency experiment.

## Deprecated paths

- [Legacy TCC I research-context index](README.md) - Deprecated path retained for links created before the OKF migration.
