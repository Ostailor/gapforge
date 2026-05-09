---
name: go-no-go-review
description: Use when making the v2.3 selected-benchmark go/no-go decision after main or pilot analysis.
---

# Go/No-Go Review

## Purpose

Produce a clear v2.3 next decision: publication candidate, revise benchmark, run more experiments, or no-go.

## Command Path

```bash
gapforge selected-main-analysis --execution-id <execution-id>
gapforge selected-benchmark-go-no-go --benchmark-id <benchmark-id>
gapforge selected-go-no-go-report --benchmark-id <benchmark-id>
```

## Decision Rules

- Go only when powered alpha, related work, required baselines, reviewer blockers, and manuscript traceability pass.
- Revise when benchmark, data, related work, baselines, or manuscript are insufficient.
- Run more experiments when power or baselines are insufficient but feasible.
- No-go when novelty, validity, or baseline evidence fails the idea or claim.
