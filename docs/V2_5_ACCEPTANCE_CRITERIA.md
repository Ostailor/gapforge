# GapForge v2.5 Acceptance Criteria

v2.5 acceptance is about adding real benchmark grounding, venue-style manuscript packaging, and OpenReview-calibrated harsh review to the v2.4 publication-candidate benchmark/protocol package.

## Definitions

- **Real benchmark grounding**: adapting an existing vetted benchmark or dataset to a bounded part of the selected protocol with source, license, mapping, leakage, and limitation artifacts.
- **Synthetic benchmark scaffolding**: generated traces and controlled scenarios used by v2.1 through v2.4 to exercise the selected benchmark protocol.
- **Venue style**: structure, rhetoric, format, section pacing, artifact checklist alignment, and review-facing organization. It is not copied prose.
- **OpenReview reviewer modeling**: critique calibration using public review patterns, rubrics, or models. It is not a truth source or acceptance predictor.
- **Reviewer-calibrated revision**: manuscript and rebuttal changes driven by classified objections, evidence links, narrowed claims, or explicit concessions.

## Required Documentation Criteria

1. v2.5 roadmap starts from the v2.4 `publication_candidate` handoff.
2. v2.5 docs distinguish real benchmark grounding from synthetic benchmark scaffolding.
3. v2.5 docs state that a known dataset does not prove benchmark validity by itself.
4. v2.5 docs define venue style as structure, rhetoric, and format rather than copied prose.
5. v2.5 docs prohibit plagiarism and disallowed TeX/source use.
6. v2.5 docs define OpenReview reviewer modeling as critique calibration, not truth generation.
7. v2.5 docs prohibit reviewer-model fabricated citations, results, datasets, baselines, and acceptance predictions.
8. README, known limitations, release process, and Codex research-agent docs mention the v2.5 lane.
9. The dashboard exposes v2.5 grounding, venue style, review calibration, drastic review, drastic revision, and release-gate pages.
10. The API exposes scriptable wrappers for each v2.5 artifact-producing step without bypassing artifact gates.

## Required Benchmark-Grounding Criteria

The v2.5 release gate must fail unless:

1. At least one candidate vetted benchmark or dataset has a source record.
2. License, access, retrieval, and attribution status are recorded.
3. Adapter fit is reviewed before claims are made.
4. At least one vetted benchmark adapter is accepted for a bounded scope.
5. Adapter mapping rules are deterministic and inspectable.
6. Ambiguous, unsupported, or incompatible source examples are excluded or labeled.
7. Leakage and contamination checks run or are blocked with visible reasons.
8. Adapter limitations are written into the manuscript package.
9. Adapter claims are separated from v2.3/v2.4 synthetic evidence.
10. No deployment-validity or benchmark-validity claim is made merely from using a known dataset.

## Required Venue-Style Manuscript Criteria

The v2.5 release gate must fail unless:

1. A venue profile exists.
2. Public paper TeX/source use is audited for license, availability, and allowed use.
3. Source analysis is limited to structure, style, rhetoric, section organization, and artifact-checklist shape.
4. No copied prose, captions, equations, distinctive macros, or reviewer-response text is present.
5. Manuscript sections link to claim IDs, related-work records, result artifacts, adapter artifacts, or limitations.
6. The synthetic-only limitation remains visible.
7. Real benchmark adapter limitations remain visible.
8. Venue acceptance is not claimed.
9. Anonymization/blinding checks run when the venue profile requires them.
10. The paper package includes appendix and artifact-review material appropriate for the venue profile.

## Required OpenReview Reviewer Criteria

The v2.5 release gate must fail unless:

1. A public-review dataset, rubric, or calibration record exists.
2. Review records have source, use-policy, retrieval, and redaction metadata.
3. Private, unavailable, or disallowed review content is excluded or represented only by safe metadata.
4. Reviewer model or rubric calibration is evaluated or manually spot-checked.
5. The selected manuscript receives at least one OpenReview-calibrated reviewer pass.
6. Reviews include novelty, soundness, empirical validity, benchmark validity, reproducibility, clarity, and missing-related-work critique.
7. Reviewer objections are tagged as `evidence_backed`, `plausible_concern`, or `speculative`.
8. Hallucinated citations, results, datasets, baselines, venues, or acceptance claims are blockers.
9. Harsh objections remain visible.
10. Reviewer simulation is labeled as simulated and not treated as acceptance prediction.

## Required Revision and Rebuttal Criteria

The v2.5 release gate must fail unless:

1. Major objections are mapped to manuscript edits, rebuttal responses, limitations, narrowed claims, new experiments, or fatal blockers.
2. Rebuttal responses cite evidence, artifact changes, or explicit concessions.
3. Unsupported rebuttal assertions are rejected.
4. Claims weakened by adapters or reviewer objections are narrowed or removed.
5. Unresolved objections remain visible in the paper package and release notes.
6. The final manuscript package includes a review-driven revision report.

## Release Gate Minimums

v2.5 cannot pass unless all minimums exist:

- at least one vetted benchmark adapter
- at least one venue-style manuscript package
- at least one OpenReview-calibrated reviewer pass
- visible dashboard artifacts or equivalent persisted reports for benchmark grounding, venue style, review calibration, drastic review, drastic revision, and the v2.5 release gate
- scriptable API or CLI access to every artifact-producing step

These are minimum artifact requirements, not proof of publication readiness, acceptance, or deployment validity.

## Pass Outcomes

### Pass With Venue-Style Review Candidate

Allowed only when:

- at least one accepted vetted benchmark adapter exists
- venue-style manuscript package passes source-use and traceability checks
- calibrated reviewer pass completes without fabrication blockers
- manuscript and rebuttal are revised or narrowed based on objections
- no fatal blocker remains

Allowed release statement:

`v2.5 passed as a venue-style review candidate with real benchmark grounding and OpenReview-calibrated critique.`

### Pass With Major Objections

Allowed when:

- minimum artifacts exist
- serious objections remain visible
- claims are narrowed accordingly
- the release does not claim submission-ready or acceptance status

Allowed release statement:

`v2.5 completed benchmark grounding and review calibration with major objections preserved.`

### Pass With Explicit Revise Or No-Go

Allowed when:

- adapter, venue-style, or reviewer-calibration work exposes blockers
- blockers are recorded with exact next steps
- publication, submission, and acceptance claims remain blocked

Allowed release statement:

`v2.5 ended in revise/no-go; grounding, venue-style, or reviewer-calibration blockers remain.`

## Fail Conditions

v2.5 fails when:

- no vetted benchmark adapter is accepted
- synthetic scaffolding is presented as real benchmark grounding
- known-dataset use is treated as validity proof
- public paper source is copied or used outside license/availability constraints
- venue acceptance or top-conference readiness is claimed
- OpenReview-style reviewer modeling fabricates facts or citations
- harsh reviewer objections are hidden or softened to pass
- rebuttal responses invent evidence
- adapter limitations are omitted from the manuscript
- v2.4 related-work, novelty, or synthetic/deployment limits are weakened

## v2.6 Handoff Criteria

If v2.5 ends with revise or no-go, the handoff must include:

- rejected and accepted benchmark adapters
- adapter validity gaps
- missing source permissions or license issues
- manuscript structure problems
- source-use or plagiarism risks
- reviewer dataset policy blockers
- reviewer hallucination or quality failures
- fatal objections and required experiments
- exact claims still blocked

If those are missing, v2.5 has not produced a useful handoff.
