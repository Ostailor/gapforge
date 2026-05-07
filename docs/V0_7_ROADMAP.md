# GapForge v0.7 Roadmap

v0.7 is the real benchmark execution and replication release. v0.6 proved that GapForge can create experiment workspaces, run fixture experiments, parse result artifacts, and keep empirical claims artifact-gated. v0.7 should move from fixture/smoke execution to benchmark-like or real benchmark execution with explicit compute, data, replication, and release-gate controls.

GapForge must still not claim empirical success from fixture runs, smoke runs, model-generated text, or incomplete benchmark jobs.

## Goals

1. Add a benchmark registry that records benchmark identity, task type, dataset requirements, metrics, baselines, licenses, expected resources, and citation requirements.
2. Add external dataset download and cache policies that require explicit user approval for large downloads and record checksums, licenses, and local paths.
3. Add compute environment abstraction for local CPU, local GPU, and cluster-style execution without requiring GPU in normal CI.
4. Add local, GPU, and cluster job execution modes with durable job records, logs, exit codes, resource summaries, and retry/failure state.
5. Add experiment sweeps and ablations with manifests, parameter grids, run grouping, and comparison tables.
6. Add real benchmark canaries that are manual/private by default and excluded from normal CI.
7. Add a result database for metric results, comparisons, slices, error cases, and benchmark leader-style tables.
8. Add error analysis and slice analysis that preserves negative, subgroup, and failure findings.
9. Add power and sample-size analysis for low-FPR experiments before allowing strong empirical claims.
10. Add independent replication packages with commands, environment lockfiles, data cards, checksums, expected artifacts, and reviewer checklist.
11. Extend artifact safety to large datasets, checkpoints, predictions, logs, and benchmark outputs.
12. Add a v0.7 release gate for real or benchmark-like non-fixture execution.

## Must-Have Workstreams

### Benchmark Registry

- `BenchmarkRecord`
- `BenchmarkCard`
- benchmark dataset, metric, baseline, and citation requirements
- known pitfalls, leakage risks, and license constraints
- benchmark readiness checks

### Data Download and Cache Policy

- explicit approval before downloading large datasets
- cache directory policy and checksum manifests
- license and redistribution warnings
- safe-to-commit classification for downloaded artifacts
- offline fallback that reports disabled status without failing CI

### Compute and Jobs

- local CPU execution
- local GPU execution when available
- cluster/handoff job manifests
- timeout and resource limits
- stdout/stderr/resource logs
- failed job preservation

### Sweeps, Ablations, and Comparisons

- sweep manifests
- ablation plans
- result tables by metric/dataset/baseline/split
- paired comparisons when valid
- multiple-testing warnings

### Error and Slice Analysis

- slice definitions
- error examples with locators or row IDs
- failure mode summaries
- low-FPR false-positive and false-negative drilldowns
- privacy-safe excerpts

### Replication Package

- `REPRODUCE.md`
- environment spec
- data download/checksum instructions
- commands to rerun
- expected output manifest
- known nondeterminism
- independent reviewer checklist

## Release-Gate Expectations

v0.7 should require at least one real or benchmark-like non-fixture run before it can claim benchmark execution acceptance. If no such run exists, the release gate must fail or mark real benchmark validation incomplete.

The release gate should distinguish:

- fixture smoke: CI-safe wiring only
- local benchmark: small real or benchmark-like run on local resources
- full benchmark: benchmark run with required data, baselines, metrics, and analysis
- replication: independent rerun package reviewed by another person or process

## Non-Goals

- Do not require GPU or external downloads in normal CI.
- Do not claim benchmark success from fixture runs.
- Do not auto-download large datasets without explicit user approval.
- Do not hide failed jobs, missing baselines, underpowered runs, or benchmark exclusions.
- Do not weaken v5 literature gates or v6 empirical claim gates.
- Do not treat Codex-generated code or analysis text as result evidence without execution artifacts.

## Milestones

1. Benchmark registry and cards.
2. Dataset download/cache policy with artifact safety.
3. Compute environment and job runner abstraction.
4. Sweep/ablation manifests and result database.
5. Error and slice analysis.
6. Low-FPR power/sample-size gate.
7. Replication package export.
8. Real benchmark canary profiles.
9. v0.7 release gate and eval fixtures.
10. Docs, skills, dashboard, and API updates.

