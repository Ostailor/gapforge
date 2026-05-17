# GapForge v2.7 Conference-Candidate Hardening

v2.7 hardening is the paper-quality work required after v2.6 reached `workshop_candidate` but not top-conference readiness. The purpose is to decide whether the selected benchmark manuscript can honestly become a `conference_candidate`.

The current hardening baseline is:

- v2.6 status: `workshop_candidate`
- likely reviewer decision: `borderline_reject`
- top-conference readiness: `false`
- paper-quality status: `progress_not_success_borderline_reject`
- paper-quality score: `0.500`

## Hardening Principle

v2.7 must improve the paper, not the label. The release gate may promote readiness only when paper-quality evidence improves. If evidence does not improve enough, the correct outcome is a precise blocker report.

## Hardening Ledger

v2.7 must maintain a hardening ledger with one entry per issue:

- `issue_id`
- source: drastic review, paper-quality metric, expert review, benchmark fit, baseline audit, manuscript review, artifact review
- severity: fatal, major, borderline, minor
- affected claim
- required evidence
- owner or workstream
- resolution status
- evidence links
- release effect

No issue can be closed by wording alone unless the issue is specifically an overclaim and the claim is removed or narrowed.

## 1. Drastic Review Likely Decision

The v2.6 likely decision `borderline_reject` is the first-class hardening target.

Required actions:

- preserve the v2.6 drastic rerun artifact
- extract objections into the hardening ledger
- classify each objection as novelty, benchmark validity, baseline strength, statistical adequacy, artifact usability, claim traceability, or writing/framing
- revise evidence or manuscript claims for each resolvable objection
- rerun drastic review after revisions

Required output:

- previous likely decision
- new likely decision
- unresolved objections
- reviewer-score or recommendation delta
- explanation for any unchanged or worsened decision

`conference_candidate` requires no unresolved fatal objections and a likely decision stronger than `borderline_reject`, or an explicit release decision that refuses promotion.

## 2. Real Benchmark Fit or No-Fit Argument

v2.7 must harden the benchmark story.

Accepted benchmark-fit path:

- source identity, version, access route, retrieval date, license, and attribution are recorded
- label semantics map to the selected low-FPR collusion-audit claim
- split, leakage, contamination, and redistribution risks are documented
- adapter conversion is deterministic and inspectable
- unsupported dimensions remain unsupported
- manuscript claims are bounded to the source mapping

Accepted no-fit path:

- candidate inventory is complete enough for the target claim
- each rejected source has a concrete exclusion reason
- the no-fit report distinguishes no collusion validity, negative-only specificity support, auxiliary safety support, and access/license blockers
- manuscript claims are narrowed to synthetic, negative-only, or protocol/artifact contributions as appropriate
- future evidence needed for real benchmark validity is specified

No-fit is allowed as an honest result. It is not an upgrade to real benchmark validity.

## 3. Baseline and Ablation Strength

v2.7 must make comparison evidence reviewable and hard to dismiss.

Baseline audit must include:

- expected baselines from related work and reviewer objections
- implemented baselines
- missing baselines
- tuning and threshold policy
- calibration set and evaluation split policy
- low-FPR denominator and uncertainty
- reason each baseline is relevant or excluded

Ablation audit must include:

- sequential-window ablation
- threshold-calibration ablation
- hard-negative ablation
- monitor-evasion or stress-case ablation
- source-evidence-type ablation when public, auxiliary, and synthetic evidence are mixed
- failure-case analysis

Conference candidacy is blocked by missing obvious baselines, underpowered comparisons, or ablations that are needed to support the central claim.

## 4. Top-Conference Contribution Framing

v2.7 must make the strongest defensible contribution obvious.

The contribution frame must answer:

- What is the paper's primary contribution?
- Is the contribution a benchmark, measurement protocol, empirical result, artifact, or negative/no-fit finding?
- What closest prior work threatens novelty?
- What claim remains valuable if no public benchmark fits?
- What would a skeptical reviewer still reject?

