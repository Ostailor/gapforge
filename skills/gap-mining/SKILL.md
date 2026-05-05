---
name: gap-mining
description: Use when identifying evidence-backed research gaps from field maps, paper notes, limitations, contradictions, missing benchmarks, or repeated assumptions.
---

# Gap Mining

## Purpose
Identify real research gaps supported by patterns in the literature. This skill should not generate random ideas; it should surface gaps that can be traced to papers, notes, claims, contradictions, or explicit indirect evidence.

## When To Use
- Use after literature mapping and deep reading.
- Use before analogy generation, novelty checking, and experiment design.
- CLI: `gapforge mine-gaps --run-id RUN_ID`.

## Inputs
- `FieldMap`
- `PaperNote` records
- claim ledger
- research topic

## Outputs
- `Gap` records
- `gaps.json`
- `gaps.md`
- uncertainty-aware gap claims in the claim ledger

## Required Artifacts
- `paper_notes.json`
- `field_map.json`
- `claims.json`
- `gaps.json`
- `gaps.md`

## Procedure
1. Look for repeated limitations across notes.
2. Identify missing or inconsistent metrics.
3. Identify absent, synthetic-only, or underspecified datasets.
4. Find assumptions repeated by multiple papers.
5. Convert field-map contradictions into theory or evaluation gaps.
6. Note deployment, reproducibility, scalability, negative-result, and measurement gaps when supported.
7. Link every gap to supporting paper IDs or explain why evidence is indirect.
8. Add `risk_that_gap_is_fake` for every gap.
9. Leave `novelty_status` as unchecked, weak, or provisional until the novelty gate runs.

## Quality Bar
- A gap must explain why existing work does not solve it.
- No high-confidence gap without supporting papers or claims.
- Do not claim novelty here; novelty belongs to the novelty gate.
- Do not hallucinate citations, results, datasets, or missing-work claims.
- Use the claim ledger for nontrivial gap statements.
- Mark uncertainty explicitly.

## Failure Modes
- Generating vague "more research is needed" ideas.
- Calling a gap real because one abstract omitted details.
- Ignoring counterevidence or closest prior work.
- Forgetting the risk that the gap is fake.

## Validation Checklist
- [ ] `gaps.json` and `gaps.md` exist.
- [ ] Each gap has a type, description, support, and fake-gap risk.
- [ ] Each gap links papers/claims or gives an explicit indirect-evidence reason.
- [ ] No gap is marked high confidence without support.
- [ ] No unsupported novelty claim is made.

## Examples
Mine gaps for an existing run:

```bash
gapforge mine-gaps --run-id 20260505T002206Z-low-false-positive-collusion-detection
```
