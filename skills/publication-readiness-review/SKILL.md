---
name: publication-readiness-review
description: Use when running or interpreting the v2.3 selected-benchmark publication-readiness reviewer panel.
---

# Publication-Readiness Review

## Purpose

Review the selected benchmark manuscript package separately from the go/no-go decision, with conservative publication labels.

## Command Path

```bash
gapforge selected-publication-review --benchmark-id <benchmark-id>
gapforge selected-publication-fix-list --benchmark-id <benchmark-id>
gapforge selected-main-manuscript --benchmark-id <benchmark-id>
gapforge selected-main-paper-package --benchmark-id <benchmark-id>
```

## Discipline Rules

- Synthetic deployment-validity claims are fatal.
- Missing real related work is major or fatal.
- Missing required baselines are major or fatal.
- Underpowered alpha claims are fatal.
- Pilot-only evidence may be workshop-candidate at most unless strong caveats are explicit.
