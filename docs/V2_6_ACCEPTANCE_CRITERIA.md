# GapForge v2.6 Acceptance Criteria

v2.6 acceptance is about remediating the v2.5 drastic-review fatal blockers, producing a real loadable artifact package, attempting real external/public benchmark grounding, revising the manuscript honestly, and rerunning drastic review.

## Acceptance Summary

v2.6 is accepted only when:

1. It directly addresses the v2.5 fatal blockers `missing:related_work_matrix` and `missing:artifact_package`.
2. The release gate returns one of `workshop_candidate`, `conference_candidate`, `revise_for_reviews`, `benchmark_no_fit`, or `no_go`.
3. Publication readiness cannot pass unless the related-work matrix and artifact package are loadable.
4. The v2.5 drastic review outcome is preserved honestly until a rerun review changes it with evidence.
5. No fake citations, no fake results, and no copied venue-style prose may be used to improve readiness.

## Definitions

- **Loadable related-work matrix**: a selected related-work matrix artifact that parses, references real traceable paper records, exposes required categories and implications, and can calibrate novelty claims.
- **Loadable artifact package**: an artifact evaluation package with a parseable manifest, required reviewer files, recorded provenance, visible data/license limits, and no invented contents.
- **Real external/public benchmark attempt**: a recorded inventory and adapter attempt against a non-fixture source with source, access, license, label, split, and fit metadata.
- **Benchmark no-fit**: an accepted release outcome when public candidates are reviewed and none fit without overclaiming.
- **Drastic rerun**: a post-remediation harsh review pass using the same or stricter standards as v2.5.
- **Conference candidate**: an evidence-gated readiness state, not acceptance, likely acceptance, or camera-ready status.

## Required Documentation Criteria

1. v2.6 roadmap starts from the v2.5 `revise_for_reviews` and `fatal_blockers` outcome.
2. v2.6 docs name `missing:related_work_matrix` and `missing:artifact_package` as fatal blockers.
3. v2.6 docs require related-work matrix recovery, repair, and load checks.
4. v2.6 docs require artifact package recovery, creation, and load checks.
5. v2.6 docs require at least one real external/public benchmark adapter attempt or a no-fit report.
6. v2.6 docs prohibit treating the v2.5 synthetic fixture as real benchmark grounding.
7. v2.6 docs require venue-style manuscript revision after repaired artifacts or preserved blockers.
8. v2.6 docs require a drastic review rerun.
9. v2.6 docs define drastic revision closure, downgrade, open, and new-fatal outcomes.
10. README, known limitations, and release process mention the v2.6 lane.
11. Dashboard pages expose matrix loading, artifact package loading, real benchmark search/adapters/experiments, manuscript integration, drastic rerun, revision package, and v2.6 release-gate status.
12. API wrappers make the v2.6 workflow scriptable without shell-only orchestration.
13. Skills guide agents through matrix recovery, artifact package repair, real benchmark search, drastic rerun, and venue revision packaging.

## Required Related-Work Matrix Criteria

The v2.6 release gate must block publication readiness unless:

1. The selected related-work matrix path is known.
2. The matrix artifact loads without schema errors.
3. Referenced paper records are real and traceable.
4. Fallback-only, fixture-only, or generated citations do not count as coverage.
5. Required categories have visible statuses.
6. Missing or impossible categories remain visible.
7. Closest-prior-work status is represented.
8. Matrix implications cover benchmark, low-FPR, sequential, baseline, threat-model, dataset/protocol, novelty, and manuscript claims.
9. Citation and fake-identifier checks pass.
10. Manuscript novelty and contribution claims link to the matrix or are narrowed.

## Required Artifact Package Criteria

The v2.6 release gate must block publication readiness unless:

1. The artifact package root is known.
2. `MANIFEST.json` parses.
3. Required package files exist or are marked not applicable with evidence.
4. Result artifacts and expected outputs resolve or are marked missing with blockers.
5. Reproduction commands have recorded provenance.
6. Data access, license, redistribution, and synthetic/real labels are visible.
7. Public benchmark adapter or no-fit status is linked.
8. Known failures and negative results remain visible.
9. Reviewer checklist maps claims, figures, and tables to artifacts or limitations.
10. No invented package file, result, command, dataset, or badge claim is present.

## Required Benchmark Upgrade Criteria

The v2.6 release gate must require one of:

1. At least one accepted real external/public benchmark adapter with bounded claims, or
2. A complete benchmark no-fit report with narrowed manuscript claims.

Every candidate must record:

- source identity and access route
- license, terms, attribution, and retrieval date
- task format, labels, splits, and contamination risks
- fit to low-FPR, sequential, hard-negative, collusion/covert coordination, and monitor-evasion dimensions
- accepted, rejected, blocked, auxiliary, or no-fit status

The gate must fail if synthetic fixture results are described as real collusion benchmark grounding.

