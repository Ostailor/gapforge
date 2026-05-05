---
name: gap-mining
description: Use when identifying evidence-backed research gaps from paper notes, evidence spans, field maps, contradictions, missing metrics, or repeated limitations.
---

# Gap Mining

## Purpose
Find real gap candidates supported by patterns in papers and notes. Gap mining should not generate random ideas or novelty claims.

## When To Use
- After literature mapping and deep reading.
- Before novelty gate, experiment design, and direction maturation.
- CLI: `gapforge mine-gaps --run-id RUN_ID`, `gapforge mine-gaps-llm --run-id RUN_ID --fake`.

## Inputs
- `FieldMap`
- `PaperNote`
- `PaperSection`
- `EvidenceSpan`
- `ClaimLedger`
- `SourceCoverageReport`
- retrieval index when available
- project memory context when attached

## Outputs
- `Gap`
- `gaps.json`
- `gaps.md`
- `GapEvidenceMatrix`
- `gap_evidence_matrix.json`
- `gap_evidence_matrix.md`
- claim ledger entries

## Required Artifacts
- `paper_notes.json`
- `claims.json`
- `gaps.json`
- `gap_evidence_matrix.json`
- `gaps.md`

## Procedure
1. Search notes/spans for repeated stated limitations, missing metrics, missing datasets, unrealistic assumptions, benchmark absence, evaluation mismatch, reproducibility issues, theory gaps, deployment gaps, negative-result gaps, and contradictions.
2. Retrieve counterevidence for each candidate when an index exists.
3. Build a GapEvidenceMatrix with supporting, countering, and contextual rows.
4. Include why existing work does not solve the gap and why it matters.
5. Include minimum experiment and risk that the gap is fake.
6. Keep `novelty_status` unchecked until novelty gate.
7. Reject or downgrade gaps without support.
8. In LLM mode, accept only JSON candidates with locators or explicit abstract-only reasons.

## Citation and Evidence Rules
- Every gap must link papers/evidence or state an explicit indirect-evidence reason.
- High confidence requires multiple supporting papers or strong full-text evidence plus counterevidence search.
- Do not claim novelty.
- Do not invent missing metrics, datasets, or limitations.

## Uncertainty Rules
- Poor source/full-text coverage lowers confidence.
- Abstract-only gaps cannot be high confidence.
- Counterevidence must be represented, not ignored.

## Validation Checklist
- [ ] Each gap has type, support, counterevidence field, fake-gap risk, and minimum experiment.
- [ ] Each gap has an evidence matrix or explicit absence reason.
- [ ] No high-confidence gap lacks supporting evidence.
- [ ] Human-rejected gaps are respected.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Generic "more research needed" gaps.
- Ignoring papers that solve the gap.
- Treating a missing abstract detail as a real gap.
- LLM-specific ideas without evidence.

## Examples
```bash
gapforge mine-gaps --run-id RUN_ID --min-confidence medium
gapforge build-index --run-id RUN_ID
GAPFORGE_LLM_MODE=fake gapforge mine-gaps-llm --run-id RUN_ID --fake
```
