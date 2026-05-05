# Known Limitations

GapForge is a research ideation aid, not an autonomous literature reviewer or publication decision system.

## Cross-Version Limits

- It does not guarantee exhaustive search.
- It does not guarantee novelty.
- It does not replace expert reading or domain judgment.
- Offline fallback and synthetic fixtures are smoke-test artifacts.
- Source APIs can be incomplete, rate-limited, stale, or unavailable.
- PDF extraction can miss text, tables, references, equations, and layout.
- Citation counts and venue heuristics can bias ranking.

## v0.1 Limits

v0.1 is deterministic and metadata/abstract-heavy. It can create useful scaffolding but should not be treated as real literature coverage.

## v0.2 Limits

v0.2 adds full-text artifacts, evidence spans, coverage reports, citation graphs, novelty dossiers, and strict reports. Remaining risks:

- full-text parsing is lightweight and may miss section boundaries
- closest-prior-work search is still conservative and partly lexical
- cross-domain analogies may remain query-only
- gap evidence matrices are only as strong as available notes and spans
- human review is still necessary before pursuing directions

## v0.3 Limits

v0.3 adds project memory, hybrid retrieval, active-loop decisions, optional LLM-backed skills, related-work matrices, maturation, protocols, review queues, dashboards, and manuscript packages. Remaining risks:

- semantic retrieval ranks candidates but does not prove relevance or novelty
- deterministic hash embeddings are useful for offline tests but not research-grade semantic models
- optional provider LLM outputs remain untrusted until schema-valid and evidence-located
- actual Codex/GPT-5.4 canary validation is opt-in and was not available in the May 5, 2026 local verification environment
- project memory can carry stale beliefs if not reviewed
- source policy profiles are transparent heuristics, not field-complete standards
- manuscript packages are starter kits and must not imply results

## v0.3 Goals

- improve closest-prior-work search using retrieval, citation graph, source policies, and project memory
- make unsupported claims, contradictions, and rejected ideas visible
- guide human review with explicit queues
- mature research directions through evidence gates
- export honest writing packages with missing-work labels

## v0.3 Non-Goals

- exhaustive autonomous literature review
- mandatory live LLM, embedding, or source API calls
- silent trust in model-generated citations
- hiding poor coverage behind polished reports
- presenting fixture/fallback data as real literature conclusions
- exporting fake results or publication-ready claims without human validation

## Operational Guidance

Use strict mode and coverage assessment before interpreting outputs:

```bash
gapforge coverage --run-id <run-id>
gapforge assess-coverage --run-id <run-id> --profile ai_safety
gapforge report --run-id <run-id> --strict
gapforge review-queue --run-id <run-id>
```

When in doubt, treat GapForge output as a to-do list for search, reading, and review rather than a conclusion.

## Latest Verification Limitation

The May 5, 2026 deterministic verification pass succeeded, including v2/v3 evals, coverage, and v2/v3 smoke runs. The fake-agent canary succeeded. Actual Codex/GPT-5.4 canaries were recorded as failed/not passed because the real-run environment variables were unset. Therefore v0.3 actual-run validation remains incomplete until a real Codex/GPT-5.4 canary is executed and accepted by human review.
