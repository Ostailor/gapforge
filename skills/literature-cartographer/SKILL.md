---
name: literature-cartographer
description: Use when mapping a research topic into clusters, methods, datasets, assumptions, venues, saturated areas, and underexplored areas from papers.
---

# Literature Cartographer

## Purpose
Build a structured map of a research field from a topic and paper set. This skill is not a summary skill: it identifies clusters, subproblems, assumptions, evaluation practices, saturation signals, contradictions, and early gap candidates.

## When To Use
- Use after initial paper search, or when new papers have been added and the field map needs refreshing.
- Use before paper triage, gap mining, analogy generation, or experiment design.
- CLI: `gapforge map "topic"` or `gapforge map --run-id RUN_ID`.

## Inputs
- `ResearchTopic`
- normalized `Paper` records in `papers.json`
- optional existing `ResearchRunState`
- source metadata, venue, abstract, keywords, year, and provenance

## Outputs
- `FieldMap`
- `field_map.json`
- `field_map.md`
- nontrivial claim ledger entries for map-level statements

## Required Artifacts
- `papers.json` must exist before meaningful mapping.
- `field_map.json` and `field_map.md` must be written.
- Any claim about field structure must be recorded in `claims.json` with provenance.

## Procedure
1. Inspect title, abstract, venue, keywords, source, and year for each paper.
2. Group papers by recurring technical vocabulary and evaluation vocabulary.
3. Name clusters using domain-specific terms, not generic labels like "Cluster 1".
4. For each cluster, record representative papers, newest papers, dominant methods, open questions, and why the cluster matters.
5. Extract field-level concerns: major questions, common datasets, common metrics, assumptions, contradictions, and adjacent fields.
6. Mark saturated areas only when many papers share methods, datasets, or assumptions.
7. Mark underexplored areas conservatively when evidence is sparse or indirect.
8. Add claim ledger entries for nontrivial field statements.
9. Store concise public reasoning summaries only; do not store hidden chain-of-thought.

## Quality Bar
- Every cluster must link to paper IDs.
- Heuristic map signals must be phrased as uncertain unless evidence is strong.
- Do not hallucinate citations, venues, datasets, or results.
- Preserve source IDs and URLs for auditability.
- Separate "papers suggest" from "the field has proven".

## Failure Modes
- Overclaiming saturation from a small paper set.
- Treating source fallback metadata as authoritative literature coverage.
- Creating clusters that are only keyword buckets with no useful research interpretation.
- Inventing datasets, methods, or venues not present in metadata.
- Hiding uncertainty instead of recording limitations.

## Validation Checklist
- [ ] `field_map.json` and `field_map.md` exist.
- [ ] Each cluster has `paper_ids` and a useful description.
- [ ] Saturated and underexplored areas include uncertainty-aware wording.
- [ ] Nontrivial claims were added to the claim ledger.
- [ ] No invented citations, datasets, results, or venues appear.
- [ ] Provenance and reasoning summaries are concise and public.

## Examples
Run mapping on a topic:

```bash
gapforge map "low false positive collusion detection"
```

Refresh mapping for an existing run:

```bash
gapforge map --run-id 20260505T002206Z-low-false-positive-collusion-detection
```
