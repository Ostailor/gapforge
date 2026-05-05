# Real-Run Review Checklist

Use this checklist for Level 5 human-reviewed acceptance of v0.3 canary runs.

## Run Identity

- [ ] Run ID recorded.
- [ ] Project ID recorded if used.
- [ ] Topic recorded.
- [ ] Commands or workflow notes saved.
- [ ] Codex/GPT-5.4 availability recorded.
- [ ] Reviewer name/date recorded.

## Source Coverage

- [ ] `source_coverage.md` inspected.
- [ ] `coverage_stopping_assessment.md` inspected.
- [ ] Search queries and failed sources are visible.
- [ ] Offline/fallback data is labeled.
- [ ] Missing source families are not hidden.

## Full Text and Evidence

- [ ] `full_text_coverage.md` inspected.
- [ ] Local PDF artifacts are allowed for use.
- [ ] Parsed sections or parser warnings are visible.
- [ ] Full-text claims cite EvidenceSpan locators.
- [ ] Abstract-only claims are not high confidence.

## Claim Ledger

- [ ] No supported claim lacks evidence.
- [ ] No high-confidence claim lacks adequate support.
- [ ] Counterevidence is represented where found.
- [ ] Uncertain claims are labeled.
- [ ] No hidden chain-of-thought appears in persisted artifacts.

## Novelty Dossiers

- [ ] Every recommended gap/direction has a novelty dossier.
- [ ] Closest prior work is listed, or novelty is marked unknown.
- [ ] Missing searches are visible.
- [ ] No fake citations or fake prior work.
- [ ] Strong novelty is not claimed under poor coverage.

## LLM-Assisted Outputs

- [ ] Codex/GPT-5.4 outputs are schema-valid or manually normalized with audit notes.
- [ ] Unsupported model claims were rejected, downgraded, or marked uncertain.
- [ ] Model outputs cite paper IDs and locators where source-backed.
- [ ] Model transcripts/prompts do not expose secrets.
- [ ] Fake LLM output is not counted as real canary validation.

## Report and Recommendations

- [ ] Strict report inspected.
- [ ] Report distinguishes evidence-backed claims, hypotheses, and unsupported claims.
- [ ] Report does not claim exhaustive literature review.
- [ ] If coverage is poor, report recommends next search/review steps instead of a paper-ready direction.
- [ ] Rejected ideas are visible.

## Human Review Record

- [ ] Human review was recorded with `approve`, `reject`, `annotate`, or review queue completion.
- [ ] Any acceptance waiver is explicit and scoped.
- [ ] Blocking issues are recorded.
- [ ] Artifact audit was run before sharing.

## Decision

- [ ] Pass.
- [ ] Pass with limitations.
- [ ] Fail.

## Current Review Outcome

May 5, 2026 verification outcome:

- Fake-agent canary: passed as CI-safe fake-agent validation.
- `low_fpr_collusion_codex`: failed/not passed because actual Codex/GPT-5.4 real-run environment was not configured.
- `manual_pdf_fulltext_codex`: failed/not passed because actual Codex/GPT-5.4 real-run environment was not configured.
- Real-run acceptance: not passed.

Do not mark Level 5 accepted until an actual Codex/GPT-5.4 canary completes, outputs are inspected against this checklist, and the canary is explicitly accepted.

Notes:

```text
Reviewer:
Date:
Decision:
Blocking issues:
Required fixes:
Residual risks:
```
