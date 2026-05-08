# GapForge v0.9 v1 Readiness

v0.9 must end with a v1 readiness assessment. v1 is not a version bump for feature volume; it is a claim that GapForge can be used outside the authoring environment with honest gates, stable workflows, and documented limits.

## Readiness Outcomes

- `ready`: v1 can be prepared with the current scope and no release-blocking pilot findings.
- `ready_with_explicit_scope`: v1 can be prepared only if release notes narrow the claim and list remaining constraints.
- `not_ready`: v1 is blocked until required fixes or evidence exist.

Do not call v1 until the readiness gate passes.

## v1 Readiness Criteria

### Research Honesty

- The external pilot produced either a defensible direction or evidence-backed refusal.
- Novelty claims are conservative and linked to closest prior work.
- Missing searches, coverage gaps, failed runs, and weak evidence remain visible.
- GapForge refuses when the direction is not ready.

### End-to-End Workflow

- A real topic moved through topic framing, live literature, novelty review, protocol, execution path, artifact package, manuscript draft, reviewer/rebuttal plan, and readiness assessment.
- Every skipped phase has a recorded blocker or refusal reason.
- The golden path is documented with commands or explicit gaps.

### Empirical and Artifact Integrity

- Fixture-only results are not counted as real empirical success.
- Small real runs, if claimed, include run records, logs, result artifacts, analysis, and review.
- Artifact packages are generated from recorded state and identify incomplete pieces.
- Safe-to-commit, private, generated, cache-only, and reviewer-facing artifacts are separated.

### Manuscript and Review Integrity

- Manuscript drafts do not hide unsupported claims, missing citations, missing results, or failed work.
- Reviewer objections are preserved with severity, evidence links, and response plans.
- Rebuttal plans use evidence, changes, new work, or concessions.
- External feedback is captured and answered or recorded as accepted risk.

### Product Usability

- The pilot command path is documented and usable by someone other than the original implementer.
- Gate failures include enough diagnostic information to choose the next action.
- Docs distinguish deterministic tests, fixture smoke, live pilot, small real run, manuscript readiness, submission readiness, camera-ready, and v1 readiness.
- Known limitations are easy to find from README.

### Migration and Compatibility

- v0.8 project, manuscript, artifact evaluation, rebuttal, and submission package state remains readable or has a documented migration.
- No migration drops claim links, evidence, citations, blockers, failed-run records, or human decisions.
- Deprecated commands have replacements, warnings, or compatibility shims.
- Release process explains how to validate compatibility before tagging v1.

### Operational Safety

- Normal CI remains deterministic and offline-safe.
- Live sources, live LLM calls, large downloads, GPUs, clusters, and external reviewers remain release-validation or pilot tasks, not default CI requirements.
- Credentials, private data, raw transcripts, caches, and generated local artifacts are not committed.
- Validation gates remain fail-closed.

## v1 Blockers

v1 is blocked if any of these are true:

- no external pilot was completed
- the pilot has neither a defensible direction nor evidence-backed refusal
- novelty or empirical success is overclaimed
- fixture-only evidence is presented as real empirical validation
- migration from v0.8 state is unsafe or untested
- external feedback is absent
- CLI golden path is too unclear for another user to follow
- artifact hygiene cannot distinguish safe and unsafe outputs
- release notes would need to hide known failed runs, blockers, or limitations
- v0.9 failure requires v0.9.1 and the patch is not complete

## v1-Ready Release Statement

When ready:

`GapForge is v1-ready within the documented scope: one external pilot completed, refusal behavior validated, artifact/manuscript workflows remained traceable, migration risk was audited, and external feedback found no unresolved release blockers.`

When scoped:

`GapForge is v1-ready only within the documented scope: <scope>. The following risks remain accepted and visible: <risks>.`

When not ready:

`GapForge is not v1-ready. Blockers: <blockers>. Required next release: <v0.9.1 or later>.`

## Readiness Evidence Checklist

- v0.9 acceptance report
- pilot topic and project records
- live literature and source coverage reports
- direction decision or refusal
- human research-quality review
- experiment protocol and execution/refusal artifacts
- artifact package and hygiene audit
- manuscript draft and traceability/citation audit
- reviewer/rebuttal plan
- external feedback record and response
- migration/backward compatibility audit
- CLI/docs usability audit
- known limitations update
