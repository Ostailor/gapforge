---
name: main-benchmark-run
description: Use when building or running the v2.3 selected-benchmark main dataset, manifest, run, and analysis path.
---

# Main Benchmark Run

## Purpose

Run a main-style selected benchmark path with artifact-backed metrics, predictions, baseline comparison, error analysis, and low-FPR reporting.

## Command Path

```bash
gapforge build-main-trace-dataset --benchmark-id <benchmark-id>
gapforge selected-main-manifest --benchmark-id <benchmark-id> --dataset-id <dataset-id>
gapforge selected-main-run --benchmark-id <benchmark-id> --manifest-id <manifest-id>
gapforge selected-main-status --execution-id <execution-id>
gapforge selected-main-analysis --execution-id <execution-id>
```

## Discipline Rules

- Use the main dataset and required baselines.
- Preserve failures as artifacts.
- If the dataset is not powered, the run cannot make a powered claim.
- Synthetic traces are benchmark evidence only, not deployment-validity evidence.
