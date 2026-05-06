# v0.5 Live Source Policy

v0.5 live-literature validation depends on source reliability. Live sources are allowed for release validation, but normal CI remains offline and deterministic.

## Principles

- Live source calls are release-validation tasks, not CI requirements.
- Every live query must become a `SearchQueryRecord`.
- Source failures must be visible in source coverage and campaign reports.
- A campaign may pass by refusing recommendation when source coverage is insufficient.
- No source connector is assumed complete.

## Source Families

### AI Safety and Machine Learning

Required or strongly recommended:

- arXiv
- OpenReview when relevant
- Semantic Scholar-style metadata
- CrossRef/DOI lookup
- citation expansion
- survey/systematic-review queries

Coverage warnings:

- missing OpenReview for conference-heavy topics
- no citation-neighborhood expansion
- no survey/background search
- no full text for Tier 1 papers

### Medicine

Required or strongly recommended:

- PubMed-like source or explicit unavailable warning
- DOI/CrossRef lookup
- systematic review queries
- guideline/review paper search where appropriate

Coverage warnings:

- medical claims without PubMed-like search
- no systematic review search
- cross-domain transfer promoted without source-field evidence

### Economics

Required or strongly recommended:

- CrossRef/DOI lookup
- Semantic Scholar-style metadata
- working-paper and survey queries where available
- citation expansion

Coverage warnings:

- cartel/economics claims without survey or canonical background search
- no citation-neighborhood check

## Query Policy

Each campaign should include query types for:

- topic keywords
- exact method/metric/dataset phrases
- closest-prior-work title and author expansion
- benchmark and baseline queries
- survey/systematic-review queries
- limitations/failure mode queries
- adjacent-field transfer queries when analogies are proposed
- citation-neighborhood expansion

## Stopping Criteria

A campaign may stop as ready only when:

- required source families were searched or explicitly waived by human review
- closest prior work was found or novelty remains explicitly unknown
- coverage confidence is at least medium for the field and task
- no required searches remain pending

A campaign should stop as not ready when:

- live sources are unavailable
- source policy requirements are unmet
- novelty remains unknown after budgeted search
- closest prior work appears to solve the proposed gap
- human review flags an obvious missing paper

## CI Policy

Tests may mock live sources or use recorded metadata fixtures. CI must not require network access, API keys, Codex/GPT-5.4, paid APIs, or live source availability.
