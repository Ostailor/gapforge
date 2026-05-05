---
name: deep-reading
description: Use when producing source-grounded paper notes from abstracts or parsed full text while separating claims, evidence, assumptions, results, and limitations.
---

# Deep Reading

## Purpose
Create structured notes that distinguish what a paper claims from what it demonstrates. Deep reading is evidence extraction, not creative completion.

## When To Use
- After triage for Tier 1/Tier 2 papers.
- After parsing full text.
- When a specific paper needs locator-backed notes.
- CLI: `gapforge read --run-id RUN_ID --tier 1`, `gapforge read-llm --run-id RUN_ID --tier 1 --dry-run-prompts`.

## Inputs
- selected `Paper` records
- `PaperSection` records when available
- `EvidenceSpan` records
- triage decisions
- topic and optional retrieval context

## Outputs
- `PaperNote`
- `paper_notes.json`
- `paper_notes.md`
- new EvidenceSpan records where extraction finds quote locators
- claim ledger entries
- optional `deep_reading_llm.md` and transcripts in LLM modes

## Required Artifacts
- `papers.json`
- `paper_notes.json`
- `paper_notes.md`
- `evidence_spans.json` when full-text evidence exists

## Procedure
1. State source basis: full text, abstract-only, or metadata-only.
2. Use sections when available: abstract/introduction for claims, method for methods, experiments/results for datasets/metrics/results, discussion/limitations/conclusion for limitations.
3. Extract only present text.
4. Main results require result/evaluation/conclusion evidence or an abstract quote.
5. Methods require method/approach evidence when full text exists.
6. Limitations require direct limitation/discussion/conclusion evidence or must be labeled inferred.
7. Add claim ledger entries only with paper IDs and evidence.
8. If using LLM mode, validate JSON and drop unsupported locators.
9. Store public reasoning summaries only.

## Citation and Evidence Rules
- No invented citations, quotes, datasets, equations, benchmarks, or results.
- Full-text claims should cite EvidenceSpan locators.
- Abstract-only notes cannot become high confidence.
- Model output without valid locators must be downgraded or dropped.

## Uncertainty Rules
- Missing sections should be recorded.
- Unstated limitations are uncertain.
- If evidence is abstract-only, confidence is low or medium.

## Validation Checklist
- [ ] Every note has `paper_id`.
- [ ] Source basis is explicit.
- [ ] Results have evidence.
- [ ] Claims have paper IDs and locators where available.
- [ ] Missing sections are visible.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Turning author claims into demonstrated results.
- Inferring datasets/metrics from title alone.
- Dropping locators.
- Trusting malformed LLM JSON.

## Examples
```bash
gapforge read --run-id RUN_ID --tier 1
gapforge read --run-id RUN_ID --paper-id PAPER_ID --fulltext-only
GAPFORGE_LLM_MODE=prompt-pack gapforge read-llm --run-id RUN_ID --tier 1 --dry-run-prompts
```
