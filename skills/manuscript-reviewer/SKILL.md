---
name: manuscript-reviewer
description: Use when running or interpreting GapForge v0.8 full-manuscript reviewer panels and fix lists.
---

# Manuscript Reviewer

## Purpose
Attack the manuscript before submission and produce evidence-linked objections.

## Inputs
- Manuscript draft/state, traceability report, bibliography, related-work matrix, novelty dossier, result artifacts, reproducibility report, artifact package, submission checklist.

## Outputs
- `reviews/manuscript_review_panel.json`
- reviewer reports
- area-chair summary
- meta-review
- fix list
- rebuttal plan seed.

## Procedure
1. Run `gapforge manuscript-review --manuscript-id MANUSCRIPT`.
2. Inspect `gapforge manuscript-meta-review --manuscript-id MANUSCRIPT`.
3. Inspect `gapforge manuscript-fix-list --manuscript-id MANUSCRIPT`.
4. Treat missing baselines, unsupported claims, missing artifact packages, missing related work, and reproducibility gaps as major/fatal.
5. Convert issues into rebuttal/revision items.

## Reviewer Roles
- novelty reviewer
- empirical reviewer
- clarity reviewer
- related-work reviewer
- reproducibility/artifact reviewer
- ethics/limitations reviewer
- area chair

## Validation Checklist
- [ ] Objections cite sections or evidence.
- [ ] Fatal flaws block readiness.
- [ ] Required fixes are concrete.
- [ ] Reviewer does not invent experiments.

## Never Do
Do not treat reviewer simulation as acceptance prediction. Do not invent reviewer agreement, citations, or results.
