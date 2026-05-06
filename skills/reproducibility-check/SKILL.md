---
name: reproducibility-check
description: Use when auditing whether a GapForge v0.6 experiment workspace or execution can be rerun and trusted as an artifact-backed result.
---

# Reproducibility Check

## Purpose
Audit whether empirical outputs have enough metadata, inputs, logs, and hashes to be rerun or honestly labeled incomplete.

## When To Use
- After an execution completes or fails.
- Before empirical review.
- Before paper package v2 export or paper-ready claims.

## Inputs
- Workspace ID or execution ID.
- Dataset cards, baseline cards, metrics, manifest, logs, result artifacts, parsed results.

## Outputs
- `ReproducibilityCheckResult`
- Markdown/JSON reproducibility reports

## Required Artifacts
- dataset cards
- baseline cards
- metric definitions
- run manifest
- stdout/stderr logs
- result artifact hashes
- confidence interval notes for low-FPR claims when applicable

## Procedure
1. Run `gapforge reproducibility-check`.
2. Inspect blockers and warnings.
3. Fix missing cards, manifests, logs, result hashes, seeds, or labels.
4. Do not export paper-ready results when status is fail.

## Validation Checklist
- [ ] Dataset cards exist.
- [ ] Baseline cards exist.
- [ ] Metric definitions exist.
- [ ] Seed/environment/command are recorded.
- [ ] Result artifacts are hashed.
- [ ] Fixture/synthetic data is labeled.

## Failure Modes
- Missing seed is ignored.
- Missing dataset card is downgraded incorrectly.
- Fake/synthetic data is unlabeled.
- Reproducibility pass is mistaken for positive result.

## Examples
```bash
gapforge reproducibility-check --execution-id EXECUTION
gapforge reproducibility-check --workspace-id WORKSPACE
```

## Evidence Rules
Reproducibility evidence supports auditability, not truth of the hypothesis.

## Uncertainty Rules
Use pass/warning/fail. Keep blockers next to any empirical claim.

## Chain-Of-Thought Rule
Store only public reasoning summaries. Do not request or store hidden chain-of-thought.

## No Fake Results
Do not mark a run reproducible by inventing missing files, hashes, seeds, datasets, or environments.
