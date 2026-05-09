# GapForge v2.3 Publication-Readiness Gate

v2.3 may upgrade the v2.2 pilot manuscript package only if the main benchmark, related-work, baseline, artifact, and reviewer gates support the claim. Publication-readiness is not a formatting state. It is a blocker-gated evidence state.

## Starting State

v2.2 produced a pilot manuscript package with readiness:

`not_publication_ready_pilot_blockers`

The preserved fatal blockers were:

- `alpha=0.001` was underpowered.
- Baselines were too weak for strong contribution claims.
- Required prior-work categories lacked real paper records.
- Related-work matrix categories were incomplete.
- Synthetic-only evidence blocked deployment-validity claims.

v2.3 must resolve these blockers with artifacts, narrow claims, or issue no-go. It must not weaken the blocker language.

## Readiness Levels

| Level | Meaning | Allowed Claim |
| --- | --- | --- |
| `blocked_manuscript` | Fatal gates are missing or failed. | Manuscript package exists with fatal blockers. |
| `main_study_manuscript_with_warnings` | Main artifacts exist but claims are narrowed by nonfatal warnings. | Inspectable main-study manuscript, not publication-ready. |
| `review_ready` | Main, related-work, baseline, citation, artifact, and reviewer gates pass for the stated scope. | Ready for external review or submission preparation. |
| `publication_ready` | Review-ready plus human acceptance of residual risks and no fatal blockers. | Publication-ready for the stated venue/profile scope. |

`publication_ready` does not mean venue acceptance.

## Required Manuscript Upgrades

The v2.3 manuscript package must include:

```bash
gapforge selected-main-manuscript --benchmark-id <benchmark-id>
gapforge selected-main-paper-package --benchmark-id <benchmark-id>
```

- title, abstract, and contribution statement with no overclaiming
- related-work matrix with real records
- closest-prior-work discussion
- benchmark design and threat model
- synthetic-data limitation statement
- main dataset card summary
- main manifest summary
- baseline suite summary
- alpha decision statement
- power and uncertainty analysis
- main result tables and figures
- hard-negative error analysis
- baseline comparison and missing-baseline blockers
- replication package summary
- claim ledger links
- citation and BibTeX audit output
- reviewer blocker table
- go/no-go recommendation

Pilot-only results may remain in background or appendix context, but they cannot be presented as main results.

## Reviewer Panel

The executable publication-readiness panel is:

```bash
gapforge selected-publication-review --benchmark-id <benchmark-id>
gapforge selected-publication-fix-list --benchmark-id <benchmark-id>
```

It writes `PublicationReadinessReview` under `selected_benchmark/reviews/main_publication_review.json` with readiness values `not_ready`, `workshop_candidate`, `conference_candidate`, or `no_go`.

The publication panel must include:

- **Statistics reviewer**: sample size, confidence intervals, sequential correction, and alpha claims.
- **Benchmark reviewer**: dataset design, threat model, family coverage, synthetic-validity limits, and leakage checks.
- **Baseline reviewer**: baseline strength, prior-work linkage, calibration, thresholds, and missing comparisons.
- **Related-work reviewer**: real records, closest-prior-work candidates, citation validity, and novelty risk.
- **Artifact reviewer**: manifest, logs, outputs, metrics, replication package, and reproducibility instructions.
- **Area-chair assessor**: final go/no-go and claim-language review.

Each reviewer must classify every issue:

- `resolved`
- `accepted_with_narrowed_claim`
- `fatal`

The area-chair assessor cannot mark publication-ready while any fatal blocker remains.

## Blocker Gates

Publication readiness is blocked when:

- `selected-baseline-strength` is missing, reports missing required baselines, or reports calibration leakage.

- `alpha=0.001` is claimed without power support
- low-FPR uncertainty or sequential correction is missing
- main dataset or main run artifacts are missing
- synthetic evidence is used to claim deployment validity
- hard negatives are missing, relabeled, or not separately reported
- required baselines are missing without accepted blockers
- prior-work categories lack real records
- related-work matrix is incomplete for the claimed scope
- closest-prior-work discussion is absent
- manuscript citations or BibTeX records are fabricated or unresolved
- result tables or figures are not linked to artifacts
- reviewer blockers are omitted, softened, or hidden
- human review does not accept residual risks for the stated scope

## Claim Language

Allowed when supported:

- `main-scale synthetic benchmark evidence`
- `specificity estimate within stated uncertainty`
- `alpha=0.01 supported for this benchmark scope`
- `alpha=0.001 supported` only if the v2.3 power gate says supported
- `publication-ready for the stated synthetic benchmark scope` only if all publication gates pass

Required when applicable:

- `alpha=0.001 dropped`
- `alpha=0.001 underpowered`
- `synthetic-only evidence; deployment validity not established`
- `baseline comparison limited`
- `related-work incomplete`
- `manuscript not publication-ready`

Forbidden unless separately proven:

- `deployment-valid`
- `real-world collusion benchmark validity`
- `exhaustive related work`
- `SOTA`
- `venue-ready`
- `publication-ready` while fatal blockers remain

## Go/No-Go Recommendation

The publication package must end with one recommendation:

- `go_publication_ready`: all publication gates pass for the stated scope.
- `go_review_ready_not_publication_ready`: external review can proceed, but publication blockers or risks remain.
- `no_go_power`: low-FPR or comparison power is inadequate.
- `no_go_related_work`: real records or matrix completion are inadequate.
- `no_go_baselines`: comparison suite is inadequate.
- `no_go_artifacts`: main-run artifacts or replication package are inadequate.
- `no_go_synthetic_validity`: intended claims require non-synthetic or externally validated data.
- `no_go_reviewer_blockers`: fatal reviewer blockers remain.

If the recommendation is any `no_go_*`, release notes must preserve that outcome.

## Publication-Readiness Output

A valid publication-readiness report must include:

- readiness level
- recommendation
- blocker table
- reviewer panel findings
- claim language approved and rejected
- manuscript package ID
- related-work matrix ID
- main execution ID
- replication package ID
- known remaining risks

If any required ID is missing, the report is incomplete and cannot claim publication readiness.

## Visible Review Surface

Publication readiness is exposed through:

```bash
gapforge dashboard --project-id <project-id> --include-selected-main
```

Inspect `publication_review.html`, `main_manuscript.html`, `go_no_go.html`, and `v23_release_gate.html` together. A single positive-looking page is insufficient: publication claims require the review, manuscript, go/no-go, and release gate to agree on the same supported scope.

Python callers should use:

```python
review = api.selected_publication_review(benchmark_id)
package = api.selected_main_manuscript(benchmark_id)
gate = api.v23_release_gate(write_report=True)
```

The API returns persisted models. It does not convert `workshop_candidate`, `revise_benchmark`, or `no_go` outcomes into publication readiness.
