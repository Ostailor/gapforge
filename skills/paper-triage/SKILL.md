---
name: paper-triage
description: Use when deciding which papers deserve deep reading, method/results reading, skimming, metadata-only treatment, or novelty/related-work attention.
---

# Paper Triage

## Purpose
Prioritize reading effort. Triage ranks papers into tiers and roles; it is not a factual claim about paper correctness.

## When To Use
- After search and field mapping.
- Before PDF download, full-text parsing, deep reading, and novelty dossiers.
- CLI: `gapforge triage --run-id RUN_ID`, `gapforge triage "topic" --max-tier1 20`, `gapforge rank-papers --run-id RUN_ID`.

## Inputs
- `ResearchTopic`
- `Paper` records
- optional `FieldMap`, source coverage, citation graph, retrieval index, project corpus, paper roles

## Outputs
- `PaperTriageResult`
- `PaperTriageDecision`
- `paper_triage.json`
- `paper_triage.md`
- optional `paper_ranking.json` and `.md`

## Required Artifacts
- `papers.json`
- `paper_triage.json`
- `paper_triage.md`
- `paper_ranking.json` when v0.2/v0.3 ranking is used

## Procedure
1. Score topic relevance, directness, recency, citation signal, venue/source authority, benchmark importance, method novelty, limitation/open-problem signal, full-text availability, and source diversity.
2. Assign roles: frontier, seminal, survey, benchmark, dataset, method, theory, negative result, adjacent field, or unclear.
3. Assign tiers: Tier 1 deep read, Tier 2 method/results/limitations, Tier 3 skim, Tier 4 metadata only.
4. Preserve source and role diversity.
5. Flag papers important for novelty checking, cross-domain transfer, or baselines.
6. Recommend whether full text should be downloaded.
7. Add claim ledger entries only for actual claims about the set, not every score.

## Citation and Evidence Rules
- Do not infer results from citation count, venue, or title.
- A triage score is not evidence of quality.
- Use paper IDs in every decision.
- Label missing abstracts, missing PDFs, and fallback records as concerns.

## Uncertainty Rules
- Metadata-only decisions should stay provisional.
- Older survey/seminal papers may remain high priority.
- Full-text availability can boost reading priority but must not dominate relevance.

## Validation Checklist
- [ ] Each decision has paper ID, title, tier, score, reasons, concerns, role, and reading depth.
- [ ] Tier 1 is not dominated by one source when alternatives exist.
- [ ] Survey/seminal papers are not discarded solely for age.
- [ ] No fabricated paper claims appear.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Citation-count popularity bias.
- Source monoculture.
- Treating role guesses as facts.
- Promoting abstract-only notes to high confidence.

## Examples
```bash
gapforge triage --run-id RUN_ID
gapforge triage "low false positive collusion detection" --max-tier1 12
gapforge rank-papers --run-id RUN_ID
```
