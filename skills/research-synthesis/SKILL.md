---
name: research-synthesis
description: Use when asking Codex/GPT-5.4 or deterministic GapForge workflows to synthesize v0.5 real-literature research directions from validated search, evidence, and prior-work artifacts.
---

# Research Synthesis

## Purpose
Synthesize at most a small number of evidence-backed research directions after live source, search, retrieval, and prior-work gates have run.

## Inputs
- Topic, source profile, live source diagnostic, search rounds, top papers, evidence spans, gap evidence matrices, closest prior work, counterevidence, rejected ideas, human constraints.

## Outputs
- `research_directions_patch.json`
- `gap_evidence_matrices_patch.json`
- `novelty_dossiers_patch.json`
- `related_work_matrix_patch.json`
- `uncertainty_register.json`
- `search_requests.json`

## Required Artifacts
- source coverage report
- search strategy and completed search rounds
- retrieval index or explicit context-limited note
- prior-work recall assessment
- validated Codex task output when agent-backed

## Procedure
1. Confirm live/source and prior-work gates have run.
2. Review evidence spans and paper IDs before proposing directions.
3. Propose no more than three directions.
4. For each direction, list supporting evidence, counterevidence, closest prior work, why it may fail, and missing searches.
5. Mark novelty unknown unless recall gate and closest-prior-work dossier support stronger language.
6. Produce JSON patches only for required files.
7. Let GapForge validation reject unsupported or fake-citation content.

## Evidence/Citation Rules
- Every direction must cite known paper IDs.
- Full-text-backed claims should cite EvidenceSpan locators.
- Unknown citations become search requests.
- Do not invent citations, quotes, datasets, metrics, baselines, results, or completed experiments.

## Source Coverage Rules
- Do not synthesize positive recommendations under poor live coverage unless explicitly framed as not ready.
- Missing prior-work rounds block strong novelty.
- Fallback/fixture-heavy campaigns must be labeled and should not claim live-literature quality.

## Failure Modes
- Free-form brainstorming before evidence gathering.
- Too many directions with shallow evidence.
- Treating adjacent-field analogy as proof.
- Omitting counterevidence or closest prior work.
- Writing markdown when JSON patches are required.

## Validation Checklist
- [ ] Source coverage and search rounds are present.
- [ ] Prior-work recall gate exists.
- [ ] Direction count is at most three.
- [ ] All paper IDs and evidence locators resolve.
- [ ] Strong novelty is blocked unless gates pass.
- [ ] Missing searches are listed.

## Examples
```bash
gapforge research-synthesis-task --campaign-id <campaign-id>
gapforge codex-handoff --task-id <task-id> --print-prompt
gapforge validate-import-all --task-id <task-id>
```

## Uncertainty Rules
When evidence is insufficient, recommend refusal, revision, or more search. Do not turn uncertainty into a research claim.

## Reasoning Storage
Store public reasoning summaries only. Do not request or store hidden chain-of-thought.
