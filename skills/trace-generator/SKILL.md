---
name: trace-generator
description: Use when generating synthetic selected-benchmark traces for smoke or pilot benchmark execution.
---

# Trace Generator

## Purpose

Generate labeled synthetic traces for benchmark wiring, hard-negative specificity checks, and pilot preparation.

## Required Trace Properties

- synthetic label on every trace
- honest, collusive, and ambiguous trace types
- transcript-visible and action-only observability modes
- honest benign coordination that can trigger false positives
- explicit collusion labels for collusive traces
- ambiguous traces excluded from main metrics unless specified

## Discipline Rules

- Synthetic smoke benchmark is not a final research result.
- Low-FPR claims require power; a small smoke trace set is underpowered by default.
- Synthetic traces do not prove real deployment or benchmark validity limitations.
- Reports must be artifact-backed by `dataset.json`, `traces.json`, and scenario records.
- No fake results, no hidden labels passed to monitors, and no relabeling hard negatives to improve scores.

## Command Path

```bash
gapforge generate-traces --benchmark-id <benchmark-id> --count 100 --split smoke
gapforge trace-dataset-report --dataset-id <dataset-id>
gapforge trace-list --benchmark-id <benchmark-id>
```
