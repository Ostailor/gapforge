---
name: real-literature-review
description: Use when reviewing GapForge v0.5 live-literature campaign outputs for research quality, separate from workflow acceptance.
---

# Real Literature Review

## Purpose
Evaluate whether a live-literature campaign is actually research-useful and honest, not merely whether commands and Codex handoffs completed.

## Inputs
- Campaign report, live source diagnostic, search strategy/rounds, source coverage, canonicalization report, prior-work recall, novelty dossiers, related-work matrix, experiment protocol, reviewer panel, human review queue.

## Outputs
- `RealLiteratureHumanReview`
- `real_literature_reviews.json`
- `real_literature_acceptance.json`
- release-quality blockers and required fixes

## Required Artifacts
- `real_literature_review.md`
- `real_literature_acceptance.md`
- `real_literature_campaign_report.md`
- `v0.5` release-gate report when applicable

## Procedure
1. Check source quality and paper relevance.
2. Check closest-prior-work recall and missing searches.
3. Verify evidence grounding and citation resolution.
4. Review novelty honesty and gap importance.
5. Review experiment feasibility, baselines, metrics, falsification, and reproducibility.
6. Confirm uncertainty and fallback/fixture counts are visible.
7. Accept for workflow only when mechanics ran.
8. Accept for research quality only when the campaign is useful and not misleading.

## Evidence/Citation Rules
- Fake citations block acceptance.
- Unsupported high-confidence claims block acceptance.
- Expected results must be hypothetical.
- Do not invent citations, results, reviewer findings, or acceptance evidence.

## Source Coverage Rules
- Poor coverage must lead to refusal or required fixes.
- Missed obvious prior work blocks research-quality acceptance.
- Workflow-accepted but quality-rejected campaigns must be labeled.

## Failure Modes
- Accepting a polished report that hides weak search.
- Treating Codex confidence as expert review.
- Ignoring strict-report overclaim.
- Accepting an experiment without baselines or falsification.

## Validation Checklist
- [ ] Workflow acceptance and quality acceptance are separate.
- [ ] Fake citation and unsupported-claim flags are checked.
- [ ] Missed prior work and overclaimed novelty are checked.
- [ ] Required fixes are recorded.
- [ ] v5 release gate cannot pass from workflow-only acceptance.

## Examples
```bash
gapforge real-literature-review --campaign-id <campaign-id>
gapforge real-literature-review --campaign-id <campaign-id> --accept-quality --reviewer "<expert>"
gapforge real-literature-acceptance --campaign-id <campaign-id>
gapforge v5-release-gate --project-id <project-id> --write-report
```

## Uncertainty Rules
Reject or require fixes when uncertainty is hidden. A correct refusal can be quality-accepted.

## Reasoning Storage
Store public reasons, scores, required fixes, and notes only. Do not store hidden chain-of-thought.
