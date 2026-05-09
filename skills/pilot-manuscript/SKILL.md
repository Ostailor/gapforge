---
name: pilot-manuscript
description: Use when generating or reviewing the v2.2 selected benchmark pilot manuscript or paper package.
---

# Pilot Manuscript

## Purpose

Package pilot evidence without turning it into publication-ready or main-benchmark claims.

## Required Sections

- motivation
- benchmark definition
- threat model
- pilot trace dataset
- baseline monitors
- calibration
- sequential specificity metrics
- pilot results
- low-FPR limitations
- related work
- reviewer blockers
- path to main benchmark

## Command Path

```bash
gapforge selected-pilot-manuscript --benchmark-id <benchmark-id>
gapforge selected-pilot-paper-package --benchmark-id <benchmark-id>
```

## Result Discipline

- Label results as pilot.
- Make synthetic limitations prominent.
- Block `alpha=0.001` unless powered.
- Include reviewer blockers and main benchmark requirements.
- Do not claim publication readiness unless release and reviewer gates allow it.
