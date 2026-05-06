---
name: result-analysis
description: Use when parsing, analyzing, or summarizing GapForge v0.6 experiment result artifacts and empirical claims.
---

# Result Analysis

## Purpose
Turn execution-produced artifacts into cautious metric summaries and empirical claims.

## When To Use
- After an experiment execution has result artifacts.
- When analyzing confidence intervals or low-FPR warnings.
- When preparing result summaries for paper package v2.

## Inputs
- Execution ID or workspace ID.
- Result artifact metadata.
- Metric registry and run manifest.

## Outputs
- `ResultSummary`
- `MetricResult`
- `EmpiricalClaim`
- `StatisticalAnalysisReport`

## Required Artifacts
- `reports/result_summary_<execution_id>.json`
- `reports/empirical_claims.json`
- `reports/analysis_report*.json`
- source `metrics_json` result artifact

## Procedure
1. Parse results with `gapforge parse-results`.
2. Check that metrics resolve to registered metric IDs.
3. Analyze uncertainty with `gapforge analyze-results`.
4. Check low-FPR sample-size warnings.
5. Keep failed/negative/inconclusive claims visible.

## Validation Checklist
- [ ] Every metric result has a raw artifact ID.
- [ ] Empirical claims link metric result IDs.
- [ ] Missing confidence intervals produce warnings.
- [ ] Failed runs do not become success claims.

## Failure Modes
- Parsing model prose instead of result artifacts.
- Creating claims from expected results.
- Overstating significance or hiding sample-size limits.

## Examples
```bash
gapforge parse-results --execution-id EXECUTION
gapforge analyze-results --execution-id EXECUTION
gapforge empirical-claims --workspace-id WORKSPACE
```

## Evidence Rules
No artifact means no empirical claim. Logs alone can support failure claims but not metric success claims.

## Uncertainty Rules
Use supported/contested/failed/uncertain status and keep limitations beside the claim.

## Chain-Of-Thought Rule
Store only public reasoning summaries. Do not request or store hidden chain-of-thought.

## No Fake Results
Do not invent metric values, intervals, sample sizes, tables, plots, or significance claims.