## Required Manuscript Revision Criteria

The v2.6 manuscript revision must:

1. Link claims to the related-work matrix, artifact package, benchmark adapter/no-fit report, result artifacts, or explicit limitations.
2. Separate synthetic fixture evidence from public benchmark evidence.
3. Preserve real benchmark no-fit or adapter limitations.
4. Preserve unresolved drastic-review objections.
5. Sharpen evidence labels and limitation text.
6. Remove, narrow, or label claims unsupported by related work, artifacts, or benchmark mapping.
7. Avoid copied prose, captions, equations, distinctive macros, or reviewer-response text.
8. Avoid top-conference acceptance or camera-ready language.

## Required Drastic Review Criteria

The v2.6 release gate must require:

1. v2.5 drastic review loaded or recovered from release record.
2. v2.5 drastic revision plan loaded or recovered from release record.
3. Rerun drastic review after artifact repair and manuscript revision.
4. Rerun review covers novelty, artifact package, benchmark validity, empirical validity, reproducibility, clarity, claim traceability, and limitations.
5. Rerun review tags objections as evidence-backed, plausible, or speculative.
6. Fabricated citations, results, datasets, baselines, reviewers, or acceptance claims are fatal.
7. Harsh objections remain visible.
8. Drastic revision plan closes, downgrades, preserves, or adds fatal blockers with evidence.

## Release Gate Outcomes

v2.6 release gate may return:

### `conference_candidate`

Allowed only when:

- related-work matrix is loadable
- artifact package is loadable
- accepted adapter or no-fit report supports narrowed claims
- manuscript traceability passes
- rerun drastic review has no fatal blockers
- no acceptance, likely-acceptance, or camera-ready claim is made

Allowed release statement:

`v2.6 passed as a conference candidate for the bounded manuscript scope; this is not acceptance or camera-ready readiness.`

### `workshop_candidate`

Allowed when:

- related-work matrix and artifact package are loadable
- fatal blockers are closed or downgraded
- substantial limitations remain visible
- claims are narrowed enough for workshop-style review

Allowed release statement:

`v2.6 passed as a workshop candidate with limitations and evidence labels preserved.`

### `revise_for_reviews`

Allowed when:

- v2.6 made durable remediation progress
- one or more major reviewer, manuscript, artifact, or benchmark blockers remain
- publication-readiness and acceptance language remain blocked

Allowed release statement:

`v2.6 ended in revise_for_reviews; remediation artifacts exist, but review blockers remain.`

### `benchmark_no_fit`

Allowed when:

- no external/public benchmark fits the selected protocol after recorded inventory and review
- no-fit report is complete
- manuscript claims are narrowed or labeled synthetic-only
- related-work matrix and artifact package readiness are reported honestly

Allowed release statement:

`v2.6 ended in benchmark_no_fit; no public benchmark was accepted for real collusion grounding, and claims were narrowed accordingly.`

### `no_go`

Required when:

- related-work matrix is missing or invalid
- artifact package is missing, invalid, or fabricated
- benchmark/no-fit evidence is missing or overclaimed
- manuscript hides fatal blockers
- drastic rerun exposes fatal unresolved novelty, artifact, benchmark, citation, or result-integrity problems

Allowed release statement:

`v2.6 ended in no_go; publication and readiness claims remain blocked.`

## Publication Readiness Blockers

Publication readiness cannot pass unless:

- related-work matrix is loadable
- artifact package is loadable
- drastic rerun has no fatal blockers
- benchmark adapter/no-fit claims are honest
- manuscript claim traceability passes

If either the related-work matrix or artifact package is not loadable, the strongest allowed outcomes are `revise_for_reviews`, `benchmark_no_fit`, or `no_go`.

## Fail Conditions

v2.6 fails when:

- v2.5 fatal blockers are omitted or softened without evidence
- related-work prose is substituted for a loadable matrix
- package directories are counted without a loadable manifest and required files
- artifact package files, commands, results, datasets, or hashes are invented
- synthetic fixture benchmark is treated as real benchmark grounding
- no-fit is used to imply external validity
- manuscript claims real collusion benchmark validity without source mapping support
- venue-style sources are copied
- fake citations, results, reviews, datasets, baselines, or reviewer claims pass
- drastic review standards are weakened to pass
- top-conference acceptance or camera-ready readiness is claimed

## v2.7 Handoff Criteria

If v2.6 ends in `revise_for_reviews`, `benchmark_no_fit`, or `no_go`, the handoff must include:

- related-work matrix status and remaining category risks
- artifact package status and missing reviewer materials
- benchmark candidates accepted, rejected, blocked, or no-fit
- manuscript claims still blocked
- drastic rerun objections
- drastic revision plan status
- top-conference readiness decision
- exact evidence needed for any stronger future claim

If these are missing, v2.6 has not produced a useful remediation handoff.
