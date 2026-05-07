# GapForge v0.7 Acceptance Criteria

v0.7 acceptance is about benchmark execution quality and replication readiness. It is not enough for fixture tests to pass. Fixture smoke remains necessary for CI, but release notes must not present fixture results as benchmark validation.

## Automated Acceptance

Normal CI must remain deterministic and offline-safe:

- unit tests pass without network access
- v6 evals and smoke tests remain passing
- v7 eval fixtures run offline
- fake/fixture benchmark records never count as real benchmark acceptance
- no test requires GPU, cluster access, or large dataset downloads

## Benchmark Acceptance

To claim real benchmark execution acceptance, v0.7 must have:

- at least one real or benchmark-like non-fixture execution record
- benchmark registry entry and benchmark card
- dataset card with license, source, checksum or version, and cache path
- baseline registry entries for required baselines
- metric registry entries and statistical plan
- run manifest with command, seed, environment, expected outputs, and compute mode
- result artifacts with hashes
- parsed metric results
- statistical analysis with uncertainty
- error or slice analysis
- reproducibility check
- empirical reviewer or benchmark reviewer output
- replication package export
- release gate report showing no fake results were accepted

If this bar is not met, the release can still ship implementation work, but it must say real benchmark validation is incomplete.

## Required Distinctions

Docs, reports, dashboards, and paper packages must distinguish:

- fixture smoke
- local benchmark
- full benchmark
- pilot run
- main run
- failed job
- negative result
- underpowered result
- replication package

## Blocking Failures

v0.7 must not pass benchmark acceptance if:

- only fixture or smoke runs exist
- the benchmark dataset was not recorded or is license-unknown without warning
- large data was downloaded without explicit approval metadata
- required baselines are missing
- low-FPR claims lack sample-size/power warning or confidence intervals
- result artifacts are missing or unhashed
- failed jobs are hidden
- fake or model-generated result files are accepted as real benchmark output
- Codex output mutates result state without validated execution artifacts
- replication instructions are missing

## Human Review

Human review should confirm:

- benchmark task and dataset are appropriate for the claim
- source and license risks are visible
- baselines are credible
- metrics match the claim
- results are not overclaimed
- failures and underpowered analyses are visible
- replication instructions are realistic

## Release Statement

Release notes must say one of:

- `v0.7 real benchmark execution acceptance passed`
- `v0.7 real benchmark execution acceptance not completed`

Do not choose the passed statement unless release-gate artifacts prove at least one accepted real or benchmark-like non-fixture run.

