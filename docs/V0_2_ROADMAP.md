# GapForge v0.2 Roadmap

v0.2 is the full-text and stronger-novelty release. It should reduce the main v0.1 risk: deterministic metadata and abstract heuristics can produce useful smoke-test artifacts, but they are not enough to support serious research decisions.

This roadmap is a planning contract only. It does not imply the capabilities below are already implemented.

## v0.2 Must-Have

### Full-Text Ingestion

- Add manual paper/PDF ingestion for local files.
- Store ingested papers inside a run without losing source metadata.
- Preserve provenance for user-provided PDFs and manually entered papers.
- Record whether a paper note is based on full text, abstract only, or manually supplied metadata.

### Section-Level Paper Parsing

- Extract structured text sections from PDFs when possible.
- Preserve page numbers, section headings, and extraction confidence.
- Store section records in durable run artifacts.
- Degrade gracefully when a PDF has bad OCR, missing text, or unusual layout.

### Evidence Spans

- Extend evidence records with page and section locators.
- Link paper-note claims, limitations, methods, datasets, metrics, and results to evidence spans.
- Keep concise public reasoning summaries; do not store hidden chain-of-thought.
- Validate that full-text-derived claims have at least one locator.

### Full-Text-Aware Deep Reading

- Update Deep Reading to prefer section-level full text when available.
- Separate author-stated claims from demonstrated results and from GapForge inferences.
- Mark abstract-only notes as lower confidence unless strong source metadata justifies otherwise.
- Avoid fabricating methods, datasets, or results when the source text does not support them.

### Stronger Novelty Gate

- Build closest-prior-work dossiers for each candidate gap or hypothesis.
- Search the current paper store first, then expand through source connectors and citation/related-work edges.
- Record search queries, sources searched, closest papers, similarity rationale, missing searches, and decisive difference needed.
- Reject or revise ideas that lack a concrete difference from closest prior work.
- Never mark novelty as strong without checked closest prior work.

### Source Coverage Reports

- Produce a run artifact that reports source coverage by connector, query, date window, source failures, cached responses, and fallback mode.
- Clearly distinguish live-source results from deterministic fallback metadata.
- Include source coverage in `final_report.md`.

### Human-in-the-Loop Review

- Add review/edit commands for claims, paper notes, gaps, novelty assessments, and experiment plans.
- Preserve manual edits as provenance events rather than overwriting generated artifacts silently.
- Let users mark claims verified, contested, uncertain, or rejected with notes.

### Stronger Evaluation Fixtures

- Add full-text fixture papers or fixture excerpts with section/page locators.
- Add duplicate ideas that require more than title lexical overlap to reject.
- Add fixture cases where abstract-only reading would produce a wrong or overconfident conclusion.
- Add evaluator checks for evidence-span coverage, source coverage reporting, and novelty dossier quality.

## v0.2 Should-Have

- Citation graph and related-work expansion from references, citations, and semantically similar papers.
- Source policy configuration for allowed connectors, max results, date windows, and fallback behavior.
- Per-field venue/source authority configuration.
- Paper-store deduplication that combines DOI, arXiv IDs, Semantic Scholar IDs, citation metadata, and title similarity.
- Better report ranking that avoids recommending gaps supported only by weak extraction artifacts.
- Report sections that summarize source coverage, full-text coverage, fallback mode, and unresolved novelty searches.
- CLI affordances for adding a PDF, adding a manual paper, listing artifacts, and opening the latest report path.

## Deferred to v0.3

- LLM-backed full-text synthesis as a default path.
- Browser-driven paper acquisition from publisher pages.
- Automatic OCR for scanned PDFs.
- Multi-run project memory and cross-run claim reconciliation.
- Collaborative review workflows with approvals and reviewer assignment.
- Export to manuscript outlines, rebuttal plans, or experiment-tracking systems.
- A real benchmark of research usefulness against human expert judgments.

## Non-Goals for v0.2

- GapForge should not claim exhaustive literature review coverage.
- GapForge should not present offline fallback metadata as real source evidence.
- GapForge should not hide uncertainty to make reports look more decisive.
- GapForge should not require paid APIs for the default smoke-test path.
- GapForge should not store hidden chain-of-thought in artifacts.

## Development Sequence

1. Define full-text artifact models and validation rules.
2. Implement local PDF/manual-paper ingestion.
3. Integrate section-level text into Deep Reading.
4. Upgrade evidence spans and claim-ledger validation.
5. Add source coverage artifacts.
6. Implement novelty dossiers and related-work expansion.
7. Add human review/edit commands.
8. Expand evaluation fixtures and metrics.
9. Update reports to expose full-text coverage, fallback mode, and novelty-dossier status.
