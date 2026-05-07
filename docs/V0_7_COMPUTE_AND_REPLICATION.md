# GapForge v0.7 Compute and Replication

v0.7 should make compute execution and replication explicit. A benchmark run should say where it ran, what resources it used, what command executed, what artifacts were produced, and whether another person can rerun it.

## Compute Modes

### Local CPU

Default benchmark execution mode. It should support small benchmark-like runs without special hardware.

### Local GPU

Optional mode for experiments that need accelerated inference or training. GPU availability must be detected and recorded, but normal CI must not require it.

### Cluster or Handoff

Cluster mode should produce job manifests, scripts, expected output paths, and import instructions. A cluster handoff does not count as executed until logs and result artifacts are imported and validated.

## Compute Environment Records

Each run should record:

- mode: local CPU, local GPU, cluster, handoff, or unknown
- hardware summary
- software environment
- command
- working directory
- resource limits
- timeout
- started and completed timestamps
- return code
- stdout/stderr log paths
- output artifacts and hashes
- provenance

## Job Failure Policy

Failed jobs are first-class artifacts. They must include:

- failure status
- command and environment
- stdout/stderr logs
- return code or timeout reason
- missing expected outputs
- retry decisions
- whether failure invalidates a claim

Do not delete or hide failed jobs to make a report look cleaner.

## Replication Package

A v0.7 replication package should include:

- `REPRODUCE.md`
- benchmark card
- dataset card and download/cache instructions
- checksums or version IDs
- environment spec
- run manifests
- exact commands
- expected output manifest
- result parser instructions
- statistical analysis instructions
- known nondeterminism
- failed-job notes
- reviewer checklist

## Independent Review

Independent replication should be recorded separately from the original execution. It should say:

- who or what reran it
- whether the environment matched
- which data version was used
- whether outputs matched within tolerance
- which differences remain unexplained

## Low-FPR Compute Guidance

Low-FPR experiments can be misleading when sample sizes are small. v0.7 should require:

- target false-positive range
- minimum negative examples
- confidence interval method
- power/sample-size note
- warning when results are underpowered
- refusal to claim strong empirical support when the run is too small

