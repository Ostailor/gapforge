---
name: manuscript-planner
description: Use when creating or planning a GapForge v0.8 manuscript project from project, direction, campaign, or workspace state.
---

# Manuscript Planner

## Purpose
Create a durable manuscript project without implying the research is submission-ready.

## Inputs
- Project ID, direction ID, workspace ID, optional campaign ID.
- Direction maturity, novelty dossiers, related-work matrix, experiment workspace, result artifacts, limitations, and reviewer blockers.

## Outputs
- `ManuscriptState`
- `manuscripts/<manuscript-id>/manuscript.json`
- section directories for future draft, assets, bibliography, reviews, submission, and artifact evaluation.

## Procedure
1. Confirm the project, direction, and workspace already exist.
2. Create state with `gapforge manuscript-create --project-id PROJECT --direction-id DIRECTION --workspace-id WORKSPACE --title "..."`.
3. Record the target venue only as a template profile, not as acceptance.
4. Add sections and claim links before drafting strong prose.
5. Keep project evidence, result state, and manuscript state separate.
6. Run dashboard or status commands to expose blockers.

## Readiness Rules
- Manuscript-ready: durable draft/state exists and may have blockers.
- Review-ready: internal reviewer/artifact checks exist.
- Submission-ready: venue checklist, citation validity, traceability, artifact, anonymization, and reviewer gates pass.
- Camera-ready: reviewer/rebuttal blockers are addressed after an explicit external trigger.

## Validation Checklist
- [ ] Manuscript ID is durable.
- [ ] Project/direction/workspace IDs resolve.
- [ ] Known blockers are visible.
- [ ] No unsupported novelty, result, or venue claim is added.

## Never Do
Do not fabricate results, citations, venue status, reviewer acceptance, or novelty. Do not hide failed/negative experiments.
