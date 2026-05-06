---
name: experiment-workspace
description: Use when creating or inspecting GapForge v0.6 experiment workspaces, run manifests, executions, logs, and result artifacts.
---

# Experiment Workspace

## Purpose
Create durable experiment state without confusing a protocol or scaffold with an executed experiment.

## When To Use
- A direction is `experiment_ready` and needs an execution workspace.
- A smoke, pilot, main, ablation, negative-control, or reproduction run needs a manifest.
- A user asks whether an experiment actually ran.

## Inputs
- Project ID, direction ID, optional campaign/protocol ID.
- Dataset, baseline, and metric IDs.
- Command, config path, expected outputs, random seed, and environment notes.

## Outputs
- `ExperimentWorkspace`
- `ExperimentRunManifest`
- `ExperimentExecutionRecord`
- `ExperimentResultArtifact`

## Required Artifacts
- `experiment_workspaces/{workspace_id}/workspace.json`
- `manifests/{manifest_id}.json`
- `runs/{execution_id}.json`
- `logs/{execution_id}.stdout.txt`
- `logs/{execution_id}.stderr.txt`
- `results/result-*.artifact.json`

## Procedure
1. Confirm the direction is experiment-ready or record why this is a scaffold-only workspace.
2. Create the workspace with `gapforge experiment-workspace-create`.
3. Register datasets, baselines, and metrics before creating a meaningful manifest.
4. Create a manifest with run type, command, expected outputs, seed, and IDs.
5. Run with `gapforge experiment-run`; never mark executed manually.
6. Inspect status and missing outputs before parsing results.

## Validation Checklist
- [ ] Workspace root exists and is ignored/generated.
- [ ] Manifest records command, expected outputs, run type, and seed.
- [ ] Execution record has status, return code, stdout/stderr paths, and failure reason if failed.
- [ ] Result artifacts have hashes.
- [ ] Smoke/pilot/main/failed labels are visible.

## Failure Modes
- Treating a scaffold as an executed experiment.
- Command exits 0 but produces no expected artifact.
- Missing output path is ignored.
- Failed or negative run is hidden from reports.

## Examples
```bash
gapforge experiment-workspace-create --project-id PROJECT --direction-id DIRECTION
gapforge experiment-manifest-create --workspace-id WORKSPACE --run-type smoke --command "python code/src/run_experiment.py" --expected-output results/smoke_metrics.json --random-seed 123
gapforge experiment-run --workspace-id WORKSPACE --manifest-id MANIFEST
```

## Evidence Rules
Execution evidence means manifest plus execution record plus logs. Result evidence additionally requires result artifact metadata.

## Uncertainty Rules
If outputs are missing or the command failed, mark status failed/incomplete and preserve logs.

## Chain-Of-Thought Rule
Store only public reasoning summaries. Do not request or store hidden chain-of-thought.

## No Fake Results
Do not create metrics, plots, logs, or result claims unless an execution actually produced the artifact.
