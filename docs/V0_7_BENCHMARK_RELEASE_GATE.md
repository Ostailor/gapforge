# GapForge v0.7 Benchmark Release Gate

The v0.7 release gate answers:

> Can this release claim real benchmark execution and replication readiness?

The gate must fail closed. Fixture smoke and fake-agent paths remain useful, but they do not prove benchmark performance.

## Required Inputs

- deterministic CI status
- v5 literature-quality gate status
- v6 empirical artifact gate status
- benchmark registry records
- dataset cards and cache metadata
- baseline and metric registry records
- compute/job execution records
- result artifacts and hashes
- parsed metric results
- statistical analysis
- error or slice analysis
- reproducibility check
- empirical/benchmark review
- replication package

## Passing Requirements

The gate should pass only if:

- deterministic CI passed
- v6 empirical artifact gate passed or limitations are documented
- at least one real or benchmark-like non-fixture run exists
- benchmark dataset and license are recorded
- large downloads, if any, have approval/cache/checksum metadata
- required baselines are present or missing baselines block acceptance
- result artifacts are hashed and parsed
- comparison tables are generated
- low-FPR or rare-event claims include sample-size and uncertainty warnings
- failed jobs are visible
- replication package is exported
- human review accepts the benchmark scope and claim language
- no fake results, hidden failures, or unsupported benchmark claims are accepted

## Incomplete Status

The gate should mark real benchmark validation incomplete if:

- only fixture smoke runs exist
- no real or benchmark-like non-fixture run exists
- external downloads were skipped and no local benchmark substitute was approved
- GPU or cluster resources were required but unavailable
- independent replication was not attempted
- benchmark review was not completed

## Expected Output

The release gate report should include:

- pass/fail status
- benchmark records considered
- benchmark level for each run
- compute mode
- dataset/cache status
- result artifact IDs
- comparison table IDs
- error/slice analysis status
- replication package path
- blockers and next commands
- explicit release statement

## Release Statements

Use exactly one:

- `v0.7 real benchmark execution acceptance passed`
- `v0.7 real benchmark execution acceptance not completed`

Never mark the gate passed because fixture smoke, fake-agent, or Codex-generated text succeeded.

