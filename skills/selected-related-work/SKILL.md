---
name: selected-related-work
description: Use when attaching prior-work recall, related-work matrices, or conservative novelty positioning for the selected benchmark.
---

# Selected Related Work

## Purpose

Ground the selected benchmark before novelty or publication-readiness claims.

## Required Categories

- low-FPR detection/evaluation
- multi-agent collusion or covert coordination
- monitor evasion
- sequential testing or change-point detection
- benchmark/evaluation protocol papers
- anomaly detection specificity
- medical screening specificity analogies, if used
- cartel or covert-channel analogies, if used

## Command Path

```bash
gapforge selected-benchmark-prior-work --benchmark-id <benchmark-id>
gapforge selected-benchmark-related-work --benchmark-id <benchmark-id>
gapforge selected-benchmark-novelty-report --benchmark-id <benchmark-id>
```

## Result Discipline

- No fake citations.
- Missing categories block strong novelty.
- Closest prior work must be explicit.
- Position the contribution as a benchmark/evaluation protocol unless evidence supports more.
