# GapForge v0.8 Manuscript Workflow

v0.8 manuscript workflow turns GapForge research state into an auditable draft package. It is designed to make missing work visible, not to make the paper look finished before the evidence is ready.

## Workflow Stages

### 1. Create Manuscript Project

Inputs should include:

- project ID
- direction ID
- experiment workspace IDs
- benchmark workspace IDs
- venue profile
- anonymity mode
- target paper type
- human owner or reviewer

The project record should link existing v5 literature artifacts, v6 empirical artifacts, and v7 benchmark/replication artifacts.

### 2. Import Claims and Evidence

The manuscript project should import:

- claim ledger entries
- evidence spans and paper locators
- source coverage reports
- closest-prior-work dossiers
- related-work matrix rows
- experiment protocols
- execution records
- result artifacts
- benchmark cards
- comparison and error-analysis outputs
- replication package status

Claims that cannot be linked must be marked as unsupported, hypothesis, limitation, future work, or removed from the submission draft.

### 3. Manage Citations and BibTeX

Citation management should:

- create keys only from known paper records or user-supplied bibliographic records
- preserve source metadata provenance
- report missing authors, titles, years, venues, DOIs, and URLs
- detect duplicate keys and unresolved citations
- keep unknown references as search requests rather than invented BibTeX
- write `references.bib` only from validated records

BibTeX validity does not prove the cited paper supports the sentence. Support still requires claim and evidence links.

### 4. Select Venue Template

A venue profile should define:

- expected sections
- page-limit metadata
- anonymity requirements
- artifact evaluation requirements
- checklist fields
- supplemental material expectations
- camera-ready checklist items

Template export should be deterministic and CI-safe. It may emit Markdown and LaTeX-ready source files, but normal CI must not require LaTeX compilation.

### 5. Draft by Section

Each section should track:

- status: missing, outline, draft, reviewed, blocked, accepted
- allowed claim types
- required claim links
- required citations
- figure/table dependencies
- reviewer comments
- human approval

Recommended section gates:

- **Abstract**: no unsupported novelty, result, or contribution claims.
- **Introduction**: every contribution maps to a supported claim or visible hypothesis.
- **Related Work**: closest prior work and missing searches are visible.
- **Method**: implementation claims link to design, code, or protocol artifacts.
- **Experiments**: every result links to execution records, result artifacts, statistics, and reproducibility status.
- **Limitations**: negative, failed, underpowered, and incomplete work is visible.
- **Artifact Appendix**: generated from replication and workspace state.

### 6. Generate Figures and Tables

Figures and tables should be generated from:

- parsed metric results
- statistical summaries
- benchmark comparison tables
- ablation manifests
- sweep outputs
- error and slice analysis
- replication status records

Each figure or table should record:

- source artifact IDs
- source hashes where available
- generation command or spec
- caption
- limitations
- whether the content is fixture, pilot, main, benchmark, failed, negative, or underpowered

Do not create a figure or table that implies an experiment ran when only a protocol, scaffold, or smoke run exists.

### 7. Run Manuscript Audit

The audit should check:

- unsupported claims
- unresolved citations
- fake or unknown BibTeX keys
- novelty claims without prior-work support
- result claims without artifacts
- hidden failed or negative results
- missing baselines or metrics
- missing artifact evaluation package
- blinding risks
- unresolved reviewer objections
- missing human approvals

The audit output should be both human-readable and machine-readable.

### 8. Export Draft Package

A manuscript-ready export should include:

- manuscript draft
- references
- claim traceability report
- citation audit
- figure/table manifest
- limitations report
- artifact evaluation package status
- reviewer objection summary
- submission-readiness report

Manuscript-ready export may include blockers. It must not call itself submission-ready unless the submission gate passes.

## Suggested Command Surface

The implemented v0.8 command surface is:

```bash
gapforge manuscript-create --project-id <project-id> --direction-id <direction-id> --workspace-id <workspace-id> --title "..."
gapforge manuscript-status --manuscript-id <manuscript-id>
gapforge manuscript-sections --manuscript-id <manuscript-id>
gapforge manuscript-report --manuscript-id <manuscript-id>
gapforge bibliography-build --manuscript-id <manuscript-id>
gapforge citation-check --manuscript-id <manuscript-id>
gapforge manuscript-traceability --manuscript-id <manuscript-id>
gapforge manuscript-table --manuscript-id <manuscript-id> --type result_table
gapforge manuscript-figure --manuscript-id <manuscript-id> --type metric_plot
gapforge manuscript-set-venue --manuscript-id <manuscript-id> --venue generic_conference
gapforge submission-checklist --manuscript-id <manuscript-id>
gapforge anonymize-manuscript --manuscript-id <manuscript-id>
gapforge artifact-eval-package --manuscript-id <manuscript-id>
gapforge manuscript-review --manuscript-id <manuscript-id>
gapforge rebuttal-plan --manuscript-id <manuscript-id>
gapforge submission-package --manuscript-id <manuscript-id> --type review
gapforge dashboard --manuscript-id <manuscript-id>
gapforge v8-release-gate --write-report --json
```

The same workflow is scriptable through `gapforge.api`: `create_manuscript`, `build_bibliography`, `draft_manuscript`, `render_manuscript`, `generate_manuscript_assets`, `run_traceability_check`, `set_venue`, `submission_checklist`, `anonymize_manuscript`, `create_artifact_eval_package`, `manuscript_review`, `rebuttal_plan`, `submission_package`, and `v8_release_gate`.

## Status Language

Use precise status labels:

- `draft_exported`
- `manuscript_ready_with_blockers`
- `manuscript_ready`
- `submission_ready`
- `submission_not_ready`
- `camera_ready_pending_acceptance`
- `camera_ready`

Do not use:

- `accepted`
- `published`
- `venue-approved`
- `camera-ready` without acceptance metadata
- `result proven` without artifact-backed evidence

## Status Discipline

`drafting` or `manuscript-ready` is not submission readiness. It means a manuscript project exists and sections can be inspected. `review_ready` means internal reviewer/artifact checks have run and blockers are visible. `submission_ready` means the venue-aware gate passes. `camera_ready` requires addressed reviewer/rebuttal blockers and must not imply venue acceptance.

Never hide uncertainty: unsupported claims, missing citations, failed runs, fake-looking citation keys, artifact-package blockers, and anonymization leaks belong in reports and dashboards.
