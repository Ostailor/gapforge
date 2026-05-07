# GapForge v0.8 Acceptance Criteria

v0.8 acceptance is about manuscript and submission workflow integrity. A polished draft is not enough. The release must prove that manuscript exports remain traceable to recorded claims, evidence, results, citations, and artifact state.

## Definitions

- **Manuscript-ready**: a draft package can be assembled from GapForge state, with all missing evidence, unsupported claims, unresolved citations, failed experiments, and artifact gaps visible.
- **Submission-ready**: the declared venue profile, anonymity mode, citation audit, claim traceability audit, result/artifact gates, reviewer objection review, and human approval all pass.
- **Camera-ready**: a post-acceptance cleanup state with final metadata, acknowledgments, non-anonymous references, artifact links, and publication checklist complete. It requires an explicit recorded acceptance trigger and is not inferred by GapForge.
- **Unsupported manuscript claim**: a claim in draft text that lacks a linked claim ledger record, evidence, citation, result artifact, or explicit hypothesis/limitation label.
- **Invented citation**: a reference, BibTeX key, DOI, arXiv ID, venue, title, author list, or citation relation that is not backed by known source metadata or a user-provided record.
- **Artifact evaluation package**: a reviewer-facing bundle generated from replication packages, experiment workspaces, benchmark workspaces, environment records, checksums, and expected output manifests.

## Required Release Criteria

1. Versioned docs explain manuscript-ready versus submission-ready versus camera-ready.
2. Manuscript exports are traceable to claims, evidence, results, and citations.
3. Artifact evaluation packages are generated from replication and workspace state, not handwritten claims alone.
4. Rebuttal workflow uses reviewer objections, evidence links, manuscript changes, and recorded experiments; it does not invent responses.
5. CI remains deterministic, offline, and does not require LaTeX, live sources, large downloads, GPUs, or live LLM calls.
6. Citation and BibTeX management rejects unresolved or invented citations.
7. Venue template exports are deterministic and can run without a local LaTeX installation.
8. Section-level drafts record status, blockers, traceability gaps, and human review.
9. Figures and tables are generated from recorded result artifacts, benchmark comparison state, statistical analysis, or explicit empty-state placeholders.
10. Anonymization support reports blinding risks and blocks submission-ready status when major double-blind risks remain.
11. Camera-ready checklist is separate from submission readiness and cannot be marked complete without explicit acceptance metadata.
12. No unsupported result or novelty claim can pass the submission-readiness gate.

## Required Artifacts

For a manuscript project:

- `manuscript_project.json`
- `sections.json`
- `claim_traceability.json`
- `citation_audit.json`
- `references.bib`
- `figures_tables_manifest.json`
- `manuscript_draft.md`
- `venue_profile.json`
- `anonymization_report.md` when anonymity is enabled
- `submission_readiness_report.md`

For an artifact evaluation package:

- `ARTIFACT_EVALUATION.md`
- `REPRODUCE.md`
- environment and dependency notes
- dataset/download/cache instructions
- result artifact manifest with hashes
- expected output manifest
- known nondeterminism and failed-run notes
- reviewer checklist

For rebuttal planning:

- `reviewer_objections.json`
- `rebuttal_plan.md`
- objection-to-evidence map
- manuscript-change plan
- additional-experiment or refusal plan
- unresolved objection list

For camera-ready tracking:

- `camera_ready_checklist.md`
- acceptance metadata record
- final citation and artifact-link audit
- final anonymity/deanonymization transition notes when relevant

## Acceptance Tests

The v0.8 test suite should cover:

- manuscript project creation from an experiment or benchmark workspace
- section status transitions
- claim-to-paper traceability pass/fail cases
- unsupported manuscript claim rejection
- citation import from known paper records
- unresolved BibTeX key rejection
- invented citation rejection
- venue template export without LaTeX
- figure/table manifest generation from result artifacts
- artifact evaluation package generation from replication package and workspace state
- reviewer objection ingestion and rebuttal plan generation
- rebuttal refusal when evidence is missing
- anonymization report generation and blocker handling
- submission gate pass/fail behavior
- camera-ready gate refusal without explicit acceptance metadata

## Submission-Readiness Blocking Failures

Reject submission-ready status if:

- any main manuscript claim is unlinked and unlabeled
- a novelty claim lacks closest-prior-work evidence and source-coverage context
- an empirical result claim lacks execution records, result artifacts, statistical analysis, and reproducibility status
- a benchmark claim lacks benchmark records, compute logs, parsed metrics, comparison/error analysis, and replication package status
- a citation or BibTeX key is unresolved or invented
- required baselines, metrics, or datasets are missing without a visible human waiver
- negative results, failed experiments, failed jobs, underpowered analyses, or replication gaps are hidden
- artifact evaluation package state is missing when the venue requires it
- double-blind submission still exposes authorship through metadata, repository links, paths, acknowledgments, or self-citation handling
- major reviewer objections remain unresolved without visible concessions or planned fixes
- human submission review is missing

## CI Requirements

Normal CI must remain deterministic and offline-safe:

- fixture manuscript projects only
- fixture citation records only
- fixture venue profiles only
- no live source calls
- no live LLM calls
- no large downloads
- no GPU or cluster requirement
- no LaTeX requirement
- no network-dependent artifact package checks

Offline fixture tests may prove workflow integrity. They do not prove that a real paper is publishable or accepted.

## Release Statement

Release notes must say one of:

- `v0.8 manuscript and artifact-evaluation workflow acceptance passed`
- `v0.8 manuscript and artifact-evaluation workflow acceptance not completed`

If no real manuscript project has passed the submission gate, release notes may still say workflow acceptance passed for fixture coverage, but they must also say that no venue-ready manuscript was validated.

## Implemented Acceptance Surface

The implemented v0.8 checks are exercised by deterministic tests and fixtures:

- `tests/test_manuscripts.py`
- `tests/test_manuscript_bibliography.py`
- `tests/test_manuscript_traceability.py`
- `tests/test_manuscript_assets.py`
- `tests/test_submission_checklist.py`
- `tests/test_manuscript_anonymization.py`
- `tests/test_artifact_eval.py`
- `tests/test_manuscript_reviewer_panel.py`
- `tests/test_manuscript_rebuttal_revision.py`
- `tests/test_manuscript_submission_package.py`
- `tests/test_release_gate_v08.py`
- `tests/test_dashboard.py`
- `tests/test_api.py`

Required commands:

```bash
make format-check
make lint
make typecheck
make test
make eval
gapforge eval --v8 --write-report
gapforge v8-release-gate --write-report --json
```

Acceptance remains fail-closed. A manuscript with unresolved fake citations, unsupported claims, result claims without artifacts, missing artifact packages, anonymous identity leaks, open fatal reviewer/rebuttal blockers, or hidden failed/negative experiments must not be marked submission-ready or camera-ready.
