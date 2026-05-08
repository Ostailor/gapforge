---
name: sequential-audit-metrics
description: Use when planning or computing low-FPR sequential audit metrics for selected-benchmark traces.
---

# Sequential Audit Metrics

## Purpose

Measure repeated-audit false alarms, detection timing, uncertainty, and underpowered status without overstating smoke results.

## Required Metrics

- per-step and per-episode false positive rate
- family-wise false alarm probability
- time-to-detection and detection delay
- true positive rate at fixed false-positive budget
- specificity at alpha
- sequential calibration error
- abstention or uncertain rate
- exact/binomial intervals and zero-false-positive upper bound

## Discipline Rules

- Synthetic smoke benchmark is not a final research result.
- Low-FPR claims require power; zero false positives still need an upper confidence bound.
- Smoke results must be labeled underpowered for strong low-FPR claims.
- Metric reports must be artifact-backed by traces and monitor predictions.
- No fake results and no hand-entered metric values unless they are computed from persisted artifacts.

## Command Path

```bash
gapforge sequential-metric-plan --benchmark-id <benchmark-id>
gapforge compute-sequential-metrics --execution-id <dataset-id>
gapforge low-fpr-audit-check --execution-id <dataset-id>
```
