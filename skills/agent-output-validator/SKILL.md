---
name: agent-output-validator
description: Use when validating, importing, repairing, or rolling back GapForge agent or campaign output patches.
---

# Agent Output Validator

## Purpose
Keep model or agent output from corrupting research state. Validation is the only path from Codex/GPT-5.4 output to persistent campaign state.

## When To Use
- Before `campaign-import-output`.
- After a Codex task writes JSON outputs.
- When validation fails and repair/rollback is needed.

## Inputs
- Task pack, expected schemas, output files, campaign state, project corpus, known paper IDs, known EvidenceSpan IDs/locators, source coverage, and prior import records.

## Outputs
- `CampaignImportRecord`, `validation.json`, accepted/rejected object lists, rollback snapshots, repair task packs.

## Artifacts
- `validation.json`
- `imports.json`
- rollback snapshot under campaign state
- `repair-agent-output` task pack or handoff

## Procedure
1. Parse every expected JSON output.
2. Validate required top-level keys and required fields.
3. Check every paper ID, prior-work ID, task ID, step ID, and evidence locator.
4. Reject fake citations and unknown DOI/arXiv claims unless they are search requests.
5. Reject high-confidence unsupported claims.
6. Reject strong novelty without closest prior work and coverage gates.
7. Apply only accepted patches, record rejected fields, and keep rollback available.

## Validation Checklist
- [ ] JSON parses.
- [ ] Required files and keys exist.
- [ ] IDs resolve to current run/project/campaign state.
- [ ] Supported claims have evidence.
- [ ] Novelty claims have closest prior work or unknown verdict.
- [ ] Rollback snapshot exists before mutation.

## Failure Modes
- Silently dropping bad fields.
- Accepting citations not in corpus.
- Treating attestation as validation.
- Importing partial output without recording rejected fields.

## Examples
```bash
gapforge campaign-validate-output --campaign-id CAMPAIGN --task-id TASK
gapforge campaign-import-output --campaign-id CAMPAIGN --task-id TASK
gapforge repair-agent-output --task-id TASK --path outputs/novelty_dossiers_patch.json --handoff
gapforge rollback-import --import-id IMPORT
```

## Evidence Rules
Evidence locators must resolve. Unknown citations are not evidence. A model statement is not support unless it cites accepted evidence. Do not invent citations, results, papers, evidence locators, DOI/arXiv IDs, datasets, metrics, or source metadata.

## Uncertainty Rules
Invalid evidence should downgrade or reject claims, not be ignored.

## Reasoning Storage
Store validation issues and concise public summaries. Do not store hidden chain-of-thought.

## Fake vs Real Agent Modes
Fake output can be validated to test the pipeline but never counts as actual-run acceptance. Real output still needs validation, import, attestation, and human review.
