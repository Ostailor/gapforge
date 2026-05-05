---
name: reviewer-simulation
description: Use when attacking experiments or research directions for novelty, baselines, metrics, theory, reproducibility, ethics, and rebuttal readiness.
---

# Reviewer Simulation

## Purpose
Attack proposed experiments and directions like serious reviewers. The goal is actionable rejection-risk discovery, not encouragement.

## When To Use
- After experiment plans/protocols.
- Before final recommendation, direction maturation to manuscript-ready, or manuscript export.
- CLI: `gapforge review --run-id RUN_ID`, `gapforge review-panel --project-id PROJECT --direction-id DIRECTION`.

## Inputs
- experiments or directions
- novelty assessments/dossiers
- related-work matrix
- experiment protocol
- claim ledger/claim graph
- paper notes and evidence

## Outputs
- `ReviewerObjection`
- `ReviewPanel`
- `ReviewerReview`
- `RebuttalPlan`
- `reviewer_simulation.md`
- `review_panel.md`
- `rebuttal_plan.md`
- `meta_review.md`

## Required Artifacts
- `experiments.json` or `research_directions.json`
- `novelty_dossiers.json`
- `related_work_matrix.json` when available
- `experiment_protocols.json` when available
- review Markdown/JSON artifacts

## Procedure
1. Simulate technical, novelty, empirical, theory, ethics, and area-chair perspectives.
2. Check unsupported novelty first; it is fatal.
3. Check missing baselines and missing metrics; these are major or fatal.
4. Check dataset validity, scaling, reproducibility, statistical tests, ethics, and clarity.
5. Link objections to evidence/prior work when possible.
6. Provide concrete required fixes and optional fixes.
7. Build rebuttal plans that request evidence or additional experiments, not fake results.

## Citation and Evidence Rules
- Reviewer evidence should cite paper IDs, dossiers, matrices, protocols, or claim IDs.
- Do not invent reviewer citations or results.
- Do not use query-only analogies as proof.

## Uncertainty Rules
- Abstract-only critique should say so.
- Missing protocol should block readiness.
- Unresolved claim contradictions should raise decision risk.

## Validation Checklist
- [ ] Objections are specific and actionable.
- [ ] Missing baselines are major/fatal.
- [ ] Unsupported novelty is fatal.
- [ ] Rebuttal plan does not invent evidence.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Generic feedback.
- Recommending submission despite fatal blockers.
- Ignoring related-work omissions.
- Drafting fake rebuttal evidence.

## Examples
```bash
gapforge review --run-id RUN_ID
gapforge review-panel --project-id PROJECT --direction-id DIRECTION
gapforge rebuttal-plan --project-id PROJECT --direction-id DIRECTION
```
