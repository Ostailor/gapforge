---
name: paper-triage
description: Use when deciding which research papers deserve deep reading, method/results reading, skimming, or metadata-only treatment.
---

# Paper Triage

## Purpose
Rank papers into reading tiers so GapForge spends deep-reading effort where it matters. Triage is prioritization metadata, not a factual claim about paper quality.

## When To Use
- Use after search and literature mapping.
- Use when many papers exist and not all should be read equally.
- CLI: `gapforge triage --run-id RUN_ID` or `gapforge triage "topic" --max-tier1 20`.

## Inputs
- `ResearchTopic`
- normalized `Paper` records
- optional `FieldMap`
- venue, year, citation count, title, abstract, source, keywords

## Outputs
- `PaperTriageResult`
- `PaperTriageDecision` records
- `paper_triage.json`
- `paper_triage.md`
- abstract-only preliminary notes for Tier 1 and Tier 2 papers
- at most a small number of claim ledger entries about the triage set

## Required Artifacts
- `papers.json`
- `paper_triage.json`
- `paper_triage.md`
- updated `paper_notes.json` only for selected high-priority papers

## Procedure
1. Score papers for topic relevance, directness, recency, venue authority, citation signal, benchmark signal, method novelty, limitation/open-problem signal, and source diversity.
2. Assign tiers:
   - Tier 1: must read deeply
   - Tier 2: read method/results/limitations
   - Tier 3: skim related work
   - Tier 4: metadata only
3. Enforce diversity so one source or venue does not dominate when comparable papers exist.
4. Record reasons and concerns for each decision.
5. Create preliminary abstract-only notes only for selected papers.
6. Add ledger claims only for actual claims, such as the composition of the Tier 1 reading set, not every score.

## Quality Bar
- Directly relevant recent papers should outrank weakly related old papers.
- Low-citation papers should not be excluded automatically.
- Metadata gaps must be listed as concerns, not silently ignored.
- Do not invent results or citations from a score.

## Failure Modes
- Popularity bias from citation counts.
- Source monoculture in Tier 1.
- Treating a scoring decision as a research finding.
- Promoting abstract-only notes to high confidence.

## Validation Checklist
- [ ] `paper_triage.json` and `paper_triage.md` exist.
- [ ] Every decision has tier, score, reasons, concerns, and recommended reading depth.
- [ ] Tier 1 includes source or venue diversity when possible.
- [ ] Abstract-only notes are labeled as abstract-only.
- [ ] No invented claims or citations appear.

## Examples
Triage an existing run:

```bash
gapforge triage --run-id 20260505T002206Z-low-false-positive-collusion-detection
```

Limit Tier 1 size:

```bash
gapforge triage "low false positive collusion detection" --max-tier1 12
```
