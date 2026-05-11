# GapForge v2.4 Roadmap

v2.4 is the Related Work Completion and Publication-Readiness Remediation release for the locked selected idea:

- Idea ID: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Title: `Sequential specificity benchmark for low-FPR collusion audits`
- Benchmark ID: `benchmark-sequential-specificity-benchmark-for-low-fpr-collusion-audits`

v2.3 completed the synthetic main benchmark workflow. It powered `alpha=0.001` for the synthetic count plan, generated a main dataset with 2995 negative traces, 500 positive traces, and 2139 hard-negative traces, completed the main execution, and produced metrics, predictions, baseline comparison, error analysis, and low-FPR report artifacts.

v2.3 still ended with:

- Go/no-go decision: `revise_benchmark`
- Publication readiness: `not_ready`
- Manuscript status: `not_ready`
- Fatal blocker: required related-work categories have no real attached paper records

v2.4 directly addresses that fatal publication blocker. It is not a new benchmark execution release unless related-work findings create a necessary follow-up experiment or baseline revision.

## Release Claim Boundary

Allowed v2.4 claim:

`v2.4 completes or honestly blocks the real related-work, novelty-positioning, manuscript-remediation, and publication-readiness rerun path for the v2.3 selected benchmark.`

Forbidden v2.4 claims unless separately proven:

- publication readiness while related work remains fallback-only
- novelty from absence of attached prior work
- real-world deployment validity from synthetic benchmark evidence
- exhaustive literature coverage
- hidden closest prior work
- fake citation, DOI, arXiv ID, venue, author list, or BibTeX metadata

## Workstreams

### 1. v2.3 Blocker Handoff

v2.4 starts by freezing the v2.3 blocker state:

- main benchmark complete
- synthetic-only limitation still active
- baselines implemented for v2.3 scope
- publication readiness blocked by missing real related work
- novelty status `unknown`
- manuscript package `not_ready`

The handoff must remain visible in v2.4 release notes.

### 2. Real Related-Work Search Campaigns

v2.4 must run recorded, category-specific search campaigns for the required categories:

- low-FPR detection and evaluation
- multi-agent collusion or covert coordination
- monitor evasion
- sequential testing or change-point detection
- benchmark or evaluation protocol papers
- anomaly detection specificity
- medical screening specificity analogies, if used
- cartel or covert-channel analogies, if used

A broad search is not enough. Each category needs its own queries, source list, inclusion rules, exclusions, retrieval status, and reviewer decision.

### 3. Real Paper Attachment

Every completed category must have real attached paper records with traceable metadata. Search terms, generated citation-looking text, fallback papers, and uncited prose do not count.

Each record must include stable title, author string, year, source, stable identifier or URL, retrieval date, category assignment, relevance note, novelty-risk note, and manuscript implication.

### 4. Closest-Prior-Work Dossier Refresh

v2.4 must rebuild the closest-prior-work dossier after real record attachment. The dossier must identify the strongest papers that could weaken the benchmark novelty claim and explain whether they create:

- a direct prior benchmark
- a related evaluation protocol
- an implementable baseline
- a statistical or low-FPR correction requirement
- a limitation or narrowed contribution claim
- a no-go novelty risk

If closest prior work is not found, the dossier must say `closest_prior_work_not_found_after_recorded_search`, not `none exists`.

### 5. Novelty Positioning Update

Novelty positioning must be rewritten after the dossier refresh. v2.4 may preserve, narrow, or reject the contribution claim, but it must not infer novelty from missing records.

The contribution claim should be softened when prior work already covers any part of the benchmark, protocol, threat model, metric, or baseline comparison.

### 6. Benchmark Positioning

The manuscript must position the v2.3 synthetic benchmark against prior benchmarks, evaluation protocols, low-FPR evaluation methods, and specificity or anomaly-detection practices discovered in v2.4.

If prior benchmark protocols are materially stronger than the current synthetic setup, v2.4 must preserve that as a limitation or issue `revise_benchmark` / `no_go`.

### 7. Baseline and Protocol Implication Review

