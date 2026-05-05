---
name: experiment-designer
description: Use when converting novelty-checked research gaps into falsifiable experiment plans with baselines, metrics, ablations, risks, and implementation steps.
---

# Experiment Designer

## Purpose
Convert validated or non-rejected research gaps into concrete experiment-ready plans. Prefer decisive, falsifiable experiments over vague research directions.

## When To Use
- Use after novelty gate.
- Use only for gaps with `pursue`, `revise`, or explicitly allowed rejected status.
- CLI: `gapforge design-experiments --run-id RUN_ID` or `gapforge design-experiment --gap-id GAP_ID`.

## Inputs
- `Gap` records
- `NoveltyAssessment` records
- `PaperNote` records
- claim ledger
- research topic

## Outputs
- `ExperimentPlan` records
- `experiments.json`
- `experiments.md`
- `implementation_tasks.md`

## Required Artifacts
- `novelty_gate.json`
- `gaps.json`
- `paper_notes.json`
- `experiments.json`
- `experiments.md`
- `implementation_tasks.md`

## Procedure
1. Skip rejected novelty assessments by default.
2. Choose gaps with the clearest measurable failure mode.
3. State one hypothesis and one core claim being tested.
4. Define the minimum viable experiment.
5. Name datasets needed and label/provenance requirements.
6. Name strong baselines, including closest prior work.
7. Name metrics tied to the gap.
8. Add statistical tests, ablations, failure modes, compute requirements, implementation steps, expected result patterns, falsification condition, reviewer-killer result, risks, and ethical/safety considerations.
9. Keep confidence conservative and uncertainty explicit.

## Quality Bar
- Every experiment needs baselines, metrics, and falsification conditions.
- No experiment should be marked paper-ready without novelty assessment.
- Prefer experiments that could kill the idea quickly.
- Do not invent datasets, results, or benchmark scores.
- Publishability criteria must name what result would convince a serious reviewer.

## Failure Modes
- Designing around a rejected idea without explicit override.
- Producing vague agendas instead of executable experiments.
- Missing closest-prior-work baselines.
- Omitting falsification conditions.
- Treating risky data or detection settings as harmless.

## Validation Checklist
- [ ] `experiments.json`, `experiments.md`, and `implementation_tasks.md` exist.
- [ ] No rejected gap is used unless explicitly allowed.
- [ ] Each experiment has baselines and metrics.
- [ ] Each experiment says what would falsify the idea.
- [ ] Each experiment explains what would make the result publishable.
- [ ] Risks and ethical/safety considerations are explicit.

## Examples
Design experiments for all non-rejected gaps:

```bash
gapforge design-experiments --run-id 20260505T002206Z-low-false-positive-collusion-detection
```

Design one experiment:

```bash
gapforge design-experiment --run-id 20260505T002206Z-low-false-positive-collusion-detection --gap-id gap-12345
```
