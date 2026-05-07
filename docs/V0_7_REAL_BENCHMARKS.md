# GapForge v0.7 Real Benchmarks

v0.7 introduces real benchmark handling. A benchmark is a named empirical evaluation target with dataset, task, metrics, baselines, expected artifacts, and reporting constraints.

## Benchmark Levels

### Fixture Smoke

Fixture smoke uses tiny local data and deterministic code paths. It is CI-safe and validates plumbing. It does not count as benchmark performance.

### Local Benchmark

A local benchmark uses real or benchmark-like data small enough to run on a developer machine. It can count for v0.7 acceptance if it has dataset cards, benchmark cards, required baselines, parsed results, analysis, and review.

### Full Benchmark

A full benchmark uses the intended benchmark dataset, required metrics, required baselines, and the intended execution environment. It may require explicit downloads, GPU, or longer runtime. It is never required in normal CI.

### Replication

Replication means another person or process can rerun the package from documented commands, environment, dataset checksums, and expected output manifests. Replication packages should include both success and known-failure notes.

## Benchmark Registry Requirements

Each benchmark should record:

- ID and name
- task type
- source URL and citation
- dataset requirements
- license and redistribution constraints
- required baselines
- required metrics
- recommended statistical tests
- expected output artifacts
- compute requirements
- known leakage risks
- known failure modes
- provenance

## Data and Cache Requirements

External data handling must be explicit:

- no automatic large downloads without approval metadata
- cache paths must be recorded
- checksums or version identifiers must be recorded where possible
- local data should be classified as real, benchmark, synthetic, fixture, generated, or unknown
- unsafe artifacts must be ignored by default
- redistribution warnings must appear in reports

## Benchmark Canaries

v0.7 should define real benchmark canaries such as:

- small local benchmark canary with real or benchmark-like public data
- underpowered low-FPR benchmark refusal canary
- missing-baseline benchmark blocker canary
- failed-job canary
- replication-package canary

These canaries are manual/private when they require network or compute. CI should use mocked or fixture versions only.

## Reporting Rules

Benchmark reports must show:

- benchmark level
- dataset and cache status
- compute mode
- commands executed
- baselines included and missing
- metrics and confidence intervals
- sample-size and power warnings
- failed jobs
- error/slice analysis
- replication package status
- what claims are supported, uncertain, failed, or planned

