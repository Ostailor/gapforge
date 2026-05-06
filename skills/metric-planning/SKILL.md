---
name: metric-planning
description: Use when defining metrics, statistical plans, confidence intervals, or low-FPR cautions for GapForge v0.6 experiments.
---

# Metric Planning

## Purpose
Make measurements and uncertainty explicit before execution and before empirical claims.

## When To Use
- Registering metrics for a workspace.
- Planning statistical tests.
- Reviewing low false-positive-rate experiments.

## Inputs
- Workspace ID or experiment protocol ID.
- Metric names, formulas, required inputs, directionality, sample-size notes, edge cases.

## Outputs
- `MetricRecord`
- `StatisticalTestPlan`
- low-FPR warnings

## Required Artifacts
- `metrics/metric-*.record.json`
- `metrics/metric_registry.md`
- `metrics/stats_plans/*.json`
- `metrics/stats_plans/*.md`

## Procedure
1. Register built-in metrics or custom definitions.
2. Confirm higher/lower-is-better semantics.
3. Create stats plan with confidence interval and multiple-testing notes.
4. For low-FPR metrics, require denominator/sample-size caution.
5. Feed metric IDs into manifests and result parsing.

## Validation Checklist
- [ ] Metric formula and required inputs are explicit.
- [ ] Low-FPR claims include confidence intervals or warnings.
- [ ] Missing sample size blocks strong claims.
- [ ] Statistical plan is written before paper-ready export.

## Failure Modes
- Optimizing the wrong direction.
- Reporting rates without denominators.
- Treating smoke metrics as main results.

## Examples
```bash
gapforge metric-register --workspace-id WORKSPACE --name "false positive rate"
gapforge stats-plan --workspace-id WORKSPACE
gapforge low-fpr-power-check --workspace-id WORKSPACE
```

## Evidence Rules
Metric definitions are measurement rules. Empirical support requires parsed metric results from result artifacts.

## Uncertainty Rules
Report confidence intervals, sample size limitations, and multiple-testing warnings where applicable.

## Chain-Of-Thought Rule
Store only public reasoning summaries. Do not request or store hidden chain-of-thought.

## No Fake Results
Do not invent values, confidence intervals, sample sizes, p-values, or plots.
