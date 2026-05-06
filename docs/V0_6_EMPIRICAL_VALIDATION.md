# v0.6 Empirical Validation

v0.6 empirical validation answers a narrower question than publication readiness: did GapForge execute, analyze, and report an experiment honestly enough that a human can inspect what happened?

## Validation Layers

1. **Protocol validation**: the experiment design has datasets, baselines, metrics, falsification conditions, and statistical plan.
2. **Workspace validation**: code, configs, registries, and tests exist.
3. **Execution validation**: run manifest, command, logs, and result artifacts exist.
4. **Statistical validation**: analysis methods match metric types and uncertainty is visible.
5. **Reproducibility validation**: the run is rerunnable or limitations are explicit.
6. **Claim validation**: result claims link to result artifacts and avoid overstatement.
7. **Reviewer validation**: empirical reviewer simulation and human review identify weaknesses.

## Statistical Analysis

v0.6 should support lightweight statistical analysis for common experiment outputs:

- confidence intervals for rates, proportions, and low-frequency false positives
- paired or unpaired comparison notes where appropriate
- exact/binomial-style notes for low-count events
- bootstrap summaries when distribution assumptions are weak
- multiple-comparison warnings
- effect size and uncertainty summaries
- failed-assumption warnings

The system should recommend analysis methods, but not pretend they prove more than the data supports.

## Result Claim Ledger

The result claim ledger should track:

- claim text
- linked experiment run IDs
- linked result artifact IDs
- metric values
- statistical summary
- confidence
- support status: supported / weak / contradicted / inconclusive / failed
- limitations
- provenance

Literature claims and empirical result claims should remain distinct.

Artifact-gating rules:

- no `MetricResult` without a metrics artifact
- no `EmpiricalClaim` without one or more metric result IDs
- no low-FPR claim without confidence-interval handling or an explicit warning
- no paper package "Results" claim from expected results, smoke-only text, Codex prose, or dashboard labels
- failed runs create failed/uncertain claims or limitations, never success claims

## Negative and Failed Results

Negative and failed experiments are first-class outputs.

Reports should show:

- what was attempted
- what failed or did not support the hypothesis
- likely causes
- whether the failure is implementation, data, design, or hypothesis related
- recommended next actions

Do not bury negative findings in appendices or convert them into success language.

## Empirical Reviewer Simulation

The empirical reviewer should inspect:

- dataset suitability and leakage risk
- baseline strength and missing baselines
- metric definitions and statistical tests
- ablation coverage
- negative controls
- sample size or power notes
- failure modes
- reproducibility status
- result claim overreach

Reviewer objections should cite protocol sections, run artifacts, result artifacts, or missing artifacts. They should not invent results.

Useful commands:

```bash
gapforge parse-results --execution-id <execution-id>
gapforge empirical-claims --workspace-id <workspace-id>
gapforge analyze-results --execution-id <execution-id>
gapforge low-fpr-power-check --workspace-id <workspace-id>
gapforge empirical-review --execution-id <execution-id>
```

## Paper Package Upgrade

Paper packages should separate:

- real executed results
- failed runs
- negative results
- smoke-test outputs
- expected/hypothetical results
- placeholders and TODOs

No manuscript export should present a placeholder or expected result as if it were observed.

The v0.6 paper package may include planned experiments, smoke outputs, pilot outputs, main outputs, failed outputs, negative results, and hypothetical expected results. Each category must be labeled. If observed empirical claims are missing, the package should say planned-only or incomplete rather than filling in results.
