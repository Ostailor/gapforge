---
name: sequential-specificity-benchmark
description: Use when defining or inspecting the v2.1 sequential specificity benchmark for the selected low-FPR collusion idea.
---

# Sequential Specificity Benchmark

## Purpose

Define the benchmark before interpreting any run output. The benchmark is about repeated audit specificity at low false-positive budgets.

## Required Artifacts

- `spec.json` and `spec.md`
- threat model and observability assumptions
- honest-agent null distribution
- collusive-agent alternative distribution
- task families and labels
- monitor input/output contract
- required baselines, metrics, and statistical requirements

## Discipline Rules

- Synthetic smoke benchmark is not a final research result.
- Low-FPR claims require power, confidence intervals, and sequential multiple-testing warnings.
- Benchmark validity limitations must name synthetic data, hidden-label exclusions, fixed scenarios, and missing external review.
- Results must be artifact-backed before analysis.
- No fake results, no oracle access for deployable monitors, and no publication-ready language from scaffolding.

## Command Path

```bash
gapforge selected-benchmark-spec --project-id <selected-project-id>
gapforge threat-model --benchmark-id <benchmark-id>
gapforge benchmark-task-families --benchmark-id <benchmark-id>
gapforge selected-benchmark-report --benchmark-id <benchmark-id>
```
