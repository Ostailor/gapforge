# v0.5 Real Literature Campaigns

v0.5 real literature campaigns are multi-step investigations over live source results and real paper metadata. They are different from v0.4.1 workflow canaries, which only prove that Codex task execution and validated import work.

## Campaign Definition

A v0.5 real literature campaign must:

1. Start from a concrete research topic and source policy profile.
2. Execute live source searches unless explicitly unavailable.
3. Record every query and source failure.
4. Triage papers across source and role diversity.
5. Retrieve or parse full text when legally and technically available.
6. Build a retrieval index over papers, sections, evidence spans, claims, and memory.
7. Run Codex/GPT-5.4 or deterministic reading with evidence-located outputs.
8. Mine gaps with evidence matrices and counterevidence search.
9. Run iterative novelty re-search until novelty is accepted, rejected, or unknown with a clear stop reason.
10. Produce a related-work matrix and experiment protocol for any recommended direction.
11. Undergo human expert review.

## Dry-Run First

Before running a broad campaign, preview it:

```bash
gapforge real-campaign-dry-run --profile live_low_fpr_collusion --write-report
gapforge real-campaign-dry-run --topic "lexical substitution attacks against LLM monitors" --source-profile ai_safety
```

The dry run should show expected source checks, planned search rounds, Codex tasks, artifact count, estimated budget, likely blockers, command sequence, and acceptance requirements. It is planning-only and does not count as live-literature validation.

## Required Campaign Profiles

v0.5 should define live profiles for:

- low false positive collusion detection in LLM agents
- lexical substitution attacks on LLM monitors
- medical screening specificity transfer for AI safety false-positive control
- cartel detection economics as an adjacent-field comparison
- intentionally undercovered topic that should refuse recommendation

Profiles may be skipped only when source access is unavailable, and that skip must be recorded as not-run, not passed.

## Current Status

The May 6, 2026 verification pass ran live-literature campaigns and the v5 release gate passed. The accepted campaigns were:

- `campaign-20260506T031950Z-low-false-positive-collusion-detection-in-llm-agents`: experiment-ready campaign accepted for research quality with live source diagnostics, search rounds, canonicalization, retrieval index, prior-work recall, novelty dossier, related-work matrix, experiment protocol, explicit stop reason, and human review.
- `campaign-20260506T031746Z-low-false-positive-collusion-detection-in-llm-agents`: conservative refusal campaign accepted for research quality because prior-work/coverage risk remained too high.

The same pass also created live-literature records for `live_llm_monitor_evasion` and `live_undercovered_refusal`. Those records help satisfy the campaign-count requirement, but the accepted quality evidence comes from the two campaigns above.

This is a local release-gate acceptance result, not a claim of exhaustive literature review. Several live source results were noisy or abstract-only, and the human review notes record those limitations.

## Campaign Outputs

Each campaign should produce:

- `campaign_report.md`
- `source_coverage.md`
- `full_text_coverage.md`
- `search_queries.json`
- `paper_ranking.md`
- `paper_notes.md`
- `gap_evidence_matrix.md`
- `novelty_dossiers.md`
- `related_work_matrix.md`
- `experiment_protocol.md` or a refusal reason
- `review_panel.md`
- human review record
- release-quality summary

## Scripted Workflow

Notebooks and future UI layers should call the Python API:

```python
from gapforge import api

api.source_health("low false positive collusion", profile="ai_safety")
api.plan_search_strategy("low false positive collusion", "ai_safety")
record = api.run_real_literature_campaign("live_low_fpr_collusion")
api.real_literature_status(record.id)
api.v5_release_gate(project_id=record.project_id)
```

The API is a thin wrapper over the same managers used by the CLI and accepts mocked sources for offline tests.

## Human Review Questions

Reviewers should answer:

- Did the campaign search the right source families for the field?
- Did it find the obvious closest prior work?
- Did it distinguish abstract-only and full-text evidence?
- Did every high-confidence claim have evidence?
- Did the related-work matrix classify important papers correctly?
- Did the novelty dossier fairly compare the proposed direction to prior work?
- Did the experiment protocol include baselines, metrics, falsification, and reproducibility details?
- Did the campaign reject or downgrade weak ideas?
- Did the report visibly state uncertainty and missing searches?

## Pass/Fail

A campaign can pass as:

- **accepted-ready**: recommends a direction with adequate coverage, prior work, evidence, protocol, and review.
- **accepted-refusal**: correctly refuses to recommend because coverage, novelty, or evidence is insufficient.

A campaign fails if it looks polished but hides weak search, missed prior work, fake citations, unsupported claims, or speculative results.
