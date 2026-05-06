---
name: baseline-selection
description: Use when registering, selecting, or reviewing baselines for GapForge v0.6 experiment protocols and workspaces.
---

# Baseline Selection

## Purpose
Make comparators explicit so empirical claims are not made against weak or hidden baselines.

## When To Use
- Pulling baseline candidates from related-work matrices.
- Registering trivial, heuristic, prior-work, supervised, statistical, ablation, or oracle baselines.
- Reviewing readiness before execution or paper export.

## Inputs
- Workspace ID, direction ID, related-work matrix, protocol, source paper IDs, implementation path/URL, risk if omitted.

## Outputs
- `BaselineRecord`
- `BaselineCard`
- readiness blockers

## Required Artifacts
- `baselines/baseline-*.record.json`
- `baselines/cards/baseline-*.card.md`
- `baselines/baseline_registry.md`

## Procedure
1. Load related-work matrix and protocol baseline requirements.
2. Register required baselines with source paper IDs when available.
3. Mark whether code exists and where.
4. Flag missing must-have baselines as blockers.
5. Feed baseline IDs into run manifests.

## Validation Checklist
- [ ] At least one credible baseline exists for nontrivial experiments.
- [ ] Must-cite baseline papers are linked.
- [ ] Required baselines have implementation path, code URL, or blocker.
- [ ] Reviewer risk if omitted is recorded.

## Failure Modes
- Comparing only to a trivial baseline when prior work exists.
- Inventing implementation availability.
- Omitting must-have baseline from manifest.

## Examples
```bash
gapforge baseline-from-related-work --project-id PROJECT --direction-id DIRECTION
gapforge baseline-register --workspace-id WORKSPACE --name "heuristic baseline" --baseline-type heuristic --implementation-path code/src/baselines.py
gapforge baseline-list --workspace-id WORKSPACE
```

## Evidence Rules
Baseline claims about prior work must cite known paper IDs or related-work entries.

## Uncertainty Rules
If implementation is unavailable, record risk and do not mark experiment paper-ready.

## Chain-Of-Thought Rule
Store only public reasoning summaries. Do not request or store hidden chain-of-thought.

## No Fake Results
Do not invent baseline scores, code URLs, or prior-work results.
