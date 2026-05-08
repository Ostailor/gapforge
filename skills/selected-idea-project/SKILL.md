---
name: selected-idea-project
description: Use when locking a v2 accepted idea or converting it into a v2.1 selected-idea research project.
---

# Selected Idea Project

## Purpose

Freeze the accepted v2 idea and make it the canonical v2.1 research target without silent drift.

## Workflow

1. Confirm the accepted idea ID is `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`.
2. Run `gapforge selected-idea-lock --idea-id <idea-id>`.
3. Run `gapforge selected-idea-project-create --idea-id <idea-id>`.
4. Inspect `gapforge selected-idea-status --project-id <selected-project-id>`.
5. Preserve rejected ideas, tournament score, human acceptance, and provenance.

## Discipline Rules

- Synthetic smoke benchmark is not a final research result.
- Low-FPR claims require power before they can support strong conclusions.
- Project status must distinguish locked, benchmark-ready, smoke-validated, pilot-validated, and manuscript-ready.
- Every downstream claim must be artifact-backed.
- No fake results, fake citations, or silent replacement ideas.

## Common Failure

Do not treat project creation as benchmark validity. It only records the target and provenance.
