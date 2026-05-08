---
name: selected-benchmark-review
description: Use when reviewing v2.1 selected-benchmark maturity, blockers, publishability risk, or manuscript claims.
---

# Selected Benchmark Review

## Purpose

Attack the selected benchmark before release or publication-facing claims. The reviewer panel should make blockers visible, not smooth them over.

## Required Review Inputs

- benchmark spec and threat model
- trace generator and dataset reports
- baseline suite and missing-baseline blockers
- metric plan and sequential metric results
- prior-work recall, related-work matrix, and limitations
- manuscript package and smoke labels

## Discipline Rules

- Synthetic smoke benchmark is not a final research result.
- Low-FPR claims require power; underpowered claims are major or fatal.
- Benchmark validity limitations are major if synthetic data is overclaimed.
- Reviews and fix lists must be artifact-backed.
- No fake results, no hidden reviewer blockers, and no publication-ready conclusion from smoke-only evidence.

## Command Path

```bash
gapforge selected-benchmark-review --benchmark-id <benchmark-id>
gapforge selected-benchmark-fix-list --benchmark-id <benchmark-id>
gapforge selected-benchmark-manuscript --benchmark-id <benchmark-id>
```
