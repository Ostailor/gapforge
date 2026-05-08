# GapForge v0.9 Acceptance Criteria

v0.9 acceptance is about external pilot honesty. It must prove that GapForge can run one real research topic end to end without confusing workflow fixtures, model confidence, generated prose, or incomplete experiments with research success.

## Definitions

- **External pilot**: a real GapForge project run against a real research topic, using live sources or recorded source failures, human review, and reviewer/pilot feedback outside normal fixture CI.
- **Defensible direction**: a research direction with sufficient source coverage, closest-prior-work review, novelty caution, feasible protocol, artifact plan, and human quality review to justify continued work.
- **Evidence-backed refusal**: a refusal that records searches, coverage gaps, closest-prior-work conflicts, infeasible protocol risks, unsupported claims, or missing evidence that prevent recommendation.
- **Small real run**: an executed non-fixture or benchmark-like run with run manifest, logs, result artifacts, analysis, limitations, and review. It may be underpowered but must be labeled honestly.
- **Fixture-backed canary**: a deterministic or synthetic run that validates workflow mechanics only. It may support v0.9 workflow coverage but cannot count as real empirical success.
- **v1 readiness**: a release decision that GapForge can be used by external users with documented scope, migration safety, stable commands, clear refusal behavior, artifact hygiene, and known limits.

## Required Release Criteria

1. v0.9 docs explain that this is the first real external pilot release.
2. v0.9 accepts either a defensible direction or an evidence-backed refusal.
3. v0.9 defines when failure becomes v0.9.1.
4. v1 readiness criteria are explicit.
5. One real external pilot topic is named and tracked from broad topic to final decision.
6. The pilot includes live literature campaign evidence or explicit source-failure records.
7. Closest prior work, novelty risk, missed searches, and refusal triggers are reviewed by a human.
8. The experiment protocol identifies datasets, baselines, metrics, falsification criteria, compute assumptions, and artifact expectations.
9. Any empirical claim is backed by run records and result artifacts; fixture-only results are labeled as workflow evidence only.
10. Artifact packages are generated from recorded project, workspace, benchmark, replication, and manuscript state.
11. Manuscript drafts keep unsupported claims, missing citations, missing results, and limitations visible.
12. Reviewer/rebuttal planning uses evidence, edits, additional work, or concessions; it does not invent responses.
13. Migration and backward compatibility from v0.8 state are audited.
14. CLI workflow cleanup and docs usability issues found during the pilot are recorded, fixed, or scheduled.
15. External reviewer or pilot feedback is captured and included in readiness assessment.

## Accepted Outcomes

### Pass With Defensible Direction

v0.9 may pass with a defensible direction when:

- live literature coverage is sufficient for the stated scope
- closest prior work does not invalidate the direction
- novelty is stated conservatively
- protocol, metrics, baselines, and falsification criteria are concrete
- at least fixture-backed workflow execution exists, and any small real run is artifact-backed
- manuscript and artifact packages expose remaining blockers
- reviewer feedback does not contain unresolved release blockers
- v1 readiness is `ready` or `ready_with_explicit_scope`

### Pass With Evidence-Backed Refusal

v0.9 may pass with refusal when:

- live search and prior-work review were attempted and recorded
- refusal reasons are specific and evidence-backed
- the system does not invent a research idea to preserve the happy path
- downstream manuscript, artifact, experiment, and rebuttal artifacts are marked blocked or not-applicable
- the refusal improves future search, protocol, or product decisions
- v1 readiness is assessed honestly

### Fail

v0.9 fails when:

- no real external pilot topic was run
- fixture-only results are presented as real empirical success
- novelty is claimed without closest-prior-work evidence
- a direction is forced despite weak novelty or poor coverage
- results, citations, reviewers, artifact contents, or experiments are fabricated
- external feedback is missing
- migration or compatibility risk is not assessed
- v1 readiness is asserted without gate evidence

## Required Artifacts

For the pilot project:

- topic framing record
- source policy and live source diagnostic report
- search strategy and search-round records
- canonical paper set and closest-prior-work review
- source coverage and missed-search report
- direction decision or refusal record
- human quality review record

For the experiment path:

- experiment protocol
- dataset, baseline, and metric records
- run manifest, logs, result artifacts, and analysis for any executed run
- failed, negative, underpowered, skipped, or fixture-only labels
- reproducibility or rerun notes

For artifact/manuscript/rebuttal:

- artifact package or blocker report
- manuscript draft or blocked-draft report
- citation and traceability audit
- reviewer-objection ledger
- rebuttal, revision, or refusal plan
- external reviewer/pilot feedback record

For release readiness:

- migration/backward compatibility audit
- CLI workflow cleanup notes
- docs usability pass notes
- artifact hygiene audit
- v1 readiness assessment
- failure-mode classification

## v0.9.1 Trigger

A v0.9 failure becomes v0.9.1 when the failure is narrow, fixable without changing the v0.9 scope, and blocks credible external pilot use.

Use v0.9.1 for:

- pilot command path breaks after documented setup
- release gate produces unclear or unactionable failure output
- migration audit finds a fixable v0.8 compatibility regression
- artifact hygiene misses generated/private files in a way that can be patched
- docs omit a required pilot step or confuse fixture evidence with real evidence
- external reviewer feedback reveals a blocking usability issue in the pilot workflow

Do not use v0.9.1 to lower evidence standards, rebrand a failed research direction as successful, or bypass the v1 readiness gate.

## Release Statement

Release notes must say one of:

- `v0.9 external pilot passed with defensible direction`
- `v0.9 external pilot passed with evidence-backed refusal`
- `v0.9 external pilot not completed`
- `v0.9 external pilot failed; v0.9.1 required`

The release statement must also say whether v1 readiness is `ready`, `ready_with_explicit_scope`, or `not_ready`.
