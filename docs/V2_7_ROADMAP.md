# GapForge v2.7 Roadmap

v2.7 is the Conference-Candidate Hardening release for the locked selected benchmark:

- Idea ID: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Title: `Sequential specificity benchmark for low-FPR collusion audits`
- Benchmark ID: `benchmark-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Manuscript ID: `manuscript-sequential-specificity-benchmark-for-low-fpr-collusion-audits`

v2.6 fixed the fatal v2.5 blockers and reached `workshop_candidate`. v2.6.1 then recalibrated eval interpretation: workflow success is not paper success. The current v2.6 release gate reports:

- readiness status: `workshop_candidate`
- top-conference readiness: `false`
- likely reviewer decision: `borderline_reject`
- paper-quality status: `progress_not_success_borderline_reject`
- paper-quality score: `0.500`

v2.7 exists to move the paper from `workshop_candidate` toward `conference_candidate` by addressing the paper-quality blockers directly. If `conference_candidate` is not reached, v2.7 must explain the blockers with enough specificity that the next release has a concrete evidence plan.

## Goal

v2.7 aims to produce an honest `conference_candidate` decision for the bounded manuscript scope. This is not an acceptance claim, likely-acceptance claim, or camera-ready claim.

The release may still end as `workshop_candidate`, `revise_for_reviews`, `benchmark_no_fit`, or `no_go` when the evidence does not support `conference_candidate`.

## Starting State

v2.7 starts from the v2.6/v2.6.1 evidence state:

- Related-work matrix is loadable.
- Artifact package is loadable.
- Real benchmark path is explicit no-fit or no-fit-only; real benchmark validity must not be claimed without new evidence.
- Drastic review predicts `borderline_reject`.
- Workshop readiness is true.
- Top-conference readiness is false.
- Paper-quality score is capped at `0.500` by the borderline-reject drastic review.

These facts are inputs to v2.7, not language to soften.

## Workstreams

### 1. Drastic Review Decision Hardening

v2.7 must convert the v2.6 `borderline_reject` diagnosis into an issue-by-issue hardening plan. The plan must:

- list every remaining fatal, major, and borderline objection
- map each objection to evidence, manuscript revision, experiment, benchmark/no-fit argument, baseline/ablation change, or external expert review
- state which objections cannot be resolved in v2.7
- rerun drastic review after revisions using the same or stricter standard
- report the new likely decision

`conference_candidate` is blocked if the rerun likely decision remains `borderline_reject` or `reject_likely` unless the release explicitly records why the gate is preserving a weaker outcome.

### 2. Real Benchmark Fit or No-Fit Argument

v2.7 must strengthen the benchmark argument in one of two ways:

1. Accept a real external/public benchmark adapter with bounded claims, source metadata, license/access review, label semantics, splits, leakage analysis, and fit to the selected protocol.
2. Produce a stronger no-fit argument explaining why no public source supports the primary collusion-validity claim and exactly how the manuscript is narrowed.

The no-fit path can support honesty and workshop readiness. It cannot by itself support real benchmark validity or deployment validity.

### 3. Baseline and Ablation Strength

v2.7 must make baseline and ablation evidence hard to dismiss. It must audit:

- required reviewer-expected baselines
- implemented baselines and tuning policy
- threshold calibration for low-FPR claims
- negative-only, auxiliary, and synthetic-only evidence labels
- ablations for sequential windows, hard negatives, monitor-evasion stress, and thresholding
- uncertainty and power for each comparison

Missing obvious baselines or ablations block `conference_candidate` unless the manuscript narrows claims and records the missing evidence as a blocker.

### 4. Top-Conference Contribution Framing

v2.7 must reframe the contribution around the strongest defensible claim. The framing must:

- separate benchmark contribution, measurement protocol, artifact contribution, and empirical claims
- compare the contribution against closest prior work
- state what is new even under the benchmark no-fit constraint
- state what is not proven
- make the main contribution visible in the abstract, introduction, limitation section, and reviewer-facing summary

Top-conference framing must not rely on inflated novelty, synthetic benchmark validity, or acceptance-style language.

### 5. External Expert Review

v2.7 must obtain or prepare for external expert review. Accepted evidence includes:

- signed or attributable expert review
- anonymized expert review with provenance
- recorded domain-specialist checklist
- blocked review record explaining who was asked, what was requested, and why review was unavailable

At least one expert review attempt must address benchmark fit, baseline sufficiency, and contribution framing. If no expert review is completed, `conference_candidate` requires an explicit risk waiver and blocker explanation.

### 6. Paper-Quality Metrics

v2.7 must use the v2.6.1 paper-quality metrics as release-gate inputs:

- `novelty_strength`
- `baseline_strength`
- `benchmark_fit`
- `statistical_adequacy`
- `related_work_completeness`
- `harsh_reviewer_likely_score`
- `manuscript_persuasiveness`
- `top_conference_readiness`

The v2.6 release-gate paper-quality score `0.500` is the baseline. v2.7 must report the new score, the delta, and the evidence that caused the change. A workflow pass cannot upgrade the paper-quality score.

### 7. Manuscript Revision

v2.7 must revise the manuscript after paper-quality blockers are mapped. The revision must:

- link claims to related work, benchmark/no-fit evidence, baselines, ablations, statistics, artifact package, or limitations
- remove unsupported real benchmark and deployment-validity language
- make the contribution framing top-conference-legible without overclaiming
- incorporate external expert feedback or preserve it as unresolved risk
- preserve negative and no-fit evidence

### 8. Artifact Package Polish

v2.7 must polish the artifact package for reviewer use, not just loadability. The package must include:

- reviewer-first README
- one-command or minimal-command reproduction path where possible
- expected runtime and hardware notes
- clear data/license/access labels
- baseline and ablation output mapping
- paper table and figure reproduction map
- known failures and unsupported claims
- artifact evaluation checklist

Artifact polish cannot compensate for weak paper-quality evidence, but poor artifact usability can block `conference_candidate`.

## Milestones

1. Load v2.6 release-gate JSON and record the v2.6.1 paper-quality baseline.
2. Build a blocker ledger from the drastic rerun, paper-quality assessment, benchmark/no-fit report, baseline inventory, and manuscript revision package.
3. Reassess real benchmark candidates or strengthen the no-fit report.
4. Audit baseline and ablation coverage against reviewer expectations.
5. Rework contribution framing against closest prior work and available evidence.
6. Complete or record external expert review.
7. Revise manuscript sections tied to claims, limitations, contribution framing, baselines, and benchmark fit.
8. Polish the artifact package for reviewer execution and inspection.
9. Rerun paper-quality eval and drastic review.
10. Run the v2.7 release gate and record the readiness decision.

## Release Outcomes

Allowed v2.7 outcomes:

- `conference_candidate`: paper-quality metrics and rerun review support a bounded top-conference submission candidate.
- `workshop_candidate`: artifacts and workflow remain strong, but paper-quality blockers still limit the manuscript.
- `revise_for_reviews`: meaningful hardening occurred, but reviewer, benchmark, baseline, expert-review, or manuscript blockers remain.
- `benchmark_no_fit`: no real benchmark fits and claims are narrowed; top-conference readiness depends on whether the no-fit contribution is strong enough.
- `no_go`: core claims, evidence, artifacts, citations, or result integrity are unsafe or unsupported.

If `conference_candidate` is not reached, v2.7 must explain the blockers, required evidence, and whether the strongest honest next step is more experiments, benchmark acquisition, manuscript reframing, or abandoning the top-conference target.

## Non-Claims

v2.7 must not claim:

- acceptance
- likely acceptance
- camera-ready readiness
- deployment-valid collusion auditing
- real benchmark validity from no-fit or synthetic evidence
- reviewer consensus without external review evidence
- top-conference readiness when paper-quality metrics disagree
