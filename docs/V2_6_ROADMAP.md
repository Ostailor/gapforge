# GapForge v2.6 Roadmap

v2.6 is the Drastic Review Remediation and Real Artifact Package release for the locked selected benchmark:

- Idea ID: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Title: `Sequential specificity benchmark for low-FPR collusion audits`
- Benchmark ID: `benchmark-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Manuscript ID: `manuscript-sequential-specificity-benchmark-for-low-fpr-collusion-audits`

v2.5 completed the tooling release for vetted benchmark grounding, venue-style manuscript shaping, OpenReview-style review calibration, and drastic review. Its honest release-gate decision was `revise_for_reviews`. The drastic review status was `fatal_blockers`, with likely decision `reject_likely`.

v2.6 does not erase that outcome. It exists to repair the two fatal blockers, attempt a real external/public benchmark adapter, revise the manuscript only after repaired artifacts are loadable, and rerun the drastic review under the same harsh standards.

## Inspectable and Scriptable Workflow

v2.6 exposes every remediation stage through CLI, API, and dashboard pages. This is inspection support, not readiness proof by itself.

Dashboard pages:

- `matrix_loader.html`
- `artifact_package_loader.html`
- `real_benchmark_search.html`
- `real_benchmark_adapter.html`
- `real_benchmark_experiment.html`
- `venue_artifact_integration.html`
- `drastic_review_rerun.html`
- `venue_revision_package.html`
- `v26_release_gate.html`

Scriptable API path:

```python
from gapforge import api

