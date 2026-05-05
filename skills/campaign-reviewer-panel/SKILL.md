---
name: campaign-reviewer-panel
description: Use when simulating or reviewing conference-style objections for a GapForge campaign direction or experiment protocol.
---

# Campaign Reviewer Panel

## Purpose
Attack a direction, protocol, or paper package like serious reviewers and turn blocking issues into campaign decisions or review queue items.

## When To Use
- After related-work matrix and experiment protocol exist.
- Before manuscript-ready maturity or paper package export.
- When reviewer fatal flaws need rebuttal/fix tasks.

## Inputs
- Direction, novelty dossier, related-work matrix, experiment protocol, claim graph, evidence spans, source coverage, and prior reviewer objections.

## Outputs
- Review panel, rebuttal plan, required fixes, review queue items, maturity downgrade when needed.

## Artifacts
- `review_panel_patch.json`
- `rebuttal_plan_patch.json`
- `required_fixes.json`
- `review_queue.md`
- campaign decisions

## Procedure
1. Review technical correctness, novelty, empirical rigor, theory/clarity, ethics, and area-chair positioning.
2. Cite protocol gaps or prior work for each serious objection.
3. Flag missing baselines, unsupported novelty, weak metrics, poor coverage, and reproducibility gaps.
4. Convert fatal issues into required fixes or human review requests.
5. Do not invent new results for rebuttals.

## Validation Checklist
- [ ] Fatal novelty or baseline issues block readiness.
- [ ] Objections cite evidence, prior work, or protocol gaps.
- [ ] Rebuttal asks for citations, experiments, or softened claims.
- [ ] Required fixes become campaign decisions or review queue items.
- [ ] No fake results appear.

## Failure Modes
- Generic feedback without evidence.
- Rebuttal invents experiments or outcomes.
- Fatal issues do not affect maturity.
- Reviewer output uses fake citations.

## Examples
```bash
gapforge reviewer-loop --campaign-id CAMPAIGN --direction-id DIRECTION
gapforge rebuttal-tasks --campaign-id CAMPAIGN --direction-id DIRECTION
gapforge apply-reviewer-fixes --campaign-id CAMPAIGN --direction-id DIRECTION
```

## Evidence Rules
Reviewer claims must cite known paper IDs, evidence locators, related-work entries, or protocol fields. Do not invent citations, paper IDs, results, experiments, or prior-work claims.

## Uncertainty Rules
If the reviewer cannot verify novelty or baseline adequacy, mark it as a blocking uncertainty.

## Reasoning Storage
Store public review summaries and concrete fixes only. Do not store hidden chain-of-thought.

## Fake vs Real Agent Modes
Fake reviewer panels test gates. Real Codex/GPT-5.4 reviewer output requires validated import, attestation when counted as actual, and human review.
