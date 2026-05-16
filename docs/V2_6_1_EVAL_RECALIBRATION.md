# GapForge v2.6.1 Eval Recalibration Plan

v2.6.1 is a documentation and gate-design patch after v2.6 reached `workshop_candidate` while drastic review still predicted `borderline_reject`.

The central correction is that current eval is not proof of top-conference quality. Existing eval scores remain useful for regression, safety, and workflow checks, but they must not be interpreted as evidence that a paper is ready for a top conference.

## Goal

v2.6.1 recalibrates evaluation into four separately reported layers:

1. regression eval
2. safety eval
3. workflow eval
4. paper-quality eval

Future release gates must report paper-quality status separately from regression, safety, and workflow status. A release can pass regression, safety, and workflow checks while still reporting `paper_quality_status: not_conference_ready`.

## Starting Point

v2.6 fixed the fatal v2.5 blockers:

- missing loadable related-work matrix
- missing loadable artifact evaluation package

It also produced a more realistic release decision: `workshop_candidate`.

The remaining problem is evaluation calibration. The release machinery can verify that artifacts exist, parse, load, and preserve known blockers. It can reject fake citations, fake results, copied prose, and unsupported claims. It can also confirm that rerun review and revision-package workflows happened. Those checks are necessary, but they are not sufficient for top-conference readiness.

## Layer 1: Regression Eval

Regression eval protects expected system behavior and prevents known failures from returning.

It covers:

- fixture correctness
- schema/load/save behavior
- release gate behavior
- known blockers preserved

Expected evidence:

- deterministic fixture reports
- schema compatibility checks
- load/save round trips
- release-gate JSON snapshots
- blocker preservation tests

Regression eval answers:

`Did the software keep behaving as expected?`

It does not answer:

`Is the paper strong?`

## Layer 2: Safety Eval

Safety eval protects research integrity boundaries.

It covers:

- fake citation rejection
- fake result rejection
- no copied prose
- no unsupported novelty
- no hidden missing categories

Expected evidence:

- adversarial fixtures for fake identifiers, fake datasets, fake baselines, and fake results
- citation and bibliography validation
- source-use and prose-copy checks
- unsupported-claim blocking
- related-work category visibility checks

Safety eval answers:

`Did the system avoid unsafe or dishonest research claims?`

It does not answer:

`Would reviewers find the contribution compelling?`

## Layer 3: Workflow Eval

Workflow eval checks whether the required paper-production process ran and left inspectable artifacts.

It covers:

- artifacts exist
- matrix/package loads
- reviewer rerun happens
- revision package exists

Expected evidence:

- loadable related-work matrix
- loadable artifact evaluation package
- reviewer rerun artifact
- drastic revision plan status
- venue revision package
- release-gate and dashboard reports

Workflow eval answers:

`Did the expected workflow complete with inspectable artifacts?`

It does not answer:

`Are those artifacts persuasive enough for a top conference?`

## Layer 4: Paper-Quality Eval

Paper-quality eval estimates the manuscript's scientific and venue-readiness strength. It must be reported separately because it judges paper quality, not software correctness or artifact presence.

It covers:

- novelty strength
- baseline strength
- benchmark fit
- statistical adequacy
- related-work completeness
- harsh reviewer likely score
- manuscript persuasiveness
- top-conference readiness

Expected evidence:

- calibrated harsh-review rubric
- novelty and closest-prior-work analysis
- baseline comparison audit
- benchmark-source fit assessment
- power and uncertainty review
- related-work completeness assessment
- manuscript persuasion review
- explicit top-conference readiness classification

Paper-quality eval answers:

`Is the paper likely strong enough for the target venue class?`

It does not answer:

`Did the code avoid regressions?`

## Status Vocabulary

Each layer should report one of:

- `pass`
- `pass_with_warnings`
- `incomplete`
- `fail`
- `not_run`

Paper-quality eval additionally reports:

- `top_conference_ready`
- `conference_candidate`
- `workshop_candidate`
- `borderline_reject`
- `reject_likely`
- `not_assessable`

The release gate must not collapse these into one green status. For v2.6.1, a realistic outcome may be:

- regression eval: `pass`
- safety eval: `pass`
- workflow eval: `pass`
- paper-quality eval: `borderline_reject`
- release status: `workshop_candidate_with_paper_quality_blockers`

## Release Gate Reporting Requirement

Future release gates must include a separate section or JSON object for paper-quality status:

```json
{
  "regression_status": "pass",
  "safety_status": "pass",
  "workflow_status": "pass",
  "paper_quality_status": "borderline_reject",
  "paper_quality_summary": {
    "novelty_strength": "moderate",
    "baseline_strength": "weak",
    "benchmark_fit": "partial",
    "statistical_adequacy": "underpowered_for_top_conference",
    "related_work_completeness": "adequate_with_risks",
    "harsh_reviewer_likely_score": "borderline_reject",
    "manuscript_persuasiveness": "insufficient",
    "top_conference_readiness": "not_ready"
  }
}
```

## Implementation Plan

1. Preserve existing fixture and release-gate evals as regression eval.
2. Classify fake-citation, fake-result, copied-prose, unsupported-novelty, and hidden-missing-category checks as safety eval.
3. Classify artifact existence, matrix/package loading, reviewer rerun, and revision package generation as workflow eval.
4. Add a separate paper-quality report with the metrics in `docs/V2_6_1_PAPER_QUALITY_METRICS.md`.
5. Require future release notes to state whether paper-quality status agrees or disagrees with workflow status.
6. Treat disagreement as normal and useful. A workflow pass with `borderline_reject` paper quality is a successful diagnostic, not a contradiction.

## Non-Goals

v2.6.1 does not claim:

- top-conference acceptance
- camera-ready readiness
- real deployment validity
- exhaustive related-work coverage
- reviewer-score prediction certainty
- that any single automated metric can replace human expert judgment

## Handoff to Future Releases

The next release should decide whether to implement CLI/API fields for the four-layer report. Until then, release notes and docs must preserve the distinction manually.

