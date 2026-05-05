---
name: experiment-designer
description: Use when converting novelty-checked gaps or mature directions into falsifiable experiment plans, protocols, baselines, and reproducibility checklists.
---

# Experiment Designer

## Purpose
Convert validated research gaps or directions into concrete experiments and v0.3 protocols. Prefer decisive tests that can falsify the idea.

## When To Use
- After novelty dossiers.
- After related-work matrix when designing v0.3 protocols.
- CLI: `gapforge design-experiments --run-id RUN_ID`, `gapforge experiment-protocol --project-id PROJECT --direction-id DIRECTION`.

## Inputs
- gaps
- novelty assessments/dossiers
- related-work matrix
- paper notes/evidence
- claim ledger
- direction maturity state

## Outputs
- `ExperimentPlan`
- `ExperimentProtocol`
- `BaselineCandidate`
- `ReproducibilityChecklist`
- `experiments.json`
- `experiments.md`
- `experiment_protocols.json`
- `experiment_protocols.md`

## Required Artifacts
- `gaps.json`
- `novelty_dossiers.json`
- `related_work_matrix.json` when available
- `experiments.json`
- `experiment_protocols.json` for v0.3 protocols

## Procedure
1. Skip rejected novelty assessments and human-rejected gaps by default.
2. Select gaps/directions with measurable claims and non-rejected novelty.
3. State hypothesis and core claim being tested.
4. Define minimum viable experiment, datasets, baselines, metrics, statistical tests, ablations, failure modes, compute, implementation steps, and falsification condition.
5. Pull required baselines from related-work matrix.
6. Add reproducibility checklist: seeds, dataset versions, environment, logging, metric definitions, negative controls, error analysis.
7. Do not mark paper-ready without protocol and reviewer checks.

## Citation and Evidence Rules
- Baselines should cite paper IDs.
- Do not invent datasets, benchmark scores, code URLs, or results.
- Expected result patterns are hypothetical until experiments run.
- Use claim IDs and evidence locators for tested claims.

## Uncertainty Rules
- Missing baselines or poor novelty lowers readiness.
- Data availability and compute assumptions should be explicit risks.
- If source coverage is weak, recommend search steps before experiments.

## Validation Checklist
- [ ] Every experiment has baselines, metrics, and falsification condition.
- [ ] Rejected gaps are skipped unless explicitly allowed.
- [ ] Protocol includes reproducibility and statistics notes.
- [ ] Publishability criteria are concrete.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Vague agenda instead of executable protocol.
- Missing closest-prior-work baseline.
- Paper-ready label without novelty/protocol support.
- Fake results in expected outcomes.

## Examples
```bash
gapforge design-experiments --run-id RUN_ID
gapforge related-work-matrix --project-id PROJECT --direction-id DIRECTION
gapforge experiment-protocol --project-id PROJECT --direction-id DIRECTION
```
