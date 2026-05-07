---
name: rebuttal-planner
description: Use when converting GapForge v0.8 manuscript reviewer objections into rebuttal and revision plans.
---

# Rebuttal Planner

## Purpose
Turn reviewer objections into actionable fixes without inventing answers.

## Inputs
- Manuscript reviewer panel, fatal flaws, required fixes, traceability warnings, missing citations, missing experiments, overstrong claims.

## Outputs
- `reviews/rebuttal_items.json`
- `reviews/revision_plan.json`
- actionable rebuttal Markdown.

## Procedure
1. Run `gapforge rebuttal-plan --manuscript-id MANUSCRIPT`.
2. Run `gapforge revision-plan --manuscript-id MANUSCRIPT`.
3. For each item, classify needed evidence, experiments, citations, searches, or claim softening.
4. Mark items only after real fixes: `gapforge mark-rebuttal-item --item-id ITEM --status addressed`.
5. Check status with `gapforge revision-status --manuscript-id MANUSCRIPT`.

## Response Rules
- Missing experiment: create/request experiment; do not state an outcome.
- Missing citation: create search/citation request; do not invent a reference.
- Overstrong claim: suggest softer wording.
- Valid limitation: concede it visibly.
- Open/deferred fatal items block camera-ready packages.

## Validation Checklist
- [ ] Every objection has a strategy.
- [ ] Evidence/citation/experiment needs are explicit.
- [ ] Open blockers remain visible.
- [ ] Camera-ready is blocked until fatal items are addressed.

## Never Do
Do not fabricate rebuttal evidence, reviewer agreement, new results, citations, or acceptance.
