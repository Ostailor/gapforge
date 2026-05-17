# GapForge v2.7 Acceptance Criteria

v2.7 is accepted only if it uses the v2.6.1 paper-quality evaluation layer to harden the selected manuscript toward `conference_candidate`, or explains why `conference_candidate` remains unsupported.

## Required Outcomes

1. v2.7 aims to move the selected manuscript from `workshop_candidate` to `conference_candidate`.
2. If `conference_candidate` is not reached, v2.7 must explain blockers and required evidence.
3. Eval paper-quality score must be used as a release-gate input.

## Required Starting Baseline

v2.7 must record the v2.6/v2.6.1 baseline:

- v2.6 readiness status: `workshop_candidate`
- top-conference readiness: `false`
- likely reviewer decision: `borderline_reject`
- paper-quality status: `progress_not_success_borderline_reject`
- paper-quality score: `0.500`

The release must report the new paper-quality score and the delta from `0.500`.

## Required Documentation Criteria

The v2.7 documentation must include:

- conference-candidate hardening goal
- blocker-aware starting state after v2.6.1
- drastic review likely-decision hardening
- real benchmark fit or no-fit hardening
- baseline and ablation strengthening
- top-conference contribution framing
- external expert review requirement
- paper-quality metric usage
- manuscript revision requirements
- artifact package polish requirements
- promotion and non-promotion rules

## Required Paper-Quality Criteria

v2.7 must report:

- `paper_quality_score`
- `paper_quality_score_delta`
- `novelty_strength`
- `baseline_strength`
- `benchmark_fit`
- `statistical_adequacy`
- `related_work_completeness`
- `harsh_reviewer_likely_score`
- `manuscript_persuasiveness`
- `top_conference_readiness`

`conference_candidate` is blocked when:

- paper-quality score does not improve from `0.500`
- `top_conference_readiness` remains `not_ready`, `workshop_only`, or `not_assessable`
- harsh reviewer likely score remains `borderline_reject` or `reject_likely`
- novelty is `weak`, `defeated`, or `unknown` for the central claim
- baseline strength is `weak` or `missing`
- benchmark fit is `weak`, `no_fit`, or `unknown` while the manuscript still claims benchmark validity
- statistical adequacy is `underpowered` or `invalid` for the central claim
- manuscript persuasiveness is `low`, `confusing`, or `not_assessable`

## Required Drastic Review Criteria

v2.7 must:

1. Load or cite the v2.6 drastic rerun result.
2. Preserve the `borderline_reject` starting decision.
3. Map each objection to the hardening ledger.
4. Rerun drastic review after hardening.
5. Report the new likely decision.
6. Explain any unchanged, worsened, or still-borderline outcome.

`conference_candidate` requires no unresolved fatal objections and no unresolved central major objection.

## Required Benchmark Criteria

v2.7 must produce one of:

1. Accepted real benchmark fit evidence with bounded claims, or
2. A strengthened no-fit report with narrowed manuscript claims.

The benchmark report must cover:

- source identity and access
- license and terms
- label semantics
- task mapping
- splits, leakage, and contamination
- low-FPR denominator
- sequential-window support
- hard-negative support
- collusion or covert-coordination validity
- accepted, auxiliary, negative-only, rejected, blocked, or no-fit status

No-fit cannot be used to claim real benchmark validity.

## Required Baseline and Ablation Criteria

v2.7 must include a baseline and ablation audit that lists:

- expected reviewer baselines
- implemented baselines
- missing baselines
- tuning and threshold policy
- calibration and evaluation split policy
- low-FPR uncertainty
- sequential-window ablation status
- hard-negative ablation status
- monitor-evasion or stress-case ablation status
- failure-case analysis

Missing central baselines or ablations must block `conference_candidate` unless the manuscript explicitly narrows the affected claims.

## Required Contribution-Framing Criteria

The manuscript must make the contribution defensible under the evidence actually available.

