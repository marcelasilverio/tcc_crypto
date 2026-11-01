---
type: Methodology Decision
title: Git-only retention of historical experiment files
description: Approved removal of superseded local artifacts and reports while preserving raw data and historical Git references.
tags: [organization, history, reproducibility, cleanup]
status: draft
authority: approved-methodology
decision_status: approved
generated: { by: "process:codex", at: "2026-11-01T12:00:00Z" }
sources:
  - id: researcher-cleanup
    resource: "source-artifact:researcher-cleanup-approval-2026-11-01"
    title: Researcher approval of historical cleanup including Markdown reports
  - id: preserved-revision
    resource: https://github.com/marcelasilverio/tcc_crypto/tree/855e32eb9d248f1e36796bd09dd7233210d10d54
    title: Complete repository revision before cleanup
---

# Git-only retention of historical experiment files

On November 1 the researcher approved removing superseded artifacts from the
working tree because their historical commits already preserve them. This
supersedes earlier requirements to keep local archive directories and manifests.

Remove historical source/configuration/notebook/test snapshots, calculated
tables, spreadsheets, model artifacts, figures, PDF reports and old Markdown
reports. Remove the historical migration script and its dedicated test. Keep
the current package, configurations, presentation notebook, collection tests,
methodological decisions, external references and TCC context.

All contents of data/raw remain intact, including metadata and Excel files.
Before deletion, verify that historical file bytes match the preserved revision.
Compare the raw file list and SHA-256 checksums before and after cleanup.
Retain necessary scientific provenance using links pinned to the full historical
commit identifier. Do not rewrite Git history or alter human verification entries.

This is a repository organization decision. It changes no scientific formulas,
parameters, temporal validation rules or preprocessing behavior. Commit and push
require a separate explicit request.
