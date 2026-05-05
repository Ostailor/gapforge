---
name: hybrid-retrieval
description: Use when building or querying GapForge indexes over papers, sections, evidence spans, claims, gaps, novelty dossiers, and project memory.
---

# Hybrid Retrieval

## Purpose
Find relevant prior work, evidence, counterevidence, and project-memory context using auditable lexical plus semantic retrieval.

## When To Use
- Before novelty dossiers and gap counterevidence search.
- When searching full-text sections or project memory.
- CLI: `gapforge build-index`, `gapforge search-index`, `gapforge explain-retrieval`.

## Inputs
- run or project state
- papers, sections, evidence spans, notes, claims, gaps, novelty dossiers, memory records
- query text

## Outputs
- `RetrievalDocument`
- `RetrievalResult`
- `IndexManifest`
- retrieval index files under `retrieval/`
- `retrieval_coverage.md`

## Required Artifacts
- `retrieval/manifest.json`
- indexed documents and embeddings
- retrieval coverage report

## Procedure
1. Build documents from metadata, sections, evidence spans, notes, claims, gaps, dossiers, and memory.
2. Build lexical scores and local deterministic embeddings.
3. Persist manifest, documents, and embeddings.
4. Search with hybrid score and rerank by exact phrases, section type, evidence type, novelty relevance, paper role, and full-text availability.
5. Return object IDs, scores, snippets, locators, and metadata.
6. Use retrieval results as candidates, not conclusions.

## Citation and Evidence Rules
- Retrieval results must keep object IDs and locators.
- Do not create paper records from retrieval text alone.
- Do not treat score as evidence.
- Cite source papers/spans in downstream claims.

## Uncertainty Rules
- Low score or generic snippets should not drive claims.
- Deterministic hash embeddings are fallback semantics, not research-grade embeddings.
- Missing index coverage must be reported.

## Validation Checklist
- [ ] Index manifest exists.
- [ ] Search returns typed results with scores and locators.
- [ ] Evidence spans can rank above generic metadata for specific queries.
- [ ] No live API is required.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Opaque retrieval without provenance.
- Treating semantic similarity as novelty.
- Letting project-memory context masquerade as current-run evidence.

## Examples
```bash
gapforge build-index --run-id RUN_ID
gapforge search-index --run-id RUN_ID "low false positive benchmark" --top-k 20
gapforge explain-retrieval --run-id RUN_ID "closest prior work"
```
