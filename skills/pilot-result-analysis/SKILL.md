---
name: pilot-result-analysis
description: Use when analyzing v2.2 selected benchmark pilot executions, low-FPR reports, baseline comparisons, or error artifacts.
---

# Pilot Result Analysis

## Purpose

Turn saved pilot execution artifacts into interpretable results while preserving low-FPR caveats.

## Required Outputs

- `pilot_metrics.json/md`
- `pilot_baseline_comparison.json/md`
- `pilot_error_analysis.json/md`
- `pilot_low_fpr_report.json/md`
- `pilot_limitations.md`

## Required Analysis

- per-monitor FPR and TPR
- per-episode false alarm probability
- time-to-detection and detection delay
- confidence intervals
- zero-false-positive upper bounds
- underpowered alpha levels
- hard-negative false positives
- action-only versus transcript-visible slices
- failed baseline runs

## Command Path

```bash
gapforge selected-pilot-analysis --execution-id <execution-id>
gapforge selected-pilot-report --benchmark-id <benchmark-id>
```

## Result Discipline

- Error examples must come from artifacts.
- Say when `alpha=0.001` is unsupported.
- Say when data is synthetic.
- Say when baselines are weak.
- Do not mix smoke, pilot, and main evidence.
