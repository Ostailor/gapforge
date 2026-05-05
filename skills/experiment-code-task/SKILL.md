---
name: experiment-code-task
description: Use when generating Codex implementation tasks for a GapForge experiment-ready direction.
---

# Experiment Code Task

## Purpose
Bridge an evidence-gated research direction to implementation tasks without inventing datasets, baselines, or results.

## When To Use
- After a direction reaches `experiment_ready`.
- After experiment protocol, baselines, metrics, and reproducibility checklist exist.
- Before handing implementation to Codex.

## Inputs
- Campaign ID, direction ID, experiment protocol, related-work matrix, baseline candidates, reproducibility checklist, and validation commands.

## Outputs
- `ExperimentCodeTask`s and optional experiment repo scaffold.

## Artifacts
- `experiment_code_tasks.json`
- `experiment_code_tasks.md`
- `experiment_code_tasks/<task>/CODEX_TASK.md`
- `experiment_repos/<direction>/`

## Procedure
1. Confirm direction is `experiment_ready` or explicitly allow rejected override.
2. Load protocol and related baselines.
3. Generate tasks for repo scaffold, dataset, baseline, metric, ablation, tests, and smoke run.
4. Include required files, expected outputs, and validation commands.
5. Label synthetic placeholder data clearly.
6. Do not claim experiment results exist.

## Validation Checklist
- [ ] Direction is not rejected unless override is explicit.
- [ ] Protocol includes datasets, baselines, metrics, falsification, and reproducibility.
- [ ] Every task has validation commands.
- [ ] Placeholder data is labeled.
- [ ] No fake results are written.

## Failure Modes
- Creating code tasks for a candidate direction.
- Omitting baselines.
- Writing measured claims before experiments run.
- Treating scaffold smoke tests as research results.

## Examples
```bash
gapforge generate-code-tasks --campaign-id CAMPAIGN --direction-id DIRECTION
gapforge scaffold-experiment-repo --campaign-id CAMPAIGN --direction-id DIRECTION
gapforge codex-code-task --code-task-id CODE_TASK
```

## Evidence Rules
Baseline and metric requirements should trace to protocol, related-work matrix, or reviewer objections. Do not invent citations, results, datasets, baselines, or implementation availability.

## Uncertainty Rules
If datasets or baselines are unavailable, create tasks or warnings, not claims of readiness.

## Reasoning Storage
Store public implementation rationale only. Do not store hidden chain-of-thought.

## Fake vs Real Agent Modes
Fake code tasks test generation. Real Codex implementation tasks are separate work and do not imply experiments ran.
