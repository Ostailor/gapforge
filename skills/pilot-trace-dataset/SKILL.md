---
name: pilot-trace-dataset
description: Use when building or inspecting the v2.2 selected benchmark pilot dataset, dataset card, split counts, or alpha support.
---

# Pilot Trace Dataset

## Purpose

Combine honest/null and collusive pilot traces into a dataset that can support only the claims its counts allow.

## Required Checks

- negative trace count supports the pilot alpha target or blocks it
- positive trace count is enough for pilot detection estimates or warns
- hard-negative count is recorded
- observability-mode counts are recorded
- ambiguous traces are excluded from primary metrics by default
- synthetic and pilot status are visible

## Command Path

```bash
gapforge build-pilot-trace-dataset --benchmark-id <benchmark-id>
gapforge build-pilot-trace-dataset --benchmark-id <benchmark-id> --negative-count 300 --positive-count 150
gapforge pilot-trace-dataset-report --dataset-id <dataset-id>
```

## Result Discipline

- Do not convert smoke traces into pilot claims without a pilot split.
- Do not hide ambiguous exclusions.
- Report `alpha_targets_supported` next to counts.
- Keep dataset-card limitations visible.
