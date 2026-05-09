---
name: main-power-plan
description: Use when planning or auditing v2.3 selected-benchmark main-scale power and alpha decisions.
---

# Main Power Plan

## Purpose

Create the v2.3 main-scale sample-size plan and formal alpha decisions before any main result claim.

## Required Inputs

- selected benchmark ID
- v2.2 pilot power handoff
- planned negative and positive trace counts
- target alpha levels and primary alpha

## Command Path

```bash
gapforge selected-main-power-plan --benchmark-id <benchmark-id>
gapforge selected-main-alpha-decision --benchmark-id <benchmark-id> --alpha 0.001
gapforge selected-main-power-report --benchmark-id <benchmark-id>
```

## Discipline Rules

- `alpha=0.001` requires the computed negative trace count.
- If infeasible, record `downgrade`, `drop`, or `defer`; do not leave it vaguely blocked.
- Publication claims must use the powered primary alpha.
- Release notes must state the alpha decision.
