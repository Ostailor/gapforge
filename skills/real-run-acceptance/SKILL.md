---
name: real-run-acceptance
description: Use when determining whether GapForge Codex/GPT-5.4 campaign output can count as actual-run acceptance.
---

# Real-Run Acceptance

## Purpose
Decide whether v0.4 may honestly claim actual Codex/GPT-5.4 campaign acceptance. The gate must fail closed when artifacts are missing or ambiguous.

## When To Use
- Before release notes claim actual-run acceptance.
- After real campaign canaries finish.
- When reviewing fake-agent, task-pack, handoff, or direct runs.

## Inputs
- Campaign records, imports, attestations, source coverage, retrieval index, novelty dossiers, campaign reports, stop reasons, and human reviews.

## Outputs
- Campaign acceptance summary and v4 release-gate report.

## Artifacts
- `campaign_acceptance_summary.json`
- `campaign_review.md`
- `docs/releases/v0.4.0-real-run-acceptance.md`
- `data/release_gate/v0.4_latest.json`

## Procedure
1. Confirm deterministic CI and fake-agent regression passed.
2. Count only campaigns in real modes: `codex_task_pack`, `codex_direct`, or `manual_handoff`.
3. Require validated imports and attestation for task-pack/handoff outputs.
4. Require source coverage, retrieval index, novelty dossier or refusal reason, campaign report, explicit stop reason, and human acceptance.
5. Reject any campaign with fake citations, unsupported high-confidence claims, strong novelty without prior work, or strict-report overclaim.
6. Require at least three accepted real campaigns, including experiment-ready, refusal, and full-text/manual-PDF coverage.

## Validation Checklist
- [ ] Fake-agent campaigns are excluded.
- [ ] Prompt-pack-only tasks are excluded.
- [ ] Every accepted campaign has human review.
- [ ] Every accepted campaign has explicit stop reason.
- [ ] Release gate output is written and auditable.

## Failure Modes
- Counting fake-agent canaries as real.
- Counting handoff without attestation.
- Accepting a campaign that completed but was not reviewed.
- Hiding source coverage weakness.

## Examples
```bash
gapforge campaign-review --campaign-id CAMPAIGN --accept --reviewer "<name>"
gapforge campaign-acceptance --campaign-id CAMPAIGN
gapforge v4-release-gate --project-id PROJECT --write-report --json
```

## Evidence Rules
Acceptance is based on artifacts, validation, and review records, not model confidence or command exit code. Do not invent citations, results, campaign IDs, agent outputs, or acceptance evidence.

## Uncertainty Rules
If any required artifact is missing, mark actual-run acceptance not completed. Never infer a pass.

## Reasoning Storage
Store public acceptance reasons, blockers, and residual risks only. Do not store hidden chain-of-thought.

## Fake vs Real Agent Modes
Fake is never real. Task-pack/manual-handoff can be real only after Codex/GPT-5.4 output is validated, imported, attested, and reviewed. Direct can be real only with configured execution records plus validation and review.
