# GapForge v2.5 Venue-Style Manuscript

v2.5 produces a venue-style manuscript package for the selected benchmark. Venue style means structure, rhetoric, format, pacing, and review-readiness conventions. It does not mean copied prose.

## Core Rule

Public paper TeX/source may be used only for structure and style analysis when license and availability allow inspection. The v2.5 workflow must not copy text, captions, equations, distinctive macros, figure wording, rebuttal phrasing, or author-specific expression.

## Venue Profile

Each venue-style package must define a venue profile:

- `venue_id`
- venue family
- submission track, if applicable
- page limit and appendix policy
- anonymity/blinding requirements
- artifact checklist requirements
- ethics, broader-impact, or limitation requirements
- review-form dimensions
- expected empirical evidence style
- citation and related-work density expectations
- reproducibility package expectations

If a venue profile is generic, the manuscript must say `generic_conference_style`, not imply fit to a named venue.

## Allowed Source Analysis

Allowed analysis of public papers:

- section ordering
- introduction argument shape
- contribution-list placement
- related-work organization
- method/result split
- figure/table placement patterns
- appendix organization
- limitation and ethics placement
- artifact checklist shape
- rebuttal issue grouping

Forbidden use:

- copying sentences or paragraphs
- copying captions or table text
- copying theorem, claim, or abstract wording
- copying distinctive macro names or formatting tricks as expression
- copying reviewer-response phrasing
- using private or unavailable source
- relying on source whose license forbids the use

## Manuscript Package Contents

The v2.5 venue-style package must include:

- source-style audit with allowed-use notes
- venue profile
- manuscript outline
- section-to-claim map
- abstract and introduction claim ledger links
- method and protocol section tied to benchmark artifacts
- real benchmark adapter section
- related-work section tied to v2.4 records
- results section tied to synthetic and adapter artifacts
- limitations section preserving synthetic and adapter validity limits
- reproducibility and artifact checklist
- appendix plan
- anonymization/blinding check, if applicable
- paper package manifest

Venue polish without claim traceability is not a v2.5 pass.

## Structure Requirements

The venue-style manuscript should make the contribution legible as:

1. a low-FPR evaluation-protocol problem,
2. a sequential specificity measurement benchmark,
3. a synthetic controlled benchmark with limitations,
4. a real benchmark adapter grounding path,
5. a claim-bounded artifact package rather than a deployment-valid detector.

The introduction must not overclaim novelty. The related-work section must carry closest-prior-work risk from v2.4. The limitations section must not hide real benchmark adapter weaknesses.

## Rhetoric Requirements

The manuscript may use venue-style rhetoric such as:

- problem-pressure framing
- explicit contribution bullets
- measurement/protocol positioning
- claim narrowing against closest prior work
- threat-to-validity organization
- artifact and reproducibility framing

It must not use rhetoric to create unsupported confidence. Strong claims require artifact links.

## Venue-Style Review Checks

The package must pass checks for:

- no copied prose from analyzed papers
- no unsupported venue-fit or acceptance language
- no missing claim links
- no fake citations or unknown BibTeX keys
- no hidden synthetic-only limitation
- no hidden real-adapter limitation
- no hidden harsh reviewer objections
- anonymity requirements, when relevant
- result tables and figures linked to artifacts
- limitations and ethics sections present when the venue expects them

## Rebuttal Package

v2.5 must include a rebuttal package shaped for OpenReview-style interaction:

- issue summary
- reviewer concern clusters
- evidence-backed responses
- manuscript changes already made
- concessions
- additional experiments or adapter work that remain future work
- claims withdrawn or narrowed
- unresolved objections

Rebuttal text cannot invent results, citations, or commitments that are not supported by the release artifacts.

## Completion Output

The venue-style manuscript workflow ends with one status:

- `venue_style_package_ready`: structure, claim traceability, source-use audit, and review checks pass.
- `venue_style_package_ready_with_objections`: package exists, but material objections remain visible.
- `revise_manuscript`: package has structural, traceability, or style issues.
- `blocked_source_use`: source-style analysis used unavailable, private, or disallowed material.
- `blocked_plagiarism_risk`: copied or too-close expression is detected.

Only the first two statuses can feed a v2.5 release pass, and neither implies venue acceptance.

## Scriptable and Visible Surface

CLI:

```bash
gapforge venue-profile-list
gapforge venue-profile --venue generic_ml_conference
gapforge manuscript-set-venue-profile --manuscript-id <manuscript-id> --venue generic_ml_conference
gapforge style-corpus-add-tex --path <allowed-source-or-fixture.tex> --venue generic_ml_conference
gapforge style-corpus-report
gapforge venue-style-analyze --venue generic_ml_conference
gapforge venue-style-recommend --manuscript-id <manuscript-id>
gapforge manuscript-rewrite-for-venue --manuscript-id <manuscript-id> --venue generic_ml_conference
gapforge manuscript-style-report --manuscript-id <manuscript-id>
gapforge dashboard --project-id <selected-project-id> --include-selected-v25
```

API:

- `select_venue_profile(...)`
- `ingest_style_corpus(...)`
- `analyze_venue_style(...)`
- `rewrite_manuscript_for_venue(...)`

Dashboard:

- `venue_profiles.html`
- `style_corpus.html`
- `venue_style_analysis.html`
- `v25_release_gate.html`

The dashboard and API expose structure, source-use warnings, style recommendations, copied-text warnings, and checklist blockers. They do not permit copied prose, fake citations, hidden limitations, or venue-acceptance claims.
