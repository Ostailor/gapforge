---
name: claim-traceability
description: Use when auditing GapForge v0.8 manuscript claims for evidence, citation, result artifact, novelty, limitation, or hypothesis labels.
---

# Claim Traceability

## Purpose
Make every nontrivial manuscript claim auditable before submission packaging.

## Inputs
- Manuscript sections, claim uses, citation keys, evidence locators, result artifact IDs, novelty dossiers, prior-work recall, limitations, and direction blockers.

## Outputs
- `submission/traceability_report.json`
- `submission/traceability_report.md`
- overclaim warnings and softening suggestions.

## Procedure
1. Run `gapforge manuscript-traceability --manuscript-id MANUSCRIPT`.
2. Inspect unsupported claims and blocking issues.
3. Run `gapforge manuscript-overclaims --manuscript-id MANUSCRIPT`.
4. Use `gapforge manuscript-soften-claims --manuscript-id MANUSCRIPT --dry-run` for conservative wording.
5. Link missing claims to known evidence, artifacts, novelty dossiers, or limitations, or label them as hypothesis/speculation.

## Blocking Rules
- No result claim without a result artifact.
- No strong novelty without novelty dossier and prior-work recall.
- No SOTA claim without benchmark comparison and verified leaderboard support.
- Smoke/pilot results cannot be main results.
- Known limitations cannot be omitted.

## Validation Checklist
- [ ] Unsupported claims are listed.
- [ ] Result claims link artifact IDs.
- [ ] Citation gaps are visible.
- [ ] Suggested fixes are actionable.

## Never Do
Do not soften by hiding uncertainty. Do not invent evidence, citations, experiments, or artifact IDs.
