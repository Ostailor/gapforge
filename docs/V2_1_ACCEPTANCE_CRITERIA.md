# GapForge v2.1 Acceptance Criteria

v2.1 acceptance is about selected-idea execution honesty. It must turn the v2.0 accepted idea into a concrete benchmark artifact path without overstating smoke outputs.

Summary boundary: v2 found candidate idea `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`; v2.1 executes that selected idea. The synthetic smoke benchmark is not a final research result, low-FPR claims require power, benchmark validity limitations must remain explicit, and next steps toward pilot/main benchmark must be recorded.

## Definitions

- **Selected idea freeze**: the v2.0 accepted idea ID, title, scope, and non-claims are recorded as the v2.1 execution target.
- **Benchmark artifact**: the versioned benchmark specification plus task generator, scenario records, baseline monitors, metric definitions, run manifests, result artifacts, analysis, critique, and package outputs required to inspect the benchmark.
- **Smoke benchmark**: a deterministic, small fixture run that proves the benchmark path is runnable and artifact-backed.
- **Pilot benchmark**: an exploratory run with expanded scenarios, all baselines, preregistered metrics, and explicit power status.
- **Main benchmark**: a claim-supporting run with locked benchmark version, sufficient sample size, uncertainty estimates, replication package, and review.
- **Sequential specificity**: low-FPR behavior measured over repeated audit windows, including family-wise false-alarm risk and time-to-first-false-alarm.

## Required Documentation Criteria

1. v2.1 roadmap is centered on `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`.
2. v2.1 selected-idea docs freeze the idea and define pivot rules.
3. v2.1 benchmark spec defines the benchmark artifact that must exist.
4. v2.1 defines smoke, pilot, and main benchmark levels.
5. v2.1 docs preserve non-goals for synthetic fixtures, smoke runs, novelty gates, and publication readiness.

## Required Benchmark Criteria

1. Benchmark name and version exist.
2. Threat model and observability assumptions are explicit.
3. Honest-agent baseline distribution is defined.
4. Collusive-agent scenario distribution is defined.
5. Hard-negative benign scenarios are defined.
6. Sequential audit protocol is specified.
7. Low-FPR specificity metrics are implemented and reported.
8. Baseline monitor suite exists and declares allowed inputs.
9. Power/sample-size plan classifies smoke, pilot, main, and underpowered runs.
10. Experiment workspace exists with benchmark, dataset, baseline, metric, and manifest records.
11. Codex implementation tasks, if used, are schema-validated and cannot import fake citations, fake results, or unsupported claims.
12. Smoke benchmark run executes end to end.
13. Result artifacts are persisted and parsed before analysis.
14. Reviewer critique records blockers and limitations.
15. Manuscript package update links claims to benchmark and result artifacts.

## v2.1 Release Gate Must Require

The release gate must fail unless all are true:

- selected idea freeze exists
- benchmark specification exists
- threat model exists
- task generator can create deterministic smoke fixtures
- honest and collusive scenario distributions are represented
- at least one hard-negative honest scenario is present
- baseline monitors run on generated tasks
- sequential specificity metrics are computed
- power plan marks smoke outputs as smoke-scale
- experiment workspace has a runnable smoke manifest
- smoke execution record, logs, raw outputs, metrics, and analysis exist
- result analysis is derived from artifacts, not invented prose
- reviewer critique exists
- manuscript package update exists
- unsupported final-result, real-world-validity, and publication-readiness claims are blocked

## Pass Outcomes

### Pass With Runnable Smoke Path

v2.1 may pass when the selected idea has:

- frozen scope
- formal benchmark artifact
- runnable smoke benchmark path
- artifact-backed smoke result analysis
- reviewer critique
- manuscript package update

Release notes may say the selected idea execution path is smoke-validated.

They must also say smoke-validated means runnable and artifact-backed only. It does not mean externally valid, powered for low-FPR claims, or ready for publication.

### Incomplete Execution

v2.1 must not pass if the strongest output is only:

- benchmark prose with no runnable path
- generator scaffolding without monitor execution
- monitor output without persisted artifacts
- metrics without power/sample-size classification
- smoke outputs presented as scientific results
- manuscript prose without traceability

## Fail Conditions

v2.1 fails when:

- the release silently changes the selected idea
- the benchmark definition is missing or ambiguous
- threat model or observability assumptions are unstated
- honest-agent and collusive-agent scenario distributions are not separated
- low-FPR specificity is not measured sequentially
- baseline monitors are missing
- the smoke path cannot run
- result artifacts are missing
- analysis invents empirical results
- synthetic fixture outputs are described as real-world validation
- novelty or prior-work gates are weakened
- reviewer critique is omitted
- manuscript package claims submission-readiness without gates

## Release Statement

Release notes must say one of:

- `v2.1 selected idea execution passed with runnable benchmark smoke path`
- `v2.1 selected idea execution incomplete; benchmark smoke path not ready`
- `v2.1 selected idea execution blocked; selected idea requires redesign or new idea-discovery run`

Do not use `passed` unless the runnable smoke path and required artifacts exist.