The revised framing must:

- identify the primary contribution
- distinguish benchmark, protocol, empirical, artifact, and no-fit contributions
- compare against closest prior work
- state what remains valuable if no real benchmark fits
- preserve limitations and non-claims
- avoid top-conference acceptance or camera-ready language

## Required External Expert Review Criteria

v2.7 must include external expert review evidence or a blocked-review record.

Expert review must address:

- novelty
- benchmark fit or no-fit argument
- baseline sufficiency
- statistical adequacy
- contribution framing
- artifact usability, when practical

If review is unavailable, the release must record:

- requested reviewer type
- requested materials
- date or attempt window
- blocker reason
- risk effect on readiness

## Required Manuscript Revision Criteria

v2.7 manuscript revision must:

- link every central claim to evidence or a limitation
- update abstract and introduction contribution framing
- update related-work and closest-prior-work comparison
- integrate benchmark fit or no-fit evidence
- integrate baseline and ablation evidence
- update statistical limitations
- incorporate expert review or preserve it as risk
- remove unsupported real benchmark, deployment-validity, and superiority claims

## Required Artifact Package Polish Criteria

v2.7 artifact package must include:

- reviewer-first README or entry point
- minimal reproduction commands
- expected outputs
- environment and runtime notes
- data access and license labels
- baseline and ablation result map
- manuscript table/figure reproduction map
- known failures
- unsupported claim list
- artifact evaluation checklist

The package must remain honest about synthetic, auxiliary, negative-only, failed, and no-fit evidence.

## Release Gate Outcomes

### `conference_candidate`

Allowed only when:

- paper-quality score improves from `0.500`
- top-conference readiness is `candidate_with_risks` or stronger
- likely reviewer decision improves beyond `borderline_reject`
- benchmark fit or no-fit argument supports the actual manuscript claims
- baseline and ablation audit has no central blocker
- expert review is completed or explicitly risk-waived
- manuscript claims are traceable
- artifact package is reviewer-usable

Allowed statement:

`v2.7 reached conference_candidate for a bounded manuscript scope; this is not acceptance, likely acceptance, or camera-ready readiness.`

### `workshop_candidate`

Allowed when:

- workflow and artifacts remain strong
- claims are honest and narrowed
- paper-quality score or reviewer decision still blocks conference candidacy

Required statement:

`v2.7 remains workshop_candidate because conference-candidate blockers remain.`

### `revise_for_reviews`

Allowed when:

- hardening produced useful evidence or revisions
- major paper-quality, benchmark, baseline, expert-review, or manuscript blockers remain

### `benchmark_no_fit`

Allowed when:

- no real benchmark fits after recorded review
- manuscript claims are narrowed
- the release explains whether the no-fit result is itself a contribution or a blocker

### `no_go`

Required when:

- claims remain unsupported
- fake citations, fake results, copied prose, hidden blockers, or synthetic deployment-validity claims appear
- artifact package polish hides limitations
- manuscript framing misrepresents evidence

## Fail Conditions

v2.7 fails if:

- it omits the v2.6 paper-quality baseline
- it does not use paper-quality score
- it treats workflow pass as paper-quality pass
- it promotes to `conference_candidate` while likely reviewer decision remains `borderline_reject` without explicit refusal or risk logic
- it claims real benchmark validity from no-fit, auxiliary, negative-only, or synthetic evidence
- it omits baseline or ablation blockers
- it skips external expert review without recording the risk
- it revises manuscript claims without claim-to-evidence mapping
- it hides blockers when `conference_candidate` is not reached

## Completion Evidence

The v2.7 final report must include:

- changed readiness decision
- previous and new paper-quality score
- paper-quality metric table
- drastic review decision delta
- benchmark fit or no-fit summary
- baseline and ablation audit summary
- external expert review summary or blocked-review record
- manuscript revision summary
- artifact package polish summary
- blockers and next evidence if not `conference_candidate`
