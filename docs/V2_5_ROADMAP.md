# GapForge v2.5 Roadmap

v2.5 is the Real Benchmark Grounding, Venue-Style Paper, and OpenReview Reviewer Training release for the locked selected benchmark:

- Idea ID: `idea-sequential-specificity-benchmark-for-low-fpr-collusion-audits`
- Title: `Sequential specificity benchmark for low-FPR collusion audits`
- Benchmark ID: `benchmark-sequential-specificity-benchmark-for-low-fpr-collusion-audits`

v2.4 produced a publication-candidate benchmark/protocol package after real related-work remediation. The selected idea now has completed related-work categories, explicit closest prior work, plausible novelty status, and careful evaluation-protocol positioning. v2.5 does not weaken those gates. It makes the package look and behave more like a serious top-conference submission by grounding the protocol in vetted benchmark artifacts where possible, shaping the manuscript to venue conventions, and calibrating reviewer simulation against OpenReview-style critique.

## Release Claim Boundary

Allowed v2.5 claim:

`v2.5 grounds the selected low-FPR collusion-audit benchmark protocol against at least one vetted benchmark adapter, produces a venue-style manuscript package, and runs an OpenReview-calibrated reviewer pass while preserving all v2.4 claim limits.`

Forbidden v2.5 claims unless separately proven:

- benchmark validity merely because a known dataset was adapted
- real-world deployment validity
- top-conference acceptance
- `SOTA`, `first`, or strong novelty language
- copied paper prose or plagiarized TeX source
- reviewer-model truth generation
- fabricated citations, results, objections, or rebuttal evidence
- hidden harsh reviewer objections

## Workstreams

### 1. v2.4 Publication-Candidate Handoff

v2.5 starts from the v2.4 `publication_candidate` status and preserves:

- synthetic-only evidence boundary
- real related-work records and closest-prior-work dossier
- plausible, not strong, novelty status
- careful benchmark/protocol contribution framing
- no deployment-validity or venue-acceptance claim
- no `SOTA`, `first`, or unsupported superiority language

### 2. Vetted Benchmark Inventory

v2.5 must identify candidate public benchmarks or datasets that can partially ground the selected protocol. Each candidate requires:

- stable source, license, access route, and retrieval date
- dataset or benchmark card
- task format and labels or outcomes
- contamination and split policy
- fit to low-FPR audit, sequential windows, hard negatives, and collusion or monitor-evasion framing
- reasons for inclusion or rejection

Known-dataset status is not enough. A benchmark is usable only after the adapter review explains what part of the selected protocol it can and cannot support.

### 3. Benchmark Adapter Implementation

At least one vetted benchmark adapter must exist for the v2.5 release gate. The adapter must map a real benchmark artifact into the selected protocol without pretending that the source benchmark was designed for collusion auditing.

Required adapter outputs:

- source benchmark metadata and license record
- deterministic conversion manifest
- trace or task mapping rules
- negative, positive, ambiguous, and excluded-item policy
- sequential-window construction, if applicable
- hard-negative or near-miss mapping, if applicable
- leakage and contamination checks
- adapter limitations
- smoke execution or no-go status

### 4. Protocol Adaptation Report

The selected benchmark protocol must be adapted to the vetted benchmark with a written report that separates:

- original synthetic scaffold assumptions
- source benchmark properties
- adapter-specific assumptions
- claims the adapter can test
- claims the adapter cannot test
- new validity risks introduced by the adapter
- comparison to v2.3/v2.4 synthetic results, if executed

The report must not claim that the selected benchmark is validated just because one adapter runs.

### 5. Venue-Style Manuscript Package

v2.5 must create a venue-style manuscript package that uses public paper TeX/source only for structure, rhetorical pattern, section pacing, figure/table placement, appendix organization, and artifact checklist alignment. It must not copy prose, equations, captions, macros that encode distinctive expression, or private/copyrighted source.

Venue style means:

- section structure and argument order
- related-work and contribution framing conventions
- limitation and threat-to-validity placement
- figure/table density and appendix shape
- abstract/introduction/results/rebuttal rhythm
- anonymous submission hygiene when relevant

Venue style does not mean copying sentences, paragraphs, captions, theorem language, reviewer responses, or unique paper phrasing.

### 6. OpenReview-Style Review Dataset

v2.5 must create a review dataset for critique calibration. It may include public OpenReview reviews only when license, availability, venue policy, and privacy constraints allow use. Dataset records must avoid private reviewer identity inference and must preserve source metadata.

The dataset should capture review shape rather than truth:

- summary
- strengths
- weaknesses
- questions
- novelty concerns
- soundness concerns
- empirical validity concerns
- clarity concerns
- reproducibility concerns
- score or confidence fields when public and allowed
- rebuttal-sensitive objections

### 7. Reviewer Model or Rubric Calibration

v2.5 must train, tune, evaluate, or configure reviewer models or rubrics to generate harsher and more realistic OpenReview-style reviews. The calibrated reviewer is a critique instrument, not an oracle.

Required reviewer boundaries:

- no fabricated citations
- no fabricated missing experiments presented as known results
- no invented paper comparisons beyond attached related work
- objections must be tagged as evidence-backed, plausible concern, or speculative
- reviewer severity must not be softened to pass the release gate
- the manuscript must preserve unresolved harsh objections

