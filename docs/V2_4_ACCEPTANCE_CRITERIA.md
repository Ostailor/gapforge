# GapForge v2.4 Acceptance Criteria

v2.4 acceptance is about resolving, or honestly preserving, the v2.3 fatal publication blocker: missing real related-work records for required categories.

## Definitions

- **Real related-work record**: traceable paper metadata from a real source, not fallback, fixture, generated, or citation-looking text.
- **Required category completion**: a required category has accepted real records, matrix implications, and reviewer status.
- **Closest-prior-work dossier**: ranked real records that most threaten or shape the novelty claim.
- **Publication remediation**: manuscript, citation, novelty, benchmark-positioning, and reviewer updates made after related-work completion.
- **Publication pass**: allowed only when related work, novelty, citation, manuscript, reviewer, and claim-language gates have no fatal blockers.

## Required Documentation Criteria

1. v2.4 roadmap starts from the v2.3 `revise_benchmark` outcome.
2. v2.4 docs name missing real related work as the fatal blocker.
3. v2.4 docs preserve the v2.3 synthetic main benchmark evidence without turning it into deployment validity.
4. v2.4 related-work docs enumerate every required category.
5. v2.4 related-work docs define real paper attachment requirements.
6. v2.4 publication-remediation docs require closest-prior-work refresh.
7. v2.4 publication-remediation docs require novelty positioning and contribution claim softening when needed.
8. v2.4 acceptance criteria block publication readiness while related work remains fallback-only.
9. v2.4 docs prohibit fake citations and fake novelty claims.
10. README, known limitations, and release process mention the v2.4 remediation lane.

## Required Related-Work Criteria

The v2.4 release gate must fail publication-readiness claims unless all are true:

1. Every required category has a recorded targeted search campaign.
2. Every required category is `complete`, `complete_with_warning`, `incomplete_blocker`, or `impossible_after_recorded_search`.
3. Optional analogy categories are complete or `dropped_not_used`.
4. Categories marked complete have at least one real traceable paper record.
5. Paper records include source identifiers and retrieval metadata.
6. Fake-citation, fake-identifier, and BibTeX checks pass.
7. The related-work matrix maps records to benchmark, low-FPR, sequential, baseline, monitor-evasion, threat-model, dataset/protocol, novelty, and manuscript implications.
8. Missing categories remain visible as blockers.
9. Search failures, paywalls, unavailable records, and missed-search risks are recorded.
10. Fallback-only records do not count as coverage.

## Required Novelty and Positioning Criteria

Publication readiness may be claimed only when:

1. Closest-prior-work candidates are attached as real records.
2. The dossier ranks direct, near, component, analogy, and non-prior records.
3. The manuscript explains differences from direct and near prior work.
4. Benchmark positioning compares the v2.3 synthetic benchmark to prior benchmarks or protocols where relevant.
5. Low-FPR, specificity, and sequential-method choices are positioned against attached prior work.
6. Monitor-evasion and multi-agent collusion framing is grounded in attached records.
7. Contribution claims are softened, narrowed, or rejected when prior work weakens novelty.
8. The manuscript does not claim novelty from missing search results.

## Required Publication-Remediation Criteria

Publication readiness may be claimed only when:

1. Related-work completion passes for the stated scope.
2. Closest-prior-work and novelty blockers are resolved or accepted only with narrowed claims.
3. Related-work-derived baseline and protocol implications are handled.
4. Citation and BibTeX audits pass.
5. Manuscript claims link to related-work records, result artifacts, claim ledger entries, or explicit limitations.
6. Synthetic/deployment limitation remains visible.
7. Publication-readiness reviewers rerun after the manuscript revision.
8. Every reviewer blocker is classified as `resolved`, `accepted_with_narrowed_claim`, or `fatal`.
9. No fatal blocker remains.
10. Go/no-go decision is updated and preserved in release notes.

## Pass Outcomes

### Pass With Publication Candidate

Allowed only when:

- required categories are complete or complete with accepted warnings
- closest-prior-work and novelty blockers are resolved
- fake-citation checks pass
- manuscript revision links claims to records and artifacts
- reviewer rerun has no fatal blockers
- synthetic-only limitation remains visible

Allowed release statement:

`v2.4 publication remediation passed for the bounded synthetic benchmark scope.`

### Pass With Review-Ready But Not Publication-Ready

Allowed when:

- real related-work records exist
- warnings remain visible
- claims are narrowed
- external review can proceed
- publication-ready language remains blocked

Allowed release statement:

`v2.4 completed related-work remediation with warnings; manuscript is review-ready but not publication-ready.`

### Pass With Explicit Revise Or No-Go

Allowed when:

- targeted searches and paper-record decisions are durable
- incomplete categories, novelty conflicts, or manuscript blockers are visible
- the release explicitly declines publication readiness
- next remediation requirements are clear

Allowed release statement:

`v2.4 related-work remediation ended in revise/no-go; publication claims remain blocked.`

## Fail Conditions

v2.4 fails when:

- v2.3 related-work blocker is omitted or softened
- required categories remain unclassified
- fallback-only records are counted as real coverage
- fake citations, identifiers, venues, or BibTeX records are accepted
- closest prior work that weakens novelty is hidden
- optional analogies remain in the manuscript without records
- synthetic benchmark evidence is used to claim deployment validity
- contribution claims remain stronger than related work supports
- publication readiness is claimed with fatal reviewer blockers
- release notes avoid the updated go/no-go decision

## v2.5 Handoff Criteria

If v2.4 ends with `revise_benchmark` or any `no_go_*` outcome, the handoff must include:

- incomplete or impossible related-work categories
- missing paper records and search gaps
- closest-prior-work conflicts
- novelty claims that remain forbidden
- baseline or protocol revisions required by prior work
- manuscript sections needing revision
- reviewer fatal blockers
- exact claim language still blocked

If these are missing, v2.4 has not produced a useful remediation handoff.
