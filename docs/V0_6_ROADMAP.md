# GapForge v0.6 Roadmap

v0.6 is the experiment execution and empirical validation release.

v0.5 can produce an experiment-ready research direction after live-literature search, closest-prior-work recall, related-work structure, and human quality review. v0.6 moves the next boundary from "this direction has a plausible protocol" to "this experiment was executed, logged, statistically analyzed, and packaged reproducibly."

v0.6 must not weaken the v0.5 literature, novelty, or human-review gates. It adds empirical execution only after a direction has enough evidence to justify running an experiment.

## Why v0.6 Exists

GapForge currently distinguishes hypotheses, protocols, and manuscript starter kits, but it does not make empirical results first-class. This leaves an important safety gap: a report can say an experiment is ready, but not whether it actually ran, what data/code was used, what failed, or which claims are supported by results.

v0.6 makes empirical status auditable:

- planned protocol
- generated code scaffold
- smoke run
- executed experiment
- failed or negative experiment
- statistically analyzed result
- reproducible result package

These states are not interchangeable. A protocol or scaffold may justify implementation work, a smoke run may justify debugging confidence, and an executed pilot/main run may support empirical claims only when linked result artifacts exist.

## Must-Have

- Experiment workspace creation from an experiment-ready direction.
- Codex-generated experiment code tasks with validation commands.
- Dataset registry and dataset cards.
- Baseline registry and baseline cards.
- Metric registry with metric definitions and acceptable use cases.
- Run manifests that record code, config, data, environment, seeds, and commands.
- Experiment execution logs with stdout/stderr summaries, status, duration, and artifact paths.
- Result artifacts for tables, metrics, plots, raw outputs, and analysis summaries.
- Statistical analysis module for confidence intervals, hypothesis tests, multiple-comparison notes, and uncertainty summaries.
- Reproducibility checks for rerunnable commands, environment spec, dataset versions, random seeds, and artifact completeness.
- Result claim ledger that separates literature claims from empirical result claims.
- Negative-result and failed-experiment records.
- Empirical reviewer simulation that attacks design, baselines, metrics, leakage, statistics, and reproducibility.
- Paper package upgrade that separates real results from placeholders, expected results, and hypotheses.

## Should-Have

- Lightweight local execution adapter for small fixture experiments.
- Configurable external runner interface for larger jobs.
- Dry-run mode that validates workspace readiness without running expensive code.
- Result comparison across repeated runs.
- Compute budget estimates and run-cost notes.
- Dataset licensing and access warnings.
- Artifact safety audit for generated experiment outputs.

## Future v0.7+

- Cloud or cluster execution adapters.
- Dataset download managers with license-aware caching.
- Continuous benchmark tracking.
- Automated ablation campaign scheduling.
- Integration with experiment trackers such as MLflow, Weights & Biases, or local alternatives.
- Rich notebook/report export for empirical results.

## Non-Goals

- Do not fabricate experimental results.
- Do not mark an experiment as executed unless a run record and result artifact exist.
- Do not make CI depend on expensive experiments.
- Do not weaken literature, novelty, or prior-work recall gates.
- Do not claim empirical success from smoke tests.
- Do not hide failed or negative results.

## Release Gate Direction

The v0.6 release gate requires at least:

- deterministic CI remains passing
- v5 literature-quality gates remain passing or are explicitly documented
- one executed fixture experiment with run manifest, logs, result artifact, statistical analysis, reproducibility check, and result claim ledger
- one failed or negative experiment path with visible failure/negative-result reporting
- paper package export that distinguishes real executed results from placeholders and hypothetical expected results
- no empirical claim marked supported without a result artifact

## Implemented Command Surface

```bash
gapforge experiment-workspace-create --project-id <project-id> --direction-id <direction-id>
gapforge dataset-register --workspace-id <workspace-id> --name "..." --path <path> --dataset-type fixture
gapforge baseline-register --workspace-id <workspace-id> --name "..." --baseline-type heuristic
gapforge metric-register --workspace-id <workspace-id> --name "false positive rate"
gapforge scaffold-experiment-code --workspace-id <workspace-id>
gapforge experiment-code-task --workspace-id <workspace-id> --type implement_metric
gapforge experiment-manifest-create --workspace-id <workspace-id> --run-type smoke --command "..." --expected-output results/metrics.json
gapforge experiment-run --workspace-id <workspace-id> --manifest-id <manifest-id>
gapforge parse-results --execution-id <execution-id>
gapforge analyze-results --execution-id <execution-id>
gapforge reproducibility-check --execution-id <execution-id>
gapforge empirical-review --execution-id <execution-id>
gapforge export-paper-package-v2 --workspace-id <workspace-id>
gapforge v6-release-gate --write-report --json
```
