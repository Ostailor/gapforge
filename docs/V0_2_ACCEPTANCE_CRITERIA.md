# GapForge v0.2 Acceptance Criteria

These criteria define pass/fail behavior for v0.2. They are intentionally concrete so implementation can be tested without implying GapForge performs exhaustive literature reviews.

## Full-Text Ingestion

Pass:

- A user can add a local PDF to an existing run from the CLI.
- The run stores the paper metadata, PDF provenance, extracted text status, and artifact paths.
- Bad or unreadable PDFs produce a clear warning artifact rather than crashing the run.
- Manual paper metadata can be added when no PDF is available.

Fail:

- PDF ingestion silently drops provenance.
- A failed extraction is treated as successful full-text reading.
- Manual papers are indistinguishable from live-source papers.

## Section-Level Parsing

Pass:

- Extracted sections include paper ID, section title, page range or page number, text, and extraction confidence.
- At least one fixture PDF/excerpt produces Introduction, Method, Results or Evaluation, and Limitations-like sections when present.
- Section parsing output is persisted in JSON.

Fail:

- Section text is only stored as one undifferentiated blob.
- Page or section locators are unavailable for evidence produced from full text.

## Evidence Spans and Claim Ledger

Pass:

- Full-text-derived claims include evidence spans with paper ID and page/section locator.
- Validation fails if a claim is marked supported from full text without evidence spans.
- Counterevidence can reference section-level evidence.
- The claim ledger export includes locator information.

Fail:

- Supported full-text claims can exist without evidence.
- Evidence locators are only free-text notes with no paper/section/page structure.

## Full-Text-Aware Deep Reading

Pass:

- Deep Reading uses full-text sections when available and records that source basis.
- Abstract-only notes remain visibly abstract-only.
- Main results are only populated when supported by abstract or full-text evidence.
- Tests cover a fixture where the abstract lacks results but the full text contains results.

Fail:

- Deep Reading fabricates datasets, metrics, or results from metadata.
- Full-text and abstract-only notes are mixed without a visible source-basis distinction.

## Stronger Novelty Gate

Pass:

- Each nontrivial gap or hypothesis can produce a closest-prior-work dossier.
- A dossier records searched sources, queries, nearest papers, similarity rationale, missing searches, and decisive difference needed.
- The novelty gate searches beyond current-run lexical overlap when configured to do so.
- Duplicate fixture ideas requiring related-work expansion are rejected.
- `strong` novelty is impossible without closest prior work.

Fail:

- `pursue` or `strong` novelty is assigned with no closest-prior-work evidence.
- Missing searches are omitted from the report.
- Lexical title overlap is the only duplicate detection path.

## Source Coverage Reports

Pass:

- Each run records source coverage by query, source, result count, date window, failures, cache hits if available, and fallback mode.
- `final_report.md` distinguishes live source coverage from offline fallback mode.
- Search failures are visible but do not kill the whole run.

Fail:

- Reports imply live search coverage when `GAPFORGE_DISABLE_NETWORK=1` was used.
- Fallback metadata appears as real literature evidence without warning.

## Human-in-the-Loop Review

Pass:

- CLI commands allow users to edit or annotate claims, paper notes, gaps, novelty assessments, and experiments.
- Manual changes are stored with user/manual provenance.
- Validation can distinguish generated and manually verified claims.

Fail:

- Manual edits overwrite generated records without provenance.
- Review commands bypass validation of supported claims or novelty claims.

## Evaluation Fixtures

Pass:

- At least two fixtures include full-text fixture papers or section-level excerpts.
- Evals include at least one abstract-only failure case, one semantic duplicate case, and one missing-source-coverage case.
- Metrics include evidence-span coverage and novelty-dossier quality.
- `gapforge eval` remains offline.

Fail:

- Evals require live APIs or API keys.
- All fixture novelty checks can be passed by title matching alone.

## Reports

Pass:

- `final_report.md` includes source coverage, full-text coverage, fallback-mode status, rejected ideas, uncertainty, and the strongest recommended direction.
- The report distinguishes evidence-backed claims, hypotheses, unsupported claims, and manually verified claims.
- The report does not claim exhaustive literature coverage.

Fail:

- Reports present smoke-test outputs as real literature conclusions.
- Reports hide missing full-text coverage or missing novelty searches.

## Release Gates

v0.2 cannot be tagged unless:

- `make lint` passes.
- `make test` passes.
- `make eval` passes.
- A documented smoke run produces `final_report.md`.
- `docs/KNOWN_LIMITATIONS.md` is updated for any remaining limitations.
- `CHANGELOG.md` includes the v0.2 entry.