Related-work records must be mapped to implementation consequences:

- no implementation implication
- baseline already covered
- missing baseline blocker
- threshold or calibration update
- sequential testing update
- dataset or protocol revision
- manuscript-only limitation

v2.4 should not rerun the synthetic benchmark just to polish results. It should rerun only when a real prior-work implication changes a required baseline, metric, thresholding rule, or protocol comparison.

### 8. Publication-Readiness Reviewer Rerun

The publication-readiness reviewer panel must be rerun after related-work completion, dossier refresh, novelty update, and manuscript revision.

The reviewer panel cannot pass publication readiness while any required category is `incomplete_blocker`, while fake-citation checks fail, or while closest-prior-work risks are unresolved.

### 9. Manuscript Revision

The manuscript package must be revised to include:

- real related-work records and matrix references
- closest-prior-work discussion
- benchmark positioning versus prior protocols
- narrowed contribution statement if needed
- preserved synthetic-only limitation
- no deployment-validity claim
- citation and BibTeX audit output
- reviewer rerun findings
- updated go/no-go recommendation

### 10. Go/No-Go Decision Update

v2.4 ends with one of:

- `go_publication_candidate`: related work, novelty, manuscript, citation, and reviewer gates pass for the bounded synthetic benchmark scope.
- `go_review_ready_not_publication_ready`: external review can proceed, but residual risks or human-review dependencies remain.
- `revise_benchmark`: prior work or reviewer findings require benchmark, baseline, metric, protocol, or manuscript revision before publication claims.
- `no_go_related_work`: required categories remain missing or fallback-only.
- `no_go_novelty`: closest prior work invalidates or materially weakens the contribution claim.
- `no_go_publication`: manuscript or reviewer gates remain fatal after remediation.

## Milestones

1. Freeze the v2.3 `revise_benchmark` handoff.
2. Create category-specific live search plans.
3. Run and record real related-work searches.
4. Attach real paper records or mark categories incomplete with reasons.
5. Complete the related-work matrix.
6. Refresh the closest-prior-work dossier.
7. Update benchmark and novelty positioning.
8. Decide whether any prior-work-derived baseline or protocol revision is required.
9. Revise the manuscript package.
10. Run citation, fake-citation, and BibTeX checks.
11. Rerun publication-readiness reviewers.
12. Issue the v2.4 go/no-go decision.

## Scriptable Workflow Surface

The intended v2.4 workflow surface is:

```bash
gapforge selected-related-work-search-plan --benchmark-id <benchmark-id>
gapforge selected-related-work-search-run --benchmark-id <benchmark-id>
gapforge selected-related-work-search-report --benchmark-id <benchmark-id>
gapforge attach-related-paper --benchmark-id <benchmark-id> --category "low-FPR detection/evaluation" --paper-id <paper-id>
gapforge related-work-curation-report --benchmark-id <benchmark-id>
gapforge read-selected-related-work --benchmark-id <benchmark-id>
gapforge selected-prior-work-refresh --benchmark-id <benchmark-id>
gapforge selected-positioning --benchmark-id <benchmark-id>
gapforge selected-related-work-matrix-v2 --benchmark-id <benchmark-id>
gapforge selected-publication-review --benchmark-id <benchmark-id> --after-related-work
gapforge selected-manuscript-related-work-revise --benchmark-id <benchmark-id>
gapforge selected-paper-package-v24 --benchmark-id <benchmark-id>
gapforge v24-release-gate --write-report --json
gapforge dashboard --project-id <selected-project-id> --include-selected-v24
```

The same workflow is scriptable through `gapforge.api`: `plan_selected_related_work_search`, `run_selected_related_work_search`, `attach_related_paper`, `read_selected_related_work`, `refresh_selected_prior_work`, `position_selected_contribution`, `build_selected_related_work_matrix_v2`, `rerun_selected_publication_review`, `revise_selected_manuscript_related_work`, and `v24_release_gate`. Prose alone cannot satisfy v2.4 acceptance without attached search, record, matrix, reviewer, manuscript, and decision artifacts.
