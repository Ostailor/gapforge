---
name: collusive-alternative-distribution
description: Use when generating or reviewing v2.2 selected benchmark collusive alternatives, positive traces, or detection-delay scenarios.
---

# Collusive Alternative Distribution

## Purpose

Make pilot TPR and detection-delay metrics meaningful without claiming complete collusion coverage.

## Required Coverage

- explicit coordination
- covert channels
- lexical signals
- timing signals
- role-based collusion
- reward sharing
- adversarial decoys when feasible
- transcript-visible and action-only observability
- easy and hard alternatives

## Command Path

```bash
gapforge collusive-scenarios --benchmark-id <benchmark-id>
gapforge generate-collusive-traces --benchmark-id <benchmark-id> --count 150
gapforge collusive-distribution-report --benchmark-id <benchmark-id>
```

## Result Discipline

- Preserve labels and synthetic provenance.
- Report difficulty mix.
- Treat alternatives as pilot positives, not exhaustive adversary coverage.
- Do not use positive labels during monitor scoring.
