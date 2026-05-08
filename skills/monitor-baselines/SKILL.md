---
name: monitor-baselines
description: Use when registering or running selected-benchmark baseline monitors on synthetic smoke traces.
---

# Monitor Baselines

## Purpose

Run explicit, auditable starting baselines before any advanced monitor or manuscript claim.

## Required Baselines

- random detector
- frequency/threshold detector
- lexical overlap detector
- repeated-action detector
- simple statistical anomaly detector
- optional LLM judge placeholder disabled in CI
- oracle upper-bound placeholder labeled analysis-only

## Discipline Rules

- Synthetic smoke benchmark is not a final research result.
- Low-FPR claims require power and cannot come from a tiny baseline smoke run.
- Each baseline must declare input mode, threshold, limitations, and whether it is CI-runnable.
- Predictions and reports must be artifact-backed.
- No fake results, no oracle as deployable method, and no hiding weak or missing baselines.

## Command Path

```bash
gapforge selected-monitor-baselines --benchmark-id <benchmark-id>
gapforge run-monitor-baseline --benchmark-id <benchmark-id> --monitor random
gapforge monitor-baseline-report --benchmark-id <benchmark-id>
```
