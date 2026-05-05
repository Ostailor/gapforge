# Source Connectors and Coverage

GapForge source connectors normalize research metadata into the shared `Paper` model and record how search coverage was obtained. Source output is evidence about what was searched; it is not proof that the literature has been exhausted.

## Connector Interface

Every connector implements:

```python
ResearchSource.search(
    query: str,
    *,
    max_results: int,
    sort: str,
    date_from: str | None,
    date_to: str | None,
) -> list[Paper]
```

Current connectors:

- arXiv
- CrossRef
- DBLP
- OpenReview
- Semantic Scholar
- generic web metadata placeholder

The default path must not require API keys. If a source is unavailable, rate-limited, or disabled, it should fail gracefully and record warnings.

## HTTP, Cache, and Offline Mode

Networked sources use `CachedHttpClient` for:

- user-agent
- timeouts
- retries
- response cache under `.gapforge_cache/`
- deterministic failure when `GAPFORGE_DISABLE_NETWORK=1`

Commands:

```bash
gapforge cache-info
gapforge search "topic" --max-results 50 --sources arxiv,crossref
```

Tests must use mocked HTTP or offline fixtures. No test should require a live public API.

## Search Query Ledger

Every source search should create a `SearchQueryRecord`:

- query
- source names
- purpose: `initial_topic`, `analogy`, `novelty`, `citation_expansion`, or `manual`
- max results and date filters
- execution time
- result paper IDs
- failure messages
- provenance

The ledger lets reports say exactly what was searched.

## Source Coverage Reports

Run:

```bash
gapforge coverage --run-id <run-id>
gapforge assess-coverage --run-id <run-id> --profile ai_safety
gapforge next-searches --run-id <run-id>
```

Artifacts:

- `source_coverage.json`
- `source_coverage.md`
- `full_text_coverage.md`
- `coverage_stopping_assessment.json`
- `coverage_stopping_assessment.md`

Coverage reports include source failures, fallback/offline records, full-text coverage, abstract-only counts, and policy warnings.

## v0.3 Source Policy Profiles

Profiles live in `src/gapforge/sources/policies.py`.

Profiles define:

- required and recommended sources
- venue keywords
- required query patterns
- recency windows
- minimum papers and full-text papers
- minimum surveys
- citation expansion rounds
- novelty and adjacent-field search requirements

Built-in profiles include machine learning, AI safety, multi-agent systems, physics, biology, economics, medicine, cybersecurity, and generic.

Strict reports and novelty gates should not upgrade novelty when policy-critical coverage is missing.

## PDF and Full Text

PDF URL inference is conservative:

- arXiv can infer `https://arxiv.org/pdf/{id}` from `arxiv_id`
- OpenReview and generic sources use explicit `pdf_url`
- CrossRef/DBLP do not invent PDF URLs unless metadata provides a reliable one

Commands:

```bash
gapforge download-pdfs --run-id <run-id> --max-papers 10 --skip-existing
gapforge parse-fulltext --run-id <run-id>
gapforge parse-structure --run-id <run-id>
gapforge add-pdf --run-id <run-id> /path/to/file.pdf --title "Paper Title" --parse
```

Downloaded or manual PDFs are stored as `PaperArtifact` records. Parsed text becomes `PaperSection`, `EvidenceSpan`, `ReferenceRecord`, `TableRecord`, `EquationRecord`, `CaptionRecord`, and `OcrAttemptRecord` where possible. Extraction warnings remain visible.

## Ranking and Deduplication

Ranking utilities combine:

- topic relevance
- recency
- citation count
- venue/source authority
- source diversity
- role diversity
- full-text availability
- closest-prior-work signal
- adjacent-field transfer signal
- survey/systematic-review signal

Deduplication uses DOI, arXiv ID, Semantic Scholar ID, exact title, and title similarity. Ranking is separate from source fetching.

## Adding a Source

1. Create `src/gapforge/sources/<name>_source.py`.
2. Subclass `ResearchSource`.
3. Accept an optional `CachedHttpClient`.
4. Implement `search(...)`.
5. Use the HTTP client wrapper, not direct network calls.
6. Catch source/network errors and record graceful failures.
7. Normalize every result into `Paper`.
8. Preserve original payloads in `raw_metadata`.
9. Attach public provenance.
10. Register the source.
11. Add mocked HTTP tests and coverage behavior tests.

Do not add a required API-key path unless a no-key fallback remains available.
