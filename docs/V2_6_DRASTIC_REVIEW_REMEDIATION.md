# GapForge v2.6 Drastic Review Remediation

v2.6 treats the v2.5 drastic review as binding reviewer evidence. The goal is not to make the review nicer. The goal is to repair or honestly preserve its fatal blockers, rerun the review, and record a readiness decision that follows from the evidence.

## v2.5 Fatal Blockers

The v2.5 drastic review identified two fatal blockers:

| Blocker | Meaning | v2.6 required treatment |
| --- | --- | --- |
| `missing:related_work_matrix` | No auditable related-work matrix is available for novelty calibration. | Recover, repair, rebuild, and load-check the matrix, or keep publication readiness blocked. |
| `missing:artifact_package` | No artifact evaluation package is loadable for the manuscript. | Recover or create a reviewer-usable package from recorded state, or keep publication readiness blocked. |

Both blockers must remain visible until resolved by loadable artifacts. Rebuttal text cannot close either blocker.

## Remediation Rules

v2.6 must:

- preserve the v2.5 review panel output and likely decision `reject_likely`
- preserve the v2.5 status `fatal_blockers` until the artifacts pass loadability checks
- preserve the v2.5 note that workshop candidacy requires sharper limitations and evidence labels
- map every fatal and major objection to an artifact fix, manuscript change, narrowed claim, no-fit justification, or still-open blocker
- reject any remediation that depends on invented citations, files, results, reviewers, or unsupported benchmark labels

## Related-Work Matrix Closure Gate

The `missing:related_work_matrix` blocker may close only when:

1. A selected related-work matrix artifact loads without schema errors.
2. The matrix points to real traceable paper records, not generated citation text.
3. Every required category has a visible status.
4. Missing, impossible, or weak categories remain visible.
5. Closest-prior-work status is represented for threatening records.
6. Matrix implications are linked to benchmark, low-FPR, sequential, baseline, threat-model, dataset/protocol, novelty, and manuscript claims.
7. Citation and fake-identifier checks pass.
8. The manuscript links novelty and contribution claims to the matrix or narrows them.

If any item fails, the blocker remains fatal or is converted only to a documented `related_work_major_blocker` when the remaining issue no longer defeats novelty calibration.

## Artifact Package Closure Gate

The `missing:artifact_package` blocker may close only when:

1. A package manifest loads.
2. Required reviewer files exist or are explicitly marked not applicable with evidence.
3. Reproduction commands come from recorded manifests, scripts, or user-provided instructions.
4. Dataset access, license, redistribution, and synthetic/real labels are visible.
5. Result artifacts and expected outputs have hashes, paths, or explicit missing-state blockers.
6. Known failures and negative results remain visible.
7. The reviewer checklist maps manuscript claims, figures, and tables to artifacts or limitations.
8. The package does not include invented files or unrecorded results.

If any item fails, the blocker remains fatal or is converted only to a documented `artifact_package_major_blocker` when the package is loadable but incomplete.

## Benchmark and Manuscript Review Inputs

The rerun drastic review must receive:

- v2.5 review and revision plan
- recovered related-work matrix and check report
- recovered artifact package and check report
- public benchmark adapter attempt records
- benchmark no-fit report, if no adapter fits
- revised manuscript
- claim ledger or equivalent claim-to-evidence map
- known limitations and non-claims

Missing inputs should be treated as review evidence, not hidden setup problems.

## API and Dashboard Surfaces

Use the v2.6 API wrappers to keep the remediation path reproducible:

- `api.load_selected_related_work_matrix(benchmark_id)`
- `api.repair_selected_related_work_matrix(benchmark_id)`
- `api.load_selected_artifact_package(benchmark_id)`
- `api.repair_selected_artifact_package(benchmark_id)`
- `api.integrate_venue_artifacts(benchmark_id)`
- `api.rerun_drastic_review(manuscript_id)`
- `api.create_venue_revision_package(benchmark_id)`
- `api.v26_release_gate(write_report=True)`

Dashboard inspection pages:

- `matrix_loader.html`
- `artifact_package_loader.html`
- `venue_artifact_integration.html`
- `drastic_review_rerun.html`
- `venue_revision_package.html`
- `v26_release_gate.html`

These pages must show remaining fatal blockers rather than hiding them. A `revise_for_reviews` or `no_go` result is not a tooling failure when it accurately preserves unresolved reviewer evidence.

## Drastic Review Rerun Criteria

The rerun must evaluate:

- novelty calibration against related work
- artifact review usability
- benchmark validity and no-fit honesty
- separation of synthetic fixture evidence from real/public benchmark evidence
- claim traceability
- limitation visibility
- citation integrity
- result integrity
- venue-style source-use safety
- unresolved reviewer objections

The rerun cannot be calibrated to produce a desired decision. It must preserve harshness, role coverage, evidence labels, and fabrication blockers.

## Revision Plan Outcomes

The drastic revision plan must close with one status:

- `fatal_blockers_closed`: v2.5 fatal blockers are resolved by loadable artifacts, and no new fatal blocker appears.
- `fatal_blockers_downgraded`: loadable artifacts exist, but major limitations remain and must be visible in the manuscript.
- `fatal_blockers_open`: one or both v2.5 fatal blockers remain unresolved.
- `new_fatal_blockers`: remediation exposes additional fatal novelty, artifact, benchmark, citation, or result-integrity blockers.

Allowed readiness effects:

| Revision status | Allowed readiness decisions |
| --- | --- |
| `fatal_blockers_closed` | `conference_candidate`, `workshop_candidate`, `revise_for_reviews` |
| `fatal_blockers_downgraded` | `workshop_candidate`, `revise_for_reviews`, `benchmark_no_fit` |
| `fatal_blockers_open` | `revise_for_reviews`, `benchmark_no_fit`, `no_go` |
| `new_fatal_blockers` | `revise_for_reviews`, `no_go` |

`conference_candidate` is blocked unless both the related-work matrix and artifact package are loadable and the rerun drastic review has no fatal blockers.

## Non-Bypass Rules

v2.6 must not:

- close a blocker by editing the review language
- count a synthetic fixture as real benchmark evidence
- count no-fit as external validity
- count a package directory as loadable without manifest and file checks
- count related-work prose as a related-work matrix
- answer missing-evidence objections with confidence language
- hide the likely reject history from v2.5
- claim acceptance, camera-ready status, or external deployment validity

## Completion Output

The remediation report must include:

- original v2.5 blockers
- artifacts recovered or rebuilt
- loadability check results
- manuscript changes tied to blockers
- benchmark adapter or no-fit status
- drastic rerun summary
- final drastic revision status
- top-conference readiness decision
- unresolved risks
