# GapForge v2.6.1 Acceptance Criteria

v2.6.1 is accepted when GapForge documentation and release guidance make eval calibration explicit enough that future releases cannot confuse workflow success with paper quality.

## Required Outcomes

1. Docs explicitly say current eval is not proof of top-conference quality.
2. v2.6.1 defines paper-quality metrics separately from workflow metrics.
3. Future release gates must report paper-quality status separately.

## Required Documentation Criteria

The v2.6.1 documentation must include:

- a four-layer eval taxonomy
- regression eval definition
- safety eval definition
- workflow eval definition
- paper-quality eval definition
- explicit paper-quality metrics
- release-gate reporting guidance that keeps paper-quality status separate
- limitation language for README, known limitations, and release process

## Four-Layer Eval Criteria

### Regression Eval

Must cover:

- fixture correctness
- schema/load/save
- release gate behavior
- known blockers preserved

Acceptance condition:

Regression eval is documented as software behavior protection, not paper-quality evidence.

### Safety Eval

Must cover:

- fake citation rejection
- fake result rejection
- no copied prose
- no unsupported novelty
- no hidden missing categories

Acceptance condition:

Safety eval is documented as research-integrity protection, not proof of reviewer enthusiasm or venue readiness.

### Workflow Eval

Must cover:

- artifacts exist
- matrix/package loads
- reviewer rerun happens
- revision package exists

Acceptance condition:

Workflow eval is documented as process completion evidence, not proof that the paper is persuasive or top-conference ready.

### Paper-Quality Eval

Must cover:

- novelty strength
- baseline strength
- benchmark fit
- statistical adequacy
- related-work completeness
- harsh reviewer likely score
- manuscript persuasiveness
- top-conference readiness

Acceptance condition:

Paper-quality eval is documented as a separate readiness assessment that can fail even when regression, safety, and workflow evals pass.

## Release Gate Criteria

Future release gates must report:

- `regression_status`
- `safety_status`
- `workflow_status`
- `paper_quality_status`

They should also report paper-quality submetrics when available.

The gate must not reduce the four layers to one pass/fail result. A valid release report may say:

`regression_status=pass, safety_status=pass, workflow_status=pass, paper_quality_status=borderline_reject`.

## Fail Conditions

v2.6.1 fails if:

- eval docs imply automated fixtures prove top-conference readiness
- workflow metrics are used as paper-quality metrics
- paper-quality status is hidden inside a generic release pass
- `workshop_candidate` is described as conference-ready
- drastic review `borderline_reject` signals are softened without evidence
- future gates are allowed to omit paper-quality status

## Non-Claims

v2.6.1 does not claim:

- accepted paper status
- camera-ready readiness
- top-conference readiness
- reviewer-score prediction certainty
- exhaustive related-work coverage
- real-world benchmark validity beyond recorded evidence

