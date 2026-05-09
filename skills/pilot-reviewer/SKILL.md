---
name: pilot-reviewer
description: Use when running or interpreting the v2.2 selected benchmark pilot reviewer panel, fix list, or publishability assessment.
---

# Pilot Reviewer

## Purpose

Review pilot evidence seriously and keep remaining blockers explicit.

## Required Reviewer Roles

- benchmark validity reviewer
- statistics/low-FPR reviewer
- baseline reviewer
- related-work/novelty reviewer
- synthetic data validity reviewer
- area chair

## Command Path

```bash
gapforge selected-pilot-review --benchmark-id <benchmark-id>
gapforge selected-pilot-fix-list --benchmark-id <benchmark-id>
```

## Result Discipline

- Underpowered alpha targets remain blockers or warnings.
- Missing related-work categories block strong novelty.
- Synthetic-only evidence blocks deployment claims.
- Weak baselines block strong contribution claims.
- Recommend main-scale data or stronger scenarios when pilot evidence is insufficient.
