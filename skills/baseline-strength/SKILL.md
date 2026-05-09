---
name: baseline-strength
description: Use when assessing v2.3 selected-benchmark baseline strength and strong-claim eligibility.
---

# Baseline Strength

## Purpose

Assess whether the selected benchmark has enough required baselines and calibration integrity for stronger contribution claims.

## Required Baselines

- sequential change-point detector
- calibrated anomaly detector
- permutation/null-distribution detector
- conformal-style score threshold detector
- action-only transition detector
- transcript-visible semantic heuristic detector
- robust lexical substitution monitor

The LLM judge is optional, opt-in, and not required in CI.

## Command Path

```bash
gapforge selected-baseline-strength --benchmark-id <benchmark-id>
gapforge implement-required-baseline-task --benchmark-id <benchmark-id> --baseline <name>
gapforge selected-baseline-strength-report --benchmark-id <benchmark-id>
```

## Discipline Rules

- Missing required baselines block publication-readiness.
- Calibration leakage is a blocker.
- Strong contribution claims require all required baselines and no calibration leakage.
- Report optional LLM judge status separately.
