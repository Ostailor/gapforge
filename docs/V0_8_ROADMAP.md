# GapForge v0.8 Roadmap

v0.8 is the manuscript, artifact evaluation, and reviewer-rebuttal release.

v0.7 made benchmark execution and replication state explicit. v0.8 should turn the existing research, claim, citation, experiment, benchmark, and replication artifacts into an auditable paper workflow. It must not turn incomplete research into a polished submission by hiding missing evidence, weak novelty, failed experiments, missing citations, or incomplete replication.

GapForge must still not fabricate results, citations, novelty claims, venue status, or reviewer responses.

## Goals

1. Add a manuscript project model that records venue target, anonymity mode, sections, drafts, claims, evidence, citations, figures, tables, artifact package status, rebuttal state, and camera-ready tasks.
2. Add claim-to-paper traceability so every manuscript claim links to claim ledger entries, evidence spans, result artifacts, benchmark records, reviewer decisions, and citations.
3. Add citation and BibTeX management that imports only known bibliographic records, reports missing citations, detects unresolved keys, and refuses invented BibTeX.
4. Add venue template support without requiring LaTeX installation in normal CI.
5. Add section-level drafting and review with status, blockers, allowed claims, missing evidence, and human approval.
6. Generate figures and tables from result artifacts, benchmark comparison tables, statistical analysis, and error/slice analysis rather than prose descriptions.
7. Generate artifact evaluation packages from replication packages, experiment workspaces, benchmark workspaces, environment records, checksums, and reviewer checklists.
8. Add reviewer simulation and rebuttal planning that uses recorded objections and evidence, not invented answers.
9. Add anonymization and blinding support for double-blind submissions, including self-citation handling, artifact redaction, and deanonymization risk reports.
10. Add a camera-ready checklist for post-acceptance cleanup without claiming venue acceptance.
11. Add a submission-readiness gate that fails closed when novelty, result, reproducibility, artifact, citation, or blinding gates fail.
12. Add explicit report language for unsupported result claims, unsupported novelty claims, missing citations, failed experiments, and incomplete artifact evaluation.

## Manuscript Readiness Levels

### Manuscript-Ready

Manuscript-ready means GapForge can assemble a coherent draft package from recorded state. It may still contain known blockers, missing evidence, placeholder sections, unsupported claims, unresolved citations, or artifact-evaluation gaps.

### Submission-Ready

Submission-ready means the manuscript package passes the v0.8 submission gate for its declared venue and anonymity mode. All paper claims are traceable, citations resolve to known records, required results and figures come from artifacts, artifact evaluation package state is complete or intentionally out of scope, and human review accepts the remaining risk.

Submission-ready is not venue acceptance.

### Camera-Ready

Camera-ready means a post-acceptance checklist has been completed against accepted-paper requirements. GapForge may track this status only after the user records acceptance or another explicit external trigger. It must not infer acceptance from reviewer sentiment, rebuttal quality, or a high readiness score.

## Must-Have Workstreams

### Manuscript Project Model

- `ManuscriptProject`
- venue target and template profile
- anonymity mode
- section records
- draft snapshots
- claim links
- citation links
- figure/table manifests
- artifact package links
- reviewer and rebuttal state
- readiness gate reports
- human approvals and waivers

### Claim-to-Paper Traceability

- each manuscript paragraph or claim block links to claim IDs
- empirical claims link to result artifacts, execution records, analysis, and reproduction status
- benchmark claims link to benchmark cards, compute logs, comparisons, and error analysis
- novelty claims link to closest prior work, related-work matrix rows, and source coverage
- unsupported claims are either removed or labeled as hypotheses, limitations, or future work

### Citation and BibTeX Management

- import citations from known paper records and source metadata
- validate BibTeX keys against known paper IDs
- report missing fields, duplicate keys, unresolved citations, and suspected hallucinations
- maintain `references.bib` and citation audit artifacts
- block submission-ready status when required citations are unresolved

### Venue Templates

- template profiles for section expectations, anonymity rules, page-limit metadata, artifact requirements, and checklist fields
- template export that can write Markdown and optional LaTeX-ready files
- no LaTeX installation requirement in CI
- deterministic fixture templates for tests

