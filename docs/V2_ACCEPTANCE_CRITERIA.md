# GapForge v2 Acceptance Criteria

v2 acceptance is about idea discovery honesty. v2 must prove that GapForge can search beyond the first obvious idea while keeping v1 evidence gates intact.

## Definitions

- **Topic portfolio**: a bounded collection of related topics, subtopics, constraints, source profiles, exclusions, and human preferences used for active idea search.
- **Idea candidate**: a structured, provisional research idea generated from a topic, gap, mutation, transfer, or human seed. It is not a research direction until accepted.
- **Accepted idea candidate**: a candidate that has passed source coverage checks, closest-prior-work review, novelty and counterevidence review, feasibility review, human review, and release-gate validation for the stated scope.
- **Rejected idea candidate**: a candidate that fails novelty, evidence, feasibility, specificity, human-review, or scope checks and remains visible with a reason.
- **Research agenda fallback**: an honest output produced when no candidate is accepted. It records rejected candidates, missing evidence, next searches, possible pivots, and why no idea should be forced.
- **Idea yield**: the measured relationship between search effort and defensible outputs, including candidates generated, candidates rejected, accepted candidates, cost, stop reasons, and fallback status.

## Required Release Criteria

1. v2 docs clearly explain how v2 differs from v1.
2. v2 defines what counts as an accepted idea.
3. v2 defines what happens if no idea is found.
4. v2 release process says failure to find an accepted idea triggers v2.0.1 or v2.1 planning, not fake success.
5. At least one topic portfolio is created and run through active idea search.
6. The run creates multiple idea candidates, not only the first obvious direction.
7. Candidate mutation is recorded with parent-child provenance.
8. Constructive gap creation is attempted and recorded.
9. Cross-domain transfer expansion is attempted and recorded.
10. Codex/GPT-5.4 idea synthesis tasks are validated before import and do not bypass evidence gates.
11. The active idea search controller records decisions, stop reasons, and next actions.
12. Novelty and counterevidence loops run before candidate acceptance.
13. An idea tournament compares candidates under shared criteria.
14. Human preference feedback is captured and used only as steering or review evidence.
15. Idea yield metrics are generated and included in release evidence.
16. The v2 release gate returns either accepted candidate evidence or explicit idea-discovery failure.

## Accepted Idea Candidate Standard

An accepted idea candidate must have:

- a precise problem statement and scope
- documented origin from portfolio search, mutation, constructive gap creation, transfer, or human seed
- source coverage adequate for the stated scope, or visible scope limits accepted by human review
- closest-prior-work review with novelty risk stated conservatively
- counterevidence search and unresolved-risk list
- concrete experiment or evaluation path with datasets, baselines, metrics, falsification criteria, and artifact expectations
- feasibility assessment for data, compute, implementation, and review burden
- tournament record showing why it beat or survived alternatives
- human review record accepting the candidate as worth continued research
- explicit statement of what claims are supported, unknown, hypothetical, or blocked

Acceptance does not mean manuscript-ready, submission-ready, publication-ready, or empirically proven.

## Pass Outcomes

### Pass With Accepted Idea Candidate

v2 may pass when at least one candidate meets the accepted-candidate standard and the release gate records:

- portfolio evidence
- candidate lineage
- novelty and counterevidence evidence
- tournament result
- human review
- idea yield metrics
- remaining risks

### Explicit Idea-Discovery Failure

If no candidate is accepted, v2 may not claim the Idea Discovery Engine succeeded. The release gate must record explicit failure and route follow-up to v2.0.1 or v2.1 planning.

The failure report must include:

- candidates attempted
- why each serious candidate was rejected
- missed searches or source limits
- human feedback
- yield metrics
- research agenda fallback
- whether the failure is a narrow implementation issue for v2.0.1 or a broader product/research design issue for v2.1

## Fail Conditions

v2 fails when:

- it evaluates only one obvious idea and calls that discovery
- a generic idea is forced through despite weak novelty or poor evidence
- speculative seeds are described as paper-ready
- citations, papers, datasets, baselines, metrics, or results are invented
- Codex/GPT-5.4 output mutates state without validation
- human review is missing or bypassed
- tournament ranking is treated as acceptance without evidence review
- no accepted candidate exists and release notes still claim idea-discovery success
- research agenda fallback is omitted when no candidate is accepted
- idea yield metrics are missing

## Required Artifacts

For each v2 release candidate:

- topic portfolio record
- active idea search controller log
- candidate registry
- mutation lineage
- constructive gap records
- cross-domain transfer records
- Codex/GPT-5.4 task-pack outputs and validation records, if used
- novelty and counterevidence records
- idea tournament report
- human feedback and review records
- accepted candidate dossier or rejection dossiers
- research agenda fallback, if no candidate is accepted
- idea yield metrics report
- v2 release-gate report

## Release Statement

Release notes must say one of:

- `v2 idea discovery passed with accepted candidate`
- `v2 idea discovery failed; v2.0.1 required`
- `v2 idea discovery failed; v2.1 planning required`

Do not use `passed` when the strongest output is only a fallback agenda.
