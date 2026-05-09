---
name: related-work-completion
description: Use when completing v2.3 selected-benchmark related work with real paper records.
---

# Related-Work Completion

## Purpose

Turn the v2.2 related-work blocker into an actionable completion campaign with real attached paper records.

## Required Categories

- low-FPR detection/evaluation
- multi-agent collusion/covert coordination
- monitor evasion
- sequential testing/change-point detection
- benchmark/evaluation protocol papers
- anomaly detection specificity
- medical screening specificity analogies, if used
- cartel/covert-channel analogies, if used

## Command Path

```bash
gapforge selected-related-work-complete --benchmark-id <benchmark-id>
gapforge selected-related-work-next-searches --benchmark-id <benchmark-id>
gapforge selected-related-work-status --benchmark-id <benchmark-id>
```

## Discipline Rules

- Fallback-only records do not complete a category.
- Novelty remains unknown until required categories have sufficient real coverage.
- Missing real prior work must stay visible in reports, manuscript text, and release gates.
