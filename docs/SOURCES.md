# Source Connectors

GapForge source connectors normalize external research metadata into the shared `Paper` model.

## Interface

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

Supported source modules:

- `ArxivSource`
- `CrossrefSource`
- `DblpSource`
- `OpenReviewSource`
- `SemanticScholarSource`
- `WebSource`

The first working version does not require API keys. Sources that are unavailable or rate-limited degrade gracefully and return deterministic fallback metadata where appropriate.

## HTTP and Caching

All networked connectors use `CachedHttpClient`.

The client provides:

- user-agent header
- timeout
- retry loop
- response cache under `.gapforge_cache/`
- environment escape hatch: `GAPFORGE_DISABLE_NETWORK=1`

Cache diagnostics:

```bash
gapforge cache-info
```

Set `GAPFORGE_CACHE_DIR=/path/to/cache` to override the cache location. Set `GAPFORGE_DISABLE_NETWORK=1` for offline tests and smoke runs; uncached network requests fail fast and connectors should degrade gracefully.

Tests must mock HTTP responses or disable network access. Do not write tests that depend on live public APIs.

## Source Coverage

Every search should create a `SearchQueryRecord` with:

- query text
- source names
- purpose, such as `initial_topic`, `analogy`, `novelty`, `citation_expansion`, or `manual`
- max results and date filters
- result paper IDs
- failure messages

Run coverage reporting with:

```bash
gapforge coverage
gapforge coverage --run-id <run-id>
```

Coverage artifacts:

- `source_coverage.json`
- `source_coverage.md`
- `full_text_coverage.md`

In offline mode, coverage must clearly label fallback records and missing full text. A report produced from fallback metadata is a smoke test, not a literature conclusion.

## PDF and Full-Text Sources

PDF handling is intentionally conservative:

- arXiv PDF URLs may be inferred from `arxiv_id`.
- OpenReview and generic sources use explicit `pdf_url` when present.
- CrossRef and DBLP do not invent PDF URLs unless metadata provides a reliable one.
- `GAPFORGE_DISABLE_NETWORK=1` skips downloads and records a warning.

Commands:

```bash
gapforge download-pdfs --run-id <run-id> --max-papers 10 --skip-existing
gapforge parse-fulltext --run-id <run-id>
gapforge add-pdf --run-id <run-id> /path/to/paper.pdf --title "Paper Title" --parse
```

Downloaded or manually added PDFs are stored under the run directory, hashed, and represented as `PaperArtifact` objects. Parsed text becomes `PaperSection` objects and may produce `EvidenceSpan` locators for downstream reading and gap mining.

## Paper Normalization

Connectors must populate as many fields as possible:

- `id`
- `title`
- `authors`
- `abstract`
- `year`
- `published_date`
- `venue`
- `source`
- `url`
- `pdf_url`
- `doi`
- `arxiv_id`
- `openreview_id`
- `semantic_scholar_id`
- `citation_count`
- `keywords`
- `raw_metadata`
- `provenance`

`raw_metadata` should preserve the original source payload for later auditing.

## Ranking and Deduplication

`sources/ranking.py` and `sources/ranking_v2.py` handle:

- newer-paper boost
- exact title/topic match boost
- authoritative venue boost
- citation-count boost
- source diversity controls
- role diversity controls for frontier, survey, benchmark, dataset, method, theory, negative-result, and adjacent-field papers
- full-text availability signals
- deduplication by DOI, arXiv ID, and high title similarity

Ranking is deliberately separate from connectors. Connectors fetch and normalize; ranking decides cross-source ordering.

## Adding a Source

1. Create `src/gapforge/sources/<name>_source.py`.
2. Subclass `ResearchSource`.
3. Accept an optional `CachedHttpClient` in `__init__`.
4. Implement `search(...)` with the common signature.
5. Use `self.http.get_json(...)` or `self.http.get_text(...)`; never call `urlopen` directly.
6. Catch source/network errors and degrade gracefully.
7. Normalize every result into `Paper`.
8. Preserve source payloads in `raw_metadata`.
9. Attach public provenance with `source_provenance(...)`.
10. Register the connector in `sources/__init__.py` and `skill_registry.default_sources`.
11. Add mocked HTTP tests.

Do not add API-key requirements for the default search path unless the connector also has a keyless fallback.
