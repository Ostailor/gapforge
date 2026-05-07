---
name: venue-submission-checklist
description: Use when assigning GapForge v0.8 venue templates or checking manuscript submission readiness.
---

# Venue Submission Checklist

## Purpose
Make submission readiness venue-aware while failing closed on missing requirements.

## Inputs
- Manuscript state, target venue template, sections, bibliography, traceability report, result artifacts, artifact package, limitations, ethics, anonymization report.

## Outputs
- `submission/venue_template.json`
- `submission/submission_checklist.json`
- `submission/submission_checklist.md`

## Procedure
1. List templates with `gapforge venue-list`.
2. Set a template with `gapforge manuscript-set-venue --manuscript-id MANUSCRIPT --venue generic_conference`.
3. Build the checklist with `gapforge submission-checklist --manuscript-id MANUSCRIPT`.
4. Treat blockers as submission-not-ready.
5. Re-run after bibliography, traceability, artifact package, or anonymization changes.

## Template Rules
- Generic conference/workshop templates are deterministic fixtures, not real venue policy guarantees.
- arXiv-like templates are less strict but still require honest claims and citations.
- LaTeX installation is not required in CI.

## Validation Checklist
- [ ] Required sections are present.
- [ ] Bibliography exists and citations are valid.
- [ ] Traceability passes.
- [ ] Result artifacts exist for result claims.
- [ ] Artifact package exists when required/expected.
- [ ] Limitations and ethics are handled.
- [ ] Anonymization passes when required.

## Never Do
Do not mark submission-ready with unsupported claims, fake citations, hidden results, or anonymization leaks.
