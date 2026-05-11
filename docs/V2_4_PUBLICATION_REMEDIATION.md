# GapForge v2.4 Publication Remediation

v2.4 remediates the v2.3 publication blocker for the selected benchmark. It starts from an artifact-backed synthetic main benchmark, not from publication readiness.

## Starting State

v2.3 produced:

- powered synthetic `alpha=0.001` count plan
- main dataset with 2995 negative traces, 500 positive traces, and 2139 hard-negative traces
- completed main execution
- 15 monitor runs
- 10 sequential metric results
- metrics, predictions, baseline comparison, error analysis, and low-FPR report artifacts
- go/no-go decision `revise_benchmark`
- publication readiness `not_ready`
- manuscript status `not_ready`

The fatal blocker is missing real related work. Publication remediation cannot pass until required categories have real attached paper records or dependent claims are dropped.

## Remediation Gates

### 1. Related-Work Gate

Pass requires:

- every required category is `complete` or `complete_with_warning`
- optional analogy categories are complete or `dropped_not_used`
- all records have traceable metadata
- fake-citation and BibTeX audits pass
- matrix implications are linked to manuscript sections

Fallback-only related work blocks publication readiness.

### 2. Closest-Prior-Work Gate

Pass requires:

- closest-prior-work dossier refreshed from real records
- direct and near priors are not hidden
- novelty risk is classified
- manuscript states how the benchmark differs from closest prior work
- contribution claims are softened or rejected when prior work warrants it

If closest prior work invalidates the central contribution, the outcome must be `no_go_novelty` or `revise_benchmark`.

### 3. Benchmark Positioning Gate

Pass requires:

- v2.3 synthetic benchmark positioned against prior benchmarks or evaluation protocols
- low-FPR and specificity choices tied to prior evaluation practice where available
- sequential testing or change-point handling compared to relevant prior methods
- monitor-evasion and collusion threat framing grounded in attached records
- synthetic/deployment limitation preserved

The manuscript must not claim real-world deployment validity.

### 4. Baseline and Protocol Implication Gate

Pass requires:

- related-work-derived baseline implications reviewed
- missing implementable baselines either added, rejected with reasons, or marked as blockers
- statistical or sequential corrections from prior work incorporated or rejected with reasons
- protocol weaknesses from prior work preserved as limitations or revision tasks

If a missing baseline is required for the contribution claim, publication readiness is blocked.

### 5. Manuscript Revision Gate

Pass requires a revised manuscript package with:

- related-work matrix references
- closest-prior-work section
- benchmark positioning section
- revised contribution statement
- narrowed claims where needed
- updated limitations
- synthetic-only evidence statement
- citation audit output
- reviewer rerun findings
- updated go/no-go decision

Polished prose without evidence links is not remediation.

### 6. Reviewer Rerun Gate

The publication-readiness panel must rerun after manuscript revision. Reviewers must cover:

- related-work coverage
- citation and metadata validity
- novelty and closest-prior-work risk
- benchmark positioning
- baseline and protocol implications
- statistics and low-FPR claims
- synthetic-validity limits
- final area-chair go/no-go

Every issue must be classified as `resolved`, `accepted_with_narrowed_claim`, or `fatal`.

## Claim-Language Rules

Allowed when supported:

- `artifact-backed synthetic main benchmark`
- `low-FPR synthetic benchmark evidence within stated uncertainty`
- `publication candidate for the bounded synthetic benchmark scope`
- `review-ready with related-work warnings`
- `revise benchmark due to related-work or novelty blockers`

Required when applicable:

- `synthetic-only evidence; deployment validity not established`
- `related-work incomplete`
- `closest-prior-work risk unresolved`
- `novelty claim softened`
- `publication readiness blocked`
- `revise_benchmark`
- `no_go_related_work`
- `no_go_novelty`

Forbidden:

- `real-world deployment-valid`
- `exhaustive related work`
- `no prior work exists` without recorded search and careful wording
- `SOTA`
- `publication-ready` while any fatal blocker remains
- `novel benchmark` when closest prior work materially covers the claim

## Publication Outcomes

v2.4 publication remediation ends with one outcome:

- `publication_candidate`: all gates pass for a bounded synthetic benchmark manuscript.
- `review_ready_not_publication_ready`: external review may proceed, but remaining warnings prevent publication-ready language.
- `revise_benchmark`: related work or reviewer findings require benchmark, baseline, protocol, or manuscript revision.
- `no_go_related_work`: required real related-work records remain incomplete or fallback-only.
- `no_go_novelty`: closest prior work defeats the central novelty claim.
- `no_go_publication`: manuscript, citation, reviewer, or claim-traceability gates remain fatal.

Release notes must preserve this outcome exactly. A v2.4 release can pass as an honest remediation release even when the final decision is revise or no-go, but it cannot call the manuscript publication-ready unless the gates pass.
