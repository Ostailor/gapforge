---
name: novelty-gate
description: Use when checking candidate gaps, hypotheses, or experiment ideas against closest prior work before claiming novelty or designing paper-ready experiments.
---

# Novelty Gate

## Purpose
Try to kill candidate ideas by finding closest prior work. The novelty gate prevents GapForge from proposing experiments that are already solved, too incremental, or insufficiently searched.

## When To Use
- Use after gap mining and analogy generation.
- Use before experiment design or any novelty claim.
- CLI: `gapforge novelty-check --run-id RUN_ID` or `gapforge novelty-check --gap-id GAP_ID`.

## Inputs
- `Gap` records
- `Hypothesis` records when available
- `PaperNote` records
- `FieldMap`
- existing `Paper` store
- optional source connectors

## Outputs
- `NoveltyAssessment` records
- `novelty_gate.json`
- `novelty_gate.md`
- updated gap `novelty_status`
- `rejected_ideas.json` for duplicates or weak ideas
- source-linked novelty claims when closest prior work exists

## Required Artifacts
- `gaps.json`
- `papers.json`
- `paper_notes.json`
- `novelty_gate.json`
- `novelty_gate.md`
- `rejected_ideas.json`

## Procedure
1. Generate search queries for each target gap or hypothesis.
2. Search existing paper store before using new sources.
3. Identify closest prior work by title, abstract, note content, DOI/arXiv IDs, and lexical/semantic overlap where available.
4. Compare the idea to closest prior work.
5. Record what is new, what is not new, reviewer objection, decisive difference needed, searches used, and missing searches.
6. Verdicts:
   - `reject`: closest prior work appears to cover the idea.
   - `revise`: idea may be incremental or needs sharper differentiation.
   - `pursue`: related prior work exists, but the gap may still be testable.
   - `unknown`: source coverage is insufficient.
7. Never mark strong novelty unless closest prior work is recorded.
8. Add claim ledger entries for novelty claims with prior-work links.

## Quality Bar
- No novelty claim without closest prior work.
- Unknown is preferable to false certainty.
- Missing searches must be explicit.
- Do not hallucinate citations, DOIs, or prior-work results.
- Rejected ideas should be written to `rejected_ideas.json`.

## Failure Modes
- Treating absence from the current run as novelty.
- Using vague prior-work labels instead of paper IDs or citations.
- Marking weak ideas as pursue because they sound promising.
- Forgetting to update gap `novelty_status`.

## Validation Checklist
- [ ] `novelty_gate.json` and `.md` exist.
- [ ] Each assessment has closest prior work or missing searches.
- [ ] Strong novelty has closest prior work.
- [ ] Rejected ideas are recorded.
- [ ] Gap novelty statuses are updated.
- [ ] Novelty ledger claims include closest prior work.

## Examples
Check all gaps:

```bash
gapforge novelty-check --run-id 20260505T002206Z-low-false-positive-collusion-detection
```

Check one gap:

```bash
gapforge novelty-check --run-id 20260505T002206Z-low-false-positive-collusion-detection --gap-id gap-12345
```
