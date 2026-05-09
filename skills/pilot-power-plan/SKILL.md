---
name: pilot-power-plan
description: Use when planning or checking v2.2 selected benchmark low-FPR pilot sample size, alpha targets, or underpowered evidence.
---

# Pilot Power Plan

## Purpose

Keep low-FPR claims power-gated before interpreting pilot results.

## Maturity Rules

- Smoke proves wiring only.
- Pilot may support `alpha=0.01` only when negative counts and confidence bounds support it.
- `alpha=0.001` is main-scale by default and remains blocked unless enough honest/null negatives exist.
- Zero false positives are an upper confidence bound, not proof of zero risk.
- Sequential repeated looks require explicit notes or correction.

## Required Artifacts

- `pilot_power/pilot_power_plan.json`
- `pilot_power/pilot_power_plan.md`
- `pilot-power-assessment-*.json`
- `pilot-power-assessment-*.md`

## Command Path

```bash
gapforge selected-pilot-power-plan --benchmark-id <benchmark-id>
gapforge selected-pilot-power-check --dataset-id <dataset-id>
```

## Result Discipline

- Report required and observed negative counts for every alpha target.
- Block low-FPR claims that exceed the data.
- Preserve underpowered targets as warnings or blockers.
- Never describe synthetic pilot evidence as operational deployment specificity.
