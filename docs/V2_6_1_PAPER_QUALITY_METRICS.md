# GapForge v2.6.1 Paper-Quality Metrics

Paper-quality metrics are separate from workflow metrics. Workflow metrics ask whether the process ran and artifacts exist. Paper-quality metrics ask whether the manuscript is scientifically strong and persuasive enough for a target venue class.

Current eval is not proof of top-conference quality. These metrics are intended to make that gap visible.

## Required Metrics

| Metric | Question | Suggested Values |
| --- | --- | --- |
| `novelty_strength` | Is the contribution clearly new relative to closest prior work? | `strong`, `moderate`, `weak`, `defeated`, `unknown` |
| `baseline_strength` | Are comparisons credible, relevant, and hard to dismiss? | `strong`, `adequate`, `weak`, `missing`, `not_applicable` |
| `benchmark_fit` | Does the benchmark match the paper's claimed problem? | `strong`, `partial`, `weak`, `no_fit`, `unknown` |
| `statistical_adequacy` | Are sample size, uncertainty, correction, and power adequate for the claims? | `adequate`, `limited`, `underpowered`, `invalid`, `not_applicable` |
| `related_work_completeness` | Does the related-work matrix cover the categories reviewers will expect? | `complete`, `adequate_with_risks`, `incomplete`, `misleading`, `unknown` |
| `harsh_reviewer_likely_score` | What would a skeptical calibrated reviewer likely recommend? | `accept_like`, `weak_accept_like`, `borderline`, `borderline_reject`, `reject_likely` |
| `manuscript_persuasiveness` | Does the manuscript make a coherent, well-supported case? | `high`, `moderate`, `low`, `confusing`, `not_assessable` |
| `top_conference_readiness` | Is the paper ready for a top-conference submission target? | `ready`, `candidate_with_risks`, `workshop_only`, `not_ready`, `not_assessable` |

## Metric Guidance

### Novelty Strength

Assess novelty against closest prior work, not against a generic topic description.

Strong novelty requires:

- explicit closest-prior-work comparison
- clear difference in task, benchmark, method, measurement, or empirical claim
- no hidden prior work that collapses the contribution

Weak novelty should block top-conference readiness even when the workflow artifacts are complete.

### Baseline Strength

Assess whether the baselines match what reviewers will expect for the claim.

Baseline strength is weak when:

- obvious baselines are missing
- comparisons are fixture-only
- baselines are under-tuned or poorly justified
- the manuscript claims superiority without adequate comparison

### Benchmark Fit

Assess whether the benchmark actually measures the claimed phenomenon.

Benchmark fit is partial or weak when:

- source labels do not match the claimed behavior
- synthetic traces are used for real-world validity claims
- the benchmark only supports an auxiliary slice of the contribution
- contamination, split, license, or access issues limit interpretation

### Statistical Adequacy

Assess whether the statistical design supports the strength of the claims.

Top-conference readiness should be blocked when:

- low-FPR claims are underpowered
- sequential/repeated-look correction is missing
- confidence intervals contradict strong claims
- sample-size plans were created after result inspection

### Related-Work Completeness

Assess whether the related-work matrix covers reviewer-expected categories and closest prior work.

Completeness is not the same as loadability. A matrix can load and still be incomplete for paper-quality purposes.

### Harsh Reviewer Likely Score

This is a calibrated critique estimate, not an acceptance prediction. It should preserve severe objections rather than average them away.

The score should consider:

- novelty objection severity
- benchmark validity objections
- missing-baseline objections
- statistical objections
- artifact and reproducibility objections
- writing and positioning objections

### Manuscript Persuasiveness

Assess the argument the reader actually sees.

Persuasiveness is low when:

- contributions are hard to identify
- claims are technically correct but undersold or overclaimed
- limitations overwhelm the main result
- tables, figures, or examples do not support the story
- reviewer objections are answered only by caveats

### Top-Conference Readiness

This is the final paper-quality classification. It must be reported separately from release-gate mechanics.

`ready` requires strong or adequate status across novelty, baseline, benchmark fit, statistics, related work, reviewer score, and manuscript persuasiveness.

`workshop_only` or `not_ready` can coexist with regression, safety, and workflow passes.

## Aggregation Rule

Use conservative aggregation:

- Any `defeated` novelty, `missing` baseline, `no_fit` benchmark, `invalid` statistics, or `misleading` related work blocks `top_conference_readiness: ready`.
- Any `reject_likely` harsh-review estimate blocks `ready`.
- Any `borderline_reject` harsh-review estimate requires `candidate_with_risks` or weaker.
- `workflow_status: pass` cannot upgrade paper-quality status.
- `safety_status: pass` cannot upgrade paper-quality status.

## Reporting Shape

Paper-quality reports should include:

- metric values
- evidence links
- top objections
- strongest positive case
- blocker list
- exact work needed to improve one readiness level

Recommended compact form:

```json
{
  "paper_quality_status": "borderline_reject",
  "top_conference_readiness": "not_ready",
  "metrics": {
    "novelty_strength": "moderate",
    "baseline_strength": "weak",
    "benchmark_fit": "partial",
    "statistical_adequacy": "limited",
    "related_work_completeness": "adequate_with_risks",
    "harsh_reviewer_likely_score": "borderline_reject",
    "manuscript_persuasiveness": "low"
  },
  "interpretation": "Workflow artifacts are present, but the manuscript is not yet persuasive enough for a top-conference claim."
}
```