matrix = api.load_selected_related_work_matrix(benchmark_id)
artifact = api.load_selected_artifact_package(benchmark_id)
search = api.search_real_benchmark_candidates(benchmark_id)
integration = api.integrate_venue_artifacts(benchmark_id)
rerun = api.rerun_drastic_review(manuscript_id)
package = api.create_venue_revision_package(benchmark_id)
gate = api.v26_release_gate(write_report=True)
```

If a real benchmark candidate exists, assess it before creating or running an adapter:

```python
assessment = api.assess_real_benchmark_adapter(benchmark_id, candidate_id)
attempts = api.run_real_benchmark_experiment(benchmark_id)
```

The gate remains allowed to return `no_go`, `benchmark_no_fit`, or `revise_for_reviews`; those are valid honest outcomes when evidence does not support stronger readiness.

## Release Claim Boundary

Allowed v2.6 claim:

`v2.6 remediates v2.5 drastic-review blockers by requiring a loadable related-work matrix, a loadable artifact evaluation package, a real external/public benchmark adapter attempt or benchmark no-fit report, a venue-style manuscript revision, and a rerun drastic review with an honest readiness decision.`

Forbidden v2.6 claims unless separately proven:

- top-conference acceptance
- camera-ready readiness
- hidden or downgraded fatal reviewer blockers
- synthetic fixture benchmark validity as real collusion benchmark grounding
- real collusion benchmark validity without source-label and mapping support
- invented artifact package files
- invented citations, results, reviews, reviewer identities, datasets, or baselines
- copied paper prose from venue-style sources
- weakened drastic reviewer standards

## Starting State From v2.5

v2.6 starts from the v2.5 release record:

- v2.5 release gate completed
- v2.5 status: `revise_for_reviews`
- drastic review status: `fatal_blockers`
- likely decision: `reject_likely`
- workshop candidate: true only after limitations and evidence labels are sharpened
- real benchmark grounding used a synthetic local fixture, useful for adapter plumbing but not real collusion data or deployment validity

Fatal blockers:

1. `missing:related_work_matrix`: no auditable related-work matrix is available for novelty calibration.
2. `missing:artifact_package`: no artifact evaluation package is loadable for the manuscript.

## Workstreams

### 1. v2.5 Blocker Handoff

v2.6 must preserve the v2.5 drastic review as evidence. The handoff must include:

- drastic review panel artifact
- drastic revision plan artifact
- fatal blocker list
- required revision list
- likely decision and score summary
- workshop-candidate caveat
- all v2.5 non-claims about synthetic fixture benchmark grounding

If the v2.5 blocker record cannot be loaded, v2.6 must reconstruct it from release notes and mark the provenance as `recovered_from_release_record`.

### 2. Related-Work Matrix Recovery, Repair, and Loading

v2.6 must make the selected related-work matrix loadable and auditable. It may recover an existing v2.4 matrix, repair stale paths or schema drift, or rebuild the matrix from recorded paper records and search campaigns.

The matrix must satisfy the v2.4 related-work rules:

- real traceable paper records only
- no fallback-only or generated citations counted as coverage
- category-level status visible
- closest-prior-work status visible
- benchmark, low-FPR, sequential, baseline, threat-model, dataset/protocol, novelty, and manuscript implications visible
- missing categories preserved as blockers

Publication readiness cannot pass while the matrix is missing, unloadable, stale, schema-invalid, fallback-only, or disconnected from manuscript claims.

### 3. Artifact Evaluation Package Recovery, Creation, and Loading

v2.6 must produce or recover a loadable artifact evaluation package for the manuscript. The package must be generated from recorded workspace, benchmark, replication, manuscript, environment, and result state.

The package must not invent files. Missing inputs must be represented as blockers, access instructions, or limitations, not as fabricated manifests.

Required package surface:

- `ARTIFACT_EVALUATION.md`
- `REPRODUCE.md`
- `MANIFEST.json`
- `ENVIRONMENT.md`
- `DATA.md`
- `EXPECTED_OUTPUTS.json`
- `RESULT_ARTIFACTS.json`
- `KNOWN_FAILURES.md`
- `REVIEWER_CHECKLIST.md`

If a file is not applicable, the manifest must state why. If a file is required but absent, the package status remains blocked.

### 4. Real External/Public Benchmark Adapter Attempt

v2.6 must attempt to identify and adapt at least one external/public benchmark or dataset that could partially ground the selected protocol. The attempt must record:

- source name, version, and stable identifier
- source URL or access route
- license, terms, attribution, and retrieval date
- task format, labels, splits, and contamination risks
- fit to low-FPR, sequential windows, hard negatives, collusion/covert coordination, and monitor evasion
- inclusion, exclusion, or no-fit decision

An accepted adapter may support only the bounded claims justified by the source. If no real benchmark fits, v2.6 may pass as `benchmark_no_fit` only when the no-fit report is explicit, sourced, and tied to narrowed manuscript claims.

### 5. Benchmark No-Fit Justification

If no external/public benchmark supports the selected protocol, v2.6 must produce a no-fit report. The report must explain:

- which public sources were considered
- why each source fails or only supports an auxiliary slice
- which claims must be removed, narrowed, or labeled synthetic-only
- why the synthetic v2.5 fixture remains adapter plumbing rather than real benchmark grounding
- what future evidence would be needed to claim real collusion benchmark validity

No-fit is an honest release outcome. It is not a publication-readiness pass by itself.

### 6. Venue-Style Manuscript Revision After Artifact Repair

The manuscript may be revised only after the related-work matrix and artifact package are loadable, or after their blockers are explicitly preserved. The revision must:

- link claims to the loadable related-work matrix, artifact package, result artifacts, benchmark adapter attempt, or no-fit report
- sharpen limitations and evidence labels
- separate synthetic fixture evidence from real/public benchmark evidence
- preserve drastic reviewer objections that remain unresolved
- avoid copied prose from venue-style sources

### 7. Drastic Review Rerun

v2.6 must rerun the drastic review after remediation. The rerun must use the same or stricter standards as v2.5 and must not be tuned to pass.

The rerun must inspect:

- related-work matrix loadability and novelty calibration
- artifact package loadability and review usability
- benchmark adapter or no-fit report honesty
- manuscript claim traceability
- citation and result integrity
- limitation visibility
- unresolved fatal, major, and minor objections

### 8. Drastic Revision Plan Closure or Downgrade

The drastic revision plan must end with one of:

- `fatal_blockers_closed`: all v2.5 fatal blockers are loadably resolved.
- `fatal_blockers_downgraded`: blockers are no longer fatal but remain major limitations.
- `fatal_blockers_open`: one or more fatal blockers remain.
- `new_fatal_blockers`: remediation exposed new fatal blockers.

Downgrading a blocker requires evidence. It cannot be done by softer wording.

### 9. Top-Conference Readiness Decision

v2.6 must end with a top-conference readiness decision. Allowed decisions:

- `conference_candidate`: related-work matrix and artifact package are loadable, drastic review has no fatal blockers, benchmark/no-fit claims are honest, and manuscript traceability passes.
- `workshop_candidate`: artifacts are loadable and fatal blockers are closed or downgraded, but substantial limitations remain.
- `revise_for_reviews`: meaningful remediation occurred, but reviewer or manuscript blockers remain.
- `benchmark_no_fit`: no public benchmark fits; no-fit report is complete and claims are narrowed.
- `no_go`: core artifacts are missing, unloadable, fabricated, unsafe, or novelty/validity is defeated.

No decision may claim acceptance or camera-ready status.

## Milestones

1. Load the v2.5 release-gate, drastic review, and drastic revision records.
2. Recover or rebuild the selected related-work matrix.
3. Validate related-work matrix schema, source records, and manuscript claim links.
4. Recover or create the artifact evaluation package from recorded state.
5. Validate artifact package manifest, files, hashes, commands, and reviewer checklist.
6. Inventory candidate external/public benchmarks.
7. Attempt at least one real/public benchmark adapter or produce a no-fit report.
8. Update manuscript evidence labels and limitations.
9. Run venue-style manuscript revision after repaired artifacts are loadable.
10. Rerun drastic review.
11. Close, downgrade, or preserve the drastic revision plan.
12. Run v2.6 release gate and record the readiness decision.

## Scriptable Workflow Surface

The intended v2.6 workflow surface is:

```bash
gapforge v25-release-gate --write-report --json
gapforge selected-related-work-matrix-load --benchmark-id <benchmark-id>
gapforge selected-related-work-matrix-repair --benchmark-id <benchmark-id>
gapforge selected-artifact-package-load --benchmark-id <benchmark-id>
gapforge selected-artifact-package-repair --benchmark-id <benchmark-id>
gapforge selected-real-benchmark-search --benchmark-id <benchmark-id>
gapforge selected-real-benchmark-adapter-assess --benchmark-id <benchmark-id> --candidate-id <candidate-id>
gapforge selected-real-benchmark-experiment-plan --benchmark-id <benchmark-id>
gapforge selected-real-benchmark-experiment-run --benchmark-id <benchmark-id>
gapforge selected-venue-artifact-integrate --benchmark-id <benchmark-id>
gapforge drastic-review-rerun --manuscript-id <manuscript-id>
gapforge drastic-revision-close --manuscript-id <manuscript-id> --item-id <item-id>
gapforge selected-venue-revision-package --benchmark-id <benchmark-id>
gapforge v26-release-gate --write-report --json
gapforge dashboard --project-id <selected-project-id> --include-selected-v26
```

Equivalent API wrappers may satisfy the same workflow only when they produce the same recoverable artifacts, checks, reports, rerun review, and release-gate decision. Prose alone cannot satisfy v2.6 acceptance.

## Dashboard and API Surface

The v2.6 dashboard lane is opt-in with `--include-selected-v26` and exposes:

- `matrix_loader.html`
- `artifact_package_loader.html`
- `real_benchmark_search.html`
- `real_benchmark_adapter.html`
- `real_benchmark_experiment.html`
- `venue_artifact_integration.html`
- `drastic_review_rerun.html`
- `venue_revision_package.html`
- `v26_release_gate.html`

The programmatic API mirrors the same workflow through:

- `load_selected_related_work_matrix`
- `repair_selected_related_work_matrix`
- `load_selected_artifact_package`
- `repair_selected_artifact_package`
- `search_real_benchmark_candidates`
- `assess_real_benchmark_adapter`
- `run_real_benchmark_experiment`
- `integrate_venue_artifacts`
- `rerun_drastic_review`
- `create_venue_revision_package`
- `v26_release_gate`

Dashboard and API visibility do not strengthen claims. They make recovery, loadability, no-fit decisions, limitations, and remaining blockers auditable.