### 8. Manuscript and Rebuttal Revision

The v2.5 manuscript and rebuttal package must improve only through evidence-backed edits, narrowed claims, added limitations, adapter results, or explicit concessions. A rebuttal may propose future work, but it cannot answer a reviewer objection with unsupported confidence.

Revision outputs must include:

- manuscript diff summary
- objection-to-change matrix
- rebuttal response plan
- unresolved objection list
- claims narrowed or removed
- experiments/adapters added or explicitly blocked
- final reviewer-pass report

### 9. v2.5 Go/No-Go Decision

v2.5 ends with one of:

- `go_venue_style_review_candidate`: adapter, venue-style package, and calibrated reviewer pass exist with no fatal gate blockers.
- `review_candidate_with_major_objections`: required artifacts exist, but harsh objections remain visible and publication claims are narrowed.
- `revise_benchmark_grounding`: benchmark adapter or protocol adaptation exposes validity gaps requiring benchmark revision.
- `revise_manuscript`: venue-style or rebuttal work is incomplete or too weak for a serious submission package.
- `no_go_benchmark_grounding`: no vetted benchmark adapter can be accepted.
- `no_go_review_calibration`: reviewer dataset or calibrated pass is invalid, unsafe, fabricated, or too weak.

## Milestones

1. Freeze the v2.4 publication-candidate handoff.
2. Build vetted benchmark inventory and inclusion/exclusion notes.
3. Select at least one benchmark adapter target.
4. Implement or record the adapter no-go path.
5. Run adapter smoke execution and protocol adaptation review.
6. Create venue-style manuscript structure analysis from allowed public sources.
7. Produce the venue-style manuscript package without copied prose.
8. Build OpenReview-style review dataset with source and use-policy metadata.
9. Train, tune, or configure calibrated reviewer model or rubric.
10. Run harsh reviewer pass and classify objections.
11. Revise manuscript and rebuttal based on evidence-backed objections.
12. Run v2.5 release gate and issue go/no-go decision.

## Scriptable Workflow Surface

The intended v2.5 workflow surface is:

```bash
gapforge vetted-benchmark-register --name "<benchmark name>" --license "<license>" --terms-of-use "<terms>"
gapforge selected-vetted-benchmark-map --benchmark-id <benchmark-id>
gapforge selected-vetted-benchmark-report --benchmark-id <benchmark-id>
gapforge benchmark-adapter-create --selected-benchmark-id <benchmark-id> --vetted-benchmark-id <vetted-id>
gapforge benchmark-adapter-run --adapter-id <adapter-id>
gapforge selected-vetted-experiment-plan --benchmark-id <benchmark-id>
gapforge selected-vetted-experiment-run --plan-id <plan-id>
gapforge venue-profile-list
gapforge manuscript-set-venue-profile --manuscript-id <manuscript-id> --venue generic_ml_conference
gapforge style-corpus-add-tex --path <allowed-fixture.tex> --venue generic_ml_conference
gapforge venue-style-analyze --venue generic_ml_conference
gapforge manuscript-rewrite-for-venue --manuscript-id <manuscript-id> --venue generic_ml_conference
gapforge review-dataset-ingest-fixture
gapforge review-labels-generate --dataset-id <dataset-id>
gapforge reviewer-train --dataset-id <dataset-id> --mode heuristic
gapforge reviewer-evaluate --dataset-id <dataset-id>
gapforge drastic-review --manuscript-id <manuscript-id>
gapforge drastic-revision-plan --manuscript-id <manuscript-id>
gapforge v25-release-gate --write-report --json
gapforge dashboard --project-id <selected-project-id> --include-selected-v25
```

Equivalent API wrappers may satisfy the same workflow only when they produce the same artifact classes. Prose alone cannot satisfy v2.5 acceptance without adapter, venue-style, review-dataset, calibrated-reviewer, manuscript-revision, rebuttal, and release-gate artifacts.

## Dashboard and API Surface

The v2.5 dashboard lane is opt-in with `--include-selected-v25` and exposes:

- `vetted_benchmarks.html`, `benchmark_mappings.html`, `benchmark_adapters.html`
- `venue_profiles.html`, `style_corpus.html`, `venue_style_analysis.html`
- `openreview_dataset.html`, `review_taxonomy.html`, `reviewer_calibration.html`
- `drastic_review.html`, `drastic_revision.html`, `v25_release_gate.html`

The programmatic API mirrors the same workflow through:

- `register_vetted_benchmark`, `assess_benchmark_fit`, `create_benchmark_adapter`, `run_vetted_experiment`
- `select_venue_profile`, `ingest_style_corpus`, `analyze_venue_style`, `rewrite_manuscript_for_venue`
- `create_review_dataset`, `train_reviewer`, `evaluate_reviewer`
- `run_drastic_review`, `create_drastic_revision_plan`, `v25_release_gate`

These wrappers are scriptability surfaces only. Venue style is structure, rhetoric, and format rather than copied prose. They do not relax the no-plagiarism, no-fake-citation, no-fake-result, no-fake-review, and no-acceptance-claim rules.
