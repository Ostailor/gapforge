---
name: empirical-reviewer
description: Use when reviewing GapForge v0.6 experiment results for empirical rigor, statistics, reproducibility, baselines, and overclaim.
---

# Empirical Reviewer

## Purpose
Attack executed experiment outputs before they become paper-package claims.

## When To Use
- After result parsing/statistical analysis.
- Before paper package v2 export.
- When a failed or negative run needs reviewer interpretation.

## Inputs
- Experiment protocol, execution records, result summaries, statistical analysis, reproducibility checks, related-work matrix, novelty dossier.

## Outputs
- `EmpiricalReviewPanel`
- required fixes
- fatal flaws
- rebuttal plan
- result-claim softening recommendations

## Required Artifacts
- `reports/empirical_review.json`
- `reports/empirical_review.md`
- result summaries and reproducibility reports

## Procedure
1. Review empirical rigor, statistics, reproducibility, novelty-with-results, and area-chair risk.
2. Flag missing baselines, missing result artifacts, failed runs, missing CIs, and irreproducibility.
3. Recommend fixes: add baseline, rerun, add ablation, soften claim, report failure, or request human review.
4. Do not turn reviewer feedback into fake rebuttal evidence.

## Validation Checklist
- [ ] No result artifact is fatal for empirical claims.
- [ ] Failed execution is not accepted as success.
- [ ] Low-FPR missing CI is major/fatal.
- [ ] Missing required baseline is major/fatal.
- [ ] Required fixes are actionable.

## Failure Modes
- Reviewer invents results or citations.
- Negative result is reframed as success.
- Missing baseline is treated as minor.

## Examples
```bash
gapforge empirical-review --execution-id EXECUTION
gapforge empirical-review --workspace-id WORKSPACE
```

## Evidence Rules
Reviewer objections cite protocol fields, execution IDs, result artifact IDs, metric results, reproducibility blockers, or known prior work.

## Uncertainty Rules
If evidence is missing, mark fatal/uncertain rather than assuming success.

## Chain-Of-Thought Rule
Store only public reasoning summaries. Do not request or store hidden chain-of-thought.

## No Fake Results
Do not invent experiment outcomes, added experiments, reviewer citations, or rebuttal evidence.
