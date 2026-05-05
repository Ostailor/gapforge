---
name: codex-campaign-task
description: Use when preparing, executing, or inspecting GapForge v0.4 Codex/GPT-5.4 campaign task packs.
---

# Codex Campaign Task

## Purpose
Give Codex/GPT-5.4 a bounded campaign task with exact inputs, output filenames, JSON schemas, evidence rules, and validation expectations.

## When To Use
- Use for `gapforge campaign-task`, `task-handoff`, `codex-run`, and campaign task-pack review.
- Use before asking Codex/GPT-5.4 to read, synthesize gaps, review novelty, design experiments, or decide stop conditions.

## Inputs
- Campaign context, compact retrieval-selected task context, allowed paper IDs, evidence span IDs/locators, source coverage, existing gaps/dossiers/directions, and expected output schema.

## Outputs
- Task pack files and Codex-produced JSON patches under `outputs/`.

## Artifacts
- `CAMPAIGN_TASK.md`
- `HANDOFF.md`
- `task_context.json`
- `expected_outputs.json`
- `schema_examples.json`
- `validation_rules.md`
- `evidence_rules.md`
- `outputs/*.json`

## Procedure
1. Create a task pack with `gapforge campaign-task --campaign-id ID --type TASK_TYPE`.
2. Inspect `task_context.json` and `expected_outputs.json`.
3. In handoff mode, give Codex/GPT-5.4 `HANDOFF.md` and the task pack path.
4. Codex writes only expected files into `outputs/`.
5. Validate before import.
6. Repair invalid outputs instead of weakening validation.

## Validation Checklist
- [ ] Task type is one of the supported campaign task types.
- [ ] Expected output filenames are clear.
- [ ] Context includes allowed IDs and missing coverage.
- [ ] Output JSON uses required top-level keys.
- [ ] No citations outside known corpus unless represented as search requests.

## Failure Modes
- Dumping too much context and hiding important IDs.
- Writing Markdown instead of required JSON.
- Inventing citations, datasets, quotes, or results.
- Treating prompt-pack creation as completed Codex research.

## Examples
```bash
gapforge campaign-task --campaign-id CAMPAIGN --type novelty_reviewer
gapforge task-handoff --task-id TASK
gapforge campaign-validate-output --campaign-id CAMPAIGN --task-id TASK
```

## Evidence Rules
Use only known paper IDs and EvidenceSpan locators. Unknown prior work should become `missing_searches` or search requests. Do not invent DOI/arXiv IDs.

## Uncertainty Rules
Mark weak coverage, missing searches, invalid locators, and unresolved novelty as unknown or not ready.

## Reasoning Storage
Include concise public reasoning summaries only. Do not ask for or store hidden chain-of-thought.

## Fake vs Real Agent Modes
Fake task outputs are regression fixtures. Real task-pack/manual-handoff outputs require Codex/GPT-5.4 execution, validated import, attestation, and human review before acceptance.
