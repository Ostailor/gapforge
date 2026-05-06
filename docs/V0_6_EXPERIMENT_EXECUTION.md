# v0.6 Experiment Execution

v0.6 makes experiment execution a first-class, auditable workflow. The core distinction is simple: a protocol proposes an experiment; a run record proves that something was actually executed.

## Execution Lifecycle

1. Select an experiment-ready direction.
2. Create an experiment workspace.
3. Generate Codex code tasks for datasets, baselines, metrics, ablations, tests, and smoke commands.
4. Validate dataset, baseline, and metric registries.
5. Create a run manifest.
6. Execute a smoke run or real run.
7. Capture logs and result artifacts.
8. Run statistical analysis.
9. Run reproducibility checks.
10. Update the result claim ledger.
11. Run empirical reviewer simulation.
12. Export an updated paper package.

## Experiment Workspace

An experiment workspace should be created under an ignored project/campaign artifact directory and include:

- source code and configuration files
- dataset card registry
- baseline registry
- metric registry
- run manifests
- logs
- result artifacts
- analysis outputs
- reproducibility reports

Generated workspaces are not automatically safe to commit. Users should export a safe bundle when sharing results.

Create and inspect a workspace:

```bash
gapforge experiment-workspace-create --project-id <project-id> --direction-id <direction-id>
gapforge experiment-workspace-status --workspace-id <workspace-id>
```

Register the empirical ingredients before running:

```bash
gapforge dataset-register --workspace-id <workspace-id> --name "fixture examples" --path data/fixture.csv --dataset-type fixture --license MIT
gapforge dataset-validate --dataset-id <dataset-id>
gapforge baseline-register --workspace-id <workspace-id> --name "heuristic baseline" --baseline-type heuristic --implementation-path code/src/baselines.py
gapforge metric-register --workspace-id <workspace-id> --name "false positive rate"
gapforge stats-plan --workspace-id <workspace-id>
```

## Codex Code Tasks

Codex/GPT-5.4 may generate experiment code tasks, but it must not invent datasets, results, or unavailable baseline implementations.

Task types should include:

- scaffold repository
- implement dataset adapter
- implement baseline
- implement metric
- implement ablation
- write tests
- run smoke command
- produce analysis script

Every task should include:

- required input artifacts
- output files
- validation commands
- allowed dataset/baseline/metric IDs
- rules against fabricated results
- instructions to label placeholders clearly

Codex code task boundaries:

- code changes must stay under the experiment workspace, normally `code/`
- task output is implementation material, not empirical evidence
- Codex may add tests, loaders, baselines, metrics, runners, and analysis scripts
- Codex must not write fake `metrics.json`, fake plots, fake p-values, or fake confidence intervals to make a run look complete
- generated placeholder data must be labeled fixture/synthetic/generated

## Run Manifest

A run manifest should record:

- experiment protocol ID
- direction ID
- code revision or workspace hash
- command executed
- configuration file
- dataset versions
- baselines enabled
- metrics enabled
- random seeds
- environment summary
- expected output paths
- started/completed timestamps
- run type: smoke / fixture / real

Without a run manifest, an experiment is not executed.

```bash
gapforge experiment-manifest-create \
  --workspace-id <workspace-id> \
  --run-type smoke \
  --command "python code/src/run_experiment.py" \
  --expected-output results/smoke_metrics.json \
  --random-seed 123
```

## Execution Logs

Execution logs should record:

- status: planned / running / succeeded / failed / cancelled
- command
- duration
- stdout/stderr summary
- error trace excerpt when failed
- generated artifact paths
- warnings
- provenance

If the command exits successfully but does not produce expected result artifacts, the run should be marked failed or incomplete.

```bash
gapforge experiment-run --workspace-id <workspace-id> --manifest-id <manifest-id>
gapforge experiment-run-status --execution-id <execution-id>
gapforge experiment-rerun --execution-id <execution-id>
```

## Result Artifacts

Result artifacts may include:

- metrics JSON
- tables
- plots
- raw predictions or outputs
- analysis reports
- error analyses
- negative control outputs

Result artifacts must be linked to run manifests and result claims. A claim cannot be empirical-supported without at least one result artifact.

## Smoke Runs

Smoke runs validate wiring and artifact production only. They can support engineering readiness, but not empirical claims about a research hypothesis.

Reports and paper packages must label smoke outputs as smoke outputs.

## Pilot, Main, Failed, and Negative Runs

- `pilot`: exploratory. Useful for debugging design and variance; not a final claim.
- `main`: intended empirical run. Claims still require result artifacts, parsing, analysis, and reproducibility checks.
- `ablation`: isolates design components. Must cite the manifest and artifacts.
- `negative_control`: validates that the pipeline does not create false success.
- `reproduction`: reruns a prior result or baseline. Must record environment and data versions.
- `failed`: command failed, timed out, or missed expected outputs. Logs and failure reason must remain visible.
- `negative`: command completed but result does not support the hypothesis. It is a valid outcome, not a hidden error.

After execution:

```bash
gapforge parse-results --execution-id <execution-id>
gapforge result-summary --execution-id <execution-id>
gapforge analyze-results --execution-id <execution-id>
gapforge reproducibility-check --execution-id <execution-id>
gapforge empirical-review --execution-id <execution-id>
gapforge export-paper-package-v2 --workspace-id <workspace-id>
```
