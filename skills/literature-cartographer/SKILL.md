---
name: literature-cartographer
description: Use when mapping a research topic into clusters, methods, datasets, assumptions, venues, saturation signals, and underexplored areas from a paper set.
---

# Literature Cartographer

## Purpose
Build a structured field map. This is not summarization; it identifies clusters, subproblems, evaluation habits, shared assumptions, contradictions, saturated areas, and early gap candidates.

## When To Use
- After search or manual ingestion.
- After analogy or citation expansion adds papers.
- Before triage, gap mining, novelty checking, or final reporting.
- CLI: `gapforge map "topic"` or `gapforge map --run-id RUN_ID`.

## Inputs
- `ResearchTopic`
- `papers.json`
- optional `paper_sections.json`, `paper_notes.json`, retrieval results, source coverage, and project memory context

## Outputs
- `FieldMap`
- `field_map.json`
- `field_map.md`
- claim ledger entries for nontrivial field statements

## Required Artifacts
- `papers.json`
- `field_map.json`
- `field_map.md`
- `claims.json` for map-level claims

## Procedure
1. Inspect titles, abstracts, venues, keywords, years, roles, and available notes/sections.
2. Cluster papers by recurring problem, method, dataset, metric, venue, and assumption signals.
3. Name clusters with domain terms, not generic labels.
4. Record representative and newest papers for each cluster.
5. Extract major questions, dominant methods, common datasets, common metrics, assumptions, contradictions, adjacent fields, and limitations.
6. Mark saturated areas only when several papers share methods, datasets, or assumptions.
7. Mark underexplored areas conservatively and link supporting paper IDs.
8. Add claim ledger entries for nontrivial statements.
9. Store concise public reasoning summaries only.

## Citation and Evidence Rules
- Cite paper IDs for every cluster and field-level claim.
- Do not invent venues, datasets, metrics, citations, or results.
- If source coverage is fallback/offline, label findings as preliminary.
- Prefer EvidenceSpan locators when field claims use full-text sections.

## Uncertainty Rules
- Weak paper sets imply low or medium confidence.
- Saturation and underexploration are hypotheses unless coverage is strong.
- Missing source families should appear in limitations.

## Validation Checklist
- [ ] Every cluster links paper IDs.
- [ ] Saturated and underexplored areas state evidence basis.
- [ ] Nontrivial claims are in the claim ledger.
- [ ] Coverage limitations are visible.
- [ ] No hidden chain-of-thought is stored.
- [ ] No fabricated citations/results appear.

## Failure Modes
- Treating keyword buckets as meaningful clusters.
- Overclaiming from abstracts or fallback metadata.
- Hiding contradictions.
- Forgetting that a field map is not a novelty assessment.

## Examples
```bash
gapforge map "low false positive collusion detection"
gapforge map --run-id 20260505T000000Z-low-false-positive-collusion-detection
gapforge run "topic" --v3 --build-index
```
