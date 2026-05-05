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

`sources/ranking.py` handles:

- newer-paper boost
- exact title/topic match boost
- authoritative venue boost
- citation-count boost
- source diversity controls
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