Required manuscript surfaces:

- abstract contribution statement
- introduction contribution list
- closest-prior-work comparison
- evidence-label table
- limitations and non-claims
- reviewer-facing summary of what changed since v2.6

The contribution frame must not inflate `workshop_candidate` evidence into top-conference readiness.

## 5. External Expert Review

v2.7 must seek external expert review because paper-quality metrics are not a substitute for domain judgment.

Expert review request must include:

- current manuscript or venue-shaped draft
- related-work matrix
- benchmark fit or no-fit report
- baseline and ablation audit
- artifact package instructions
- specific questions on novelty, benchmark validity, baseline sufficiency, statistics, and contribution framing

Expert review output must record:

- reviewer identity or anonymization/provenance policy
- review date
- expertise area
- review scope
- major objections
- required changes
- readiness recommendation
- author response or blocker status

If external review is unavailable, v2.7 must record the attempted route and treat the missing review as a paper-quality risk.

## 6. Paper-Quality Metrics

v2.7 must report the v2.6.1 metrics before and after hardening.

Required report fields:

```json
{
  "previous_paper_quality_score": 0.500,
  "new_paper_quality_score": 0.0,
  "paper_quality_score_delta": 0.0,
  "novelty_strength": "unknown",
  "baseline_strength": "unknown",
  "benchmark_fit": "unknown",
  "statistical_adequacy": "unknown",
  "related_work_completeness": "unknown",
  "harsh_reviewer_likely_score": "unknown",
  "manuscript_persuasiveness": "unknown",
  "top_conference_readiness": "not_assessable"
}
```

The final report must replace unknown values with assessed values or explain why the metric is not assessable.

Conference candidacy requires:

- paper-quality score improved from the v2.6 baseline
- `top_conference_readiness` is at least `candidate_with_risks`
- `harsh_reviewer_likely_score` is not `borderline_reject` or `reject_likely`
- no metric has a fatal blocking value unless the release refuses promotion

## 7. Manuscript Revision

The manuscript revision must be evidence-led.

Required revisions:

- update abstract and introduction around the hardened contribution
- add or update closest-prior-work comparison
- integrate benchmark fit or no-fit argument
- integrate baseline and ablation evidence
- update statistical limitations and uncertainty language
- update artifact package references
- incorporate external expert feedback
- remove unsupported claims
- preserve limitations prominently

The revision must include a claim-to-evidence map. Any claim without evidence must be removed, narrowed, or marked as future work.

## 8. Artifact Package Polish

v2.7 artifact polish means the package is usable by a reviewer under time pressure.

Required polish:

- reviewer-first entry point
- minimal reproduction path
- exact command list
- expected outputs and hashes where available
- environment and runtime notes
- data access and license labels
- baseline and ablation result map
- manuscript table/figure reproduction map
- known failures
- unsupported claim list
- artifact evaluation checklist

Artifact package polish must preserve no-fit, negative, failed, or synthetic-only labels. It must not hide limitations to look cleaner.

## Promotion Rules

`conference_candidate` is allowed only when:

- paper-quality score improves from `0.500`
- top-conference readiness is `candidate_with_risks` or stronger
- likely reviewer decision improves beyond `borderline_reject`
- benchmark fit or no-fit argument supports the manuscript's actual claims
- baseline and ablation audit has no unresolved central blockers
- external expert review is completed or its absence is explicitly risk-waived
- manuscript claims are traceable
- artifact package is reviewer-usable

If these conditions are not met, v2.7 must keep or downgrade readiness and explain the blockers.

## Completion Report

The v2.7 hardening report must include:

- v2.6 baseline metrics
- hardening ledger summary
- benchmark fit or no-fit decision
- baseline and ablation audit result
- external expert review result
- manuscript revision summary
- artifact package polish summary
- new paper-quality metrics and score delta
- rerun drastic review likely decision
- final readiness decision
- blockers if `conference_candidate` is not reached
