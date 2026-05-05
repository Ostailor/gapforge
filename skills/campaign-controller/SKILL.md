---
name: campaign-controller
description: Use when running, resuming, inspecting, or debugging GapForge v0.4 research campaigns and their campaign decisions.
---

# Campaign Controller

## Purpose
Coordinate a v0.4 campaign as an auditable research loop. The controller chooses whether to search, parse, build retrieval, ask Codex, import outputs, request human review, design experiments, export packages, or stop.

## When To Use
- Use for `gapforge campaign-run`, `campaign-next`, `campaign-resume`, and `campaign-report`.
- Use when deciding why a campaign paused, failed, or stopped.
- Do not use for one-off run-local v0.1/v0.2/v0.3 commands unless the run is attached to a v0.4 campaign.

## Inputs
- Campaign state, project memory, attached runs, source coverage, retrieval manifest, gaps, novelty dossiers, directions, review queue, and budget.

## Outputs
- `CampaignDecision`, `CampaignStep`, `CampaignMilestone`, `CampaignStopCondition`, and `campaign_report.md`.

## Artifacts
- `projects/<project>/campaigns/<campaign>/campaign.json`
- `steps.json`, `decisions.json`, `milestones.json`, `stop_conditions.json`
- `campaign_report.md`

## Procedure
1. Load campaign, project, and attached runs.
2. Assess coverage, retrieval, reading coverage, gaps, novelty, direction maturity, review queue, and budget.
3. Record one decision with reason, evidence, expected value, and cost estimate.
4. Execute deterministic steps directly or create a Codex task pack.
5. Pause on manual handoff, invalid agent output, or human review requirements.
6. Stop only with an explicit stop reason.

## Validation Checklist
- [ ] Every decision has reason and evidence.
- [ ] Budget and iteration limits are respected.
- [ ] Fake-agent, task-pack, direct, and manual-handoff modes are labeled.
- [ ] Campaign report shows stop reason and uncertainty.
- [ ] No unvalidated agent output mutates state.

## Failure Modes
- Infinite search/read loops without budget checks.
- Treating task-pack creation as completed Codex work.
- Recommending a direction under poor coverage.
- Losing failed-step evidence during resume.

## Examples
```bash
gapforge campaign-next --campaign-id CAMPAIGN
gapforge campaign-run --campaign-id CAMPAIGN --mode deterministic --max-iterations 3
gapforge campaign-run --campaign-id CAMPAIGN --mode codex_task_pack
gapforge campaign-report --campaign-id CAMPAIGN
```

## Evidence Rules
Campaign decisions should cite artifacts, paper IDs, evidence locators, validation IDs, or source coverage warnings. Do not invent citations, papers, or results.

## Uncertainty Rules
If coverage, novelty, or validation is incomplete, pause, request review, or stop as not ready. Do not soften unknown novelty into pursue.

## Reasoning Storage
Store only concise public reasoning summaries. Do not store hidden chain-of-thought.

## Fake vs Real Agent Modes
Fake-agent mode validates plumbing and never counts as actual-run acceptance. Task-pack/manual-handoff can count only after real Codex/GPT-5.4 outputs are imported, validated, attested, and human-reviewed. Direct mode counts only when configured, executed, validated, and reviewed.
