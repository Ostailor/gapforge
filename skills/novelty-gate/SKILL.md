---
name: novelty-gate
description: Use when checking gaps, hypotheses, or directions against closest prior work before novelty claims, experiments, or manuscript export.
---

# Novelty Gate

## Purpose
Try to kill the idea by finding closest prior work. The novelty gate is stricter than gap mining and must preserve missing searches.

## When To Use
- After gap mining and related/citation expansion.
- Before experiment design, direction maturation, or manuscript export.
- CLI: `gapforge novelty-check --run-id RUN_ID --deep`, `gapforge novelty-check-llm --run-id RUN_ID --all --fake`.

## Inputs
- gaps or hypotheses
- paper store and paper notes
- field map
- citation graph
- retrieval candidates
- source coverage and policy assessment
- project memory

## Outputs
- `NoveltyAssessment`
- `NoveltyDossier`
- `novelty_gate.json`
- `novelty_gate.md`
- `novelty_dossiers.json`
- `novelty_dossiers.md`
- updated gap novelty status
- rejected ideas

## Required Artifacts
- `gaps.json`
- `papers.json`
- `novelty_gate.json`
- `novelty_dossiers.json`
- `rejected_ideas.json`

## Procedure
1. Generate exact phrase, method/metric, benchmark/dataset, failure-mode, limitation, adjacent-field, and citation-neighborhood queries.
2. Search existing run/project memory first.
3. Use retrieval and citation graph candidates when available.
4. Compare problem, method, dataset, metric, contribution, limitation, and evaluation overlap.
5. Record closest prior work, what is new, what is not new, decisive difference, reviewer objection, missing searches, and verdict.
6. Reject duplicates, revise near misses, pursue only when coverage supports it, and use unknown when coverage is weak.
7. In LLM mode, refine only from known paper IDs and recorded search results.

## Citation and Evidence Rules
- No novelty claim without closest prior work or explicit missing-search reason.
- Strong novelty requires adequate source policy coverage, retrieval/citation expansion, closest prior work, and no blocking missing searches.
- Model-generated prior work must resolve to known paper IDs.
- Do not invent DOI/arXiv IDs or paper claims.

## Uncertainty Rules
- Poor coverage forces unknown or weak novelty.
- Deterministic/LLM disagreement should become contested unless evidence resolves it.
- Absence from current run is not novelty.

## Validation Checklist
- [ ] Every dossier lists candidates considered and closest prior work or missing searches.
- [ ] Duplicate ideas are rejected.
- [ ] Strong novelty has prior work and coverage support.
- [ ] Rejected ideas are preserved.
- [ ] No hidden chain-of-thought is stored.

## Failure Modes
- Treating lexical difference as novelty.
- Ignoring project-memory rejected ideas.
- Allowing LLMs to invent prior work.
- Hiding missing searches.

## Examples
```bash
gapforge novelty-check --run-id RUN_ID --deep
gapforge novelty-dossier --run-id RUN_ID --gap-id GAP_ID
GAPFORGE_LLM_MODE=fake gapforge novelty-check-llm --run-id RUN_ID --all --fake
```
