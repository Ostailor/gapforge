---
name: submission-package
description: Use when exporting or auditing GapForge v0.8 manuscript submission packages.
---

# Submission Package

## Purpose
Export review, camera-ready, arXiv, or internal packages only when status and blockers are explicit.

## Inputs
- Manuscript state, venue template, bibliography, figures/tables, appendix, limitations, checklist, anonymization report, artifact evaluation package, replication instructions, rebuttal/revision plan.

## Outputs
- `submission/packages/<package-id>/submission_package.json`
- manuscript Markdown/LaTeX-ready file
- bibliography/assets/appendix
- checklist, anonymization, artifact evaluation, replication instructions, package status.

## Procedure
1. Run `gapforge submission-package --manuscript-id MANUSCRIPT --type review`.
2. Use `--type camera_ready` only after fatal rebuttal blockers are addressed.
3. Inspect `gapforge submission-package-status --package-id PACKAGE`.
4. Confirm dashboard and v8 release gate show no hidden blockers.

## Package Rules
- Review package requires anonymization when the venue template requires it.
- Camera-ready requires addressed reviewer/rebuttal blockers.
- Internal packages may be less strict but must label status.
- No unsupported claims can pass submission-ready packages.

## Validation Checklist
- [ ] Bibliography and assets are included.
- [ ] Artifact evaluation README/instructions are included when available.
- [ ] Limitations and checklist report are included.
- [ ] Anonymization report is included when required.
- [ ] Package status is blocked/review_ready/submission_ready/camera_ready as evidence allows.

## Never Do
Do not export a package that hides unsupported claims, fake citations, missing artifacts, anonymization leaks, failed experiments, or open fatal rebuttal items.
