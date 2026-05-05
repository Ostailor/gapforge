---
name: reviewer-simulation
description: Use when attacking proposed experiments for novelty, baselines, metrics, datasets, theory, clarity, scaling, reproducibility, or ethics before recommending submission.
---

# Reviewer Simulation

## Purpose
Attack each proposed experiment like a serious conference reviewer. The goal is to find fatal weaknesses before GapForge recommends an idea.

## When To Use
- Use after experiment design.
- Use before final recommendation or report generation.
- CLI: `gapforge review --run-id RUN_ID` or `gapforge review --experiment-id EXPERIMENT_ID`.

## Inputs
- `ExperimentPlan` records
- `NoveltyAssessment` records
- claim ledger
- `PaperNote` records

## Outputs
- `ReviewerObjection` records
- `reviewer_objections.json`
- `reviewer_summaries.json`
- `reviewer_simulation.md`
- `revised_experiment_recommendations.md`

## Required Artifacts
- `experiments.json`
- `novelty_gate.json`
- `claims.json`
- `paper_notes.json`
- `reviewer_objections.json`
- `reviewer_simulation.md`
- `revised_experiment_recommendations.md`

## Procedure
1. Simulate four perspectives:
   - Reviewer 1: technical correctness
   - Reviewer 2: novelty skeptic
   - Reviewer 3: empirical rigor and baselines
   - Area Chair: positioning and contribution clarity
2. Check novelty support first. Unsupported novelty is fatal.
3. Check baselines. Missing baselines are major or fatal.
4. Check metrics, datasets, statistical tests, ablations, reproducibility, scaling, and ethics.
5. For each objection, record why a reviewer would care, evidence or prior work, suggested fix, whether it blocks submission, and confidence.
6. Produce readiness score, blocking issues, required fixes, optional fixes, and final recommendation.
7. Attack the idea before recommending it.

## Quality Bar
- Objections must be specific to the experiment, not generic advice.
- Every objection must include a concrete fix.
- Fatal and major issues must block submission.
- Do not invent reviewer evidence, citations, or results.
- Mark uncertainty when the critique depends on abstract-only notes.

## Failure Modes
- Giving encouraging feedback without stress-testing the idea.
- Missing unsupported novelty.
- Accepting weak or absent baselines.
- Recommending conference submission despite blocking issues.
- Producing vague fixes like "improve evaluation".

## Validation Checklist
- [ ] `reviewer_simulation.md` exists.
- [ ] `revised_experiment_recommendations.md` exists.
- [ ] Each objection has severity, category, evidence, fix, and blocking flag.
- [ ] Missing baselines are major or fatal.
- [ ] Unsupported novelty is fatal.
- [ ] Final recommendation is one of `not_ready`, `workshop_ready`, `conference_potential`, or `strong_submission_candidate`.

## Examples
Review all experiments:

```bash
gapforge review --run-id 20260505T002206Z-low-false-positive-collusion-detection
```

Review one experiment:

```bash
gapforge review --run-id 20260505T002206Z-low-false-positive-collusion-detection --experiment-id experiment-1
```
