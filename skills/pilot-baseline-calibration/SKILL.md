---
name: pilot-baseline-calibration
description: Use when calibrating or running v2.2 selected benchmark pilot monitor baselines or checking missing-baseline blockers.
---

# Pilot Baseline Calibration

## Purpose

Make pilot baseline comparisons credible enough for exploratory evidence without treating weak baselines as SOTA.

## Required Baselines

Pilot readiness requires at least:

- random detector
- fixed-threshold frequency detector
- statistical anomaly detector
- action-only heuristic monitor

Other registered baselines should run or be explicitly blocked. Optional LLM judge baselines are opt-in and never required in CI.

## Command Path

```bash
gapforge calibrate-monitor --benchmark-id <benchmark-id> --monitor <name> --target-alpha 0.01
gapforge run-pilot-baselines --benchmark-id <benchmark-id> --dataset-id <dataset-id>
gapforge pilot-baseline-report --benchmark-id <benchmark-id>
```

## Result Discipline

- Calibrate thresholds on honest/null data only.
- Warn or block calibration leakage.
- Preserve failed and missing baseline runs.
- Do not claim monitor superiority unless comparison power supports it.