### Section-Level Drafting

- section status: missing, outline, draft, reviewed, blocked, accepted
- allowed claim types per section
- required citations and evidence per section
- section-level reviewer comments and blocking issues
- draft snapshots with provenance and diff summaries

### Figure and Table Generation

- tables generated from result databases, benchmark comparison tables, statistical summaries, and ablation manifests
- figures generated from recorded result artifacts or explicit plotting specs
- every figure/table includes source artifact IDs and hashes where available
- generated captions state limitations and data level
- failed, negative, and underpowered results remain visible

### Artifact Evaluation Package

- package generated from replication package and workspace state
- `ARTIFACT_EVALUATION.md`
- `REPRODUCE.md`
- environment and dependency notes
- dataset/download/cache instructions
- expected output manifest
- checksums or version identifiers
- known failures and nondeterminism
- reviewer checklist

### Reviewer and Rebuttal Workflow

- deterministic reviewer simulations using manuscript, claims, evidence, prior work, and artifact state
- objection ledger with severity, section links, evidence links, and blocking status
- rebuttal plan that maps each objection to evidence, changes, experiments, or honest concessions
- no invented rebuttal citations, results, or promises

### Anonymization and Blinding

- double-blind profile with author metadata removal
- self-citation and artifact URL review
- path, package, and repository-name redaction warnings
- deanonymization risk report
- reversible internal mapping that is excluded from submission bundles by default

### Submission and Camera-Ready Gates

- submission gate fails on unresolved unsupported claims, fake citations, missing artifact links, failed reproducibility gates, hidden negative results, unresolved blinding blockers, or unreviewed major objections
- camera-ready checklist is separate and only applies after recorded acceptance
- release notes distinguish manuscript-ready, submission-ready, and camera-ready

## Non-Goals

- Do not fabricate results.
- Do not fabricate citations, BibTeX, DOIs, arXiv IDs, venues, or related-work entries.
- Do not mark a manuscript submission-ready if novelty, result, reproducibility, artifact, citation, blinding, or human-review gates fail.
- Do not claim venue acceptance.
- Do not require LaTeX installation in CI.
- Do not hide negative results, failed experiments, missing baselines, failed replication attempts, or incomplete artifact packages.
- Do not weaken v5 literature gates, v6 empirical gates, or v7 benchmark/replication gates.

## Milestones

1. Manuscript project model and section state.
2. Claim-to-paper traceability and submission-claim audit.
3. Citation and BibTeX validation.
4. Venue template profiles and deterministic exports.
5. Section-level drafting workflow.
6. Figure/table generation from recorded result artifacts.
7. Artifact evaluation package export from replication/workspace state.
8. Reviewer objection ledger and rebuttal planning workflow.
9. Anonymization and blinding audit.
10. Submission-readiness gate.
11. Camera-ready checklist.
12. v0.8 eval fixtures, documentation, and release-process updates.

## Implemented Workflow Surface

v0.8 is implemented as first-class state and manager modules rather than a prose-only export:

- `src/gapforge/manuscript/` stores manuscript projects, sections, claim uses, bibliography records, traceability reports, figures, tables, venue templates, anonymization reports, reviewer panels, rebuttal/revision plans, and submission packages.
- `src/gapforge/artifact_eval/` exports artifact evaluation packages from replication/workspace state and assesses badge eligibility conservatively.
- `src/gapforge/release_gate/v08.py` checks the manuscript, citation, traceability, asset, artifact package, reviewer, rebuttal, submission package, and failed/negative experiment requirements.
- `src/gapforge/dashboard/static_site.py` renders manuscript dashboard pages for blockers, fake-looking citations, unsupported claims, assets, reviews, rebuttals, packages, and v8 gate status.
- `src/gapforge/api.py` exposes the same workflow for scripts and notebooks.

The release still makes a narrow claim: v0.8 validates workflow integrity on deterministic fixtures. It does not claim venue acceptance, complete third-party reproduction, broad benchmark validation, or real manuscript submission unless those external artifacts are recorded.
