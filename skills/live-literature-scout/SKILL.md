---
name: live-literature-scout
description: Use when checking live source readiness and collecting real-paper evidence for GapForge v0.5 real-literature campaigns.
---

# Live Literature Scout

## Purpose
Assess whether live sources are usable for a topic and start a campaign with auditable source coverage instead of fallback or fixture data.

## Inputs
- Topic, source policy profile, required/recommended sources.
- Existing `SourceCoverageReport`, `SearchQueryRecord`s, source health checks, campaign state, and project memory.

## Outputs
- `SourceHealthCheck`
- `LiveSourceDiagnostic`
- source coverage warnings
- recommended fallback/search actions

## Required Artifacts
- `data/source_health/live_source_diagnostic_latest.json`
- `data/source_health/live_source_diagnostic_latest.md`
- campaign or run `source_coverage.md`

## Procedure
1. Run `gapforge real-campaign-dry-run --profile <profile>` before broad campaigns.
2. Run `gapforge source-health --topic "<topic>"` or `gapforge live-source-diagnostic --topic "<topic>" --source-profile <profile> --write-report`.
3. Check required sources first, then recommended sources.
4. Treat disabled, unavailable, or fallback-only sources as blockers unless the campaign is an explicit refusal campaign.
5. Record every source failure and recommended fallback.

## Evidence/Citation Rules
- Source health proves reachability only, not paper quality or completeness.
- Do not cite papers that were not returned by a recorded query.
- Do not invent citations, DOIs, arXiv IDs, venues, quotes, datasets, or results.

## Source Coverage Rules
- Required source failures must be visible in reports.
- Fallback/fixture counts must be prominent.
- Offline runs may validate plumbing, not live-literature quality.

## Failure Modes
- `GAPFORGE_DISABLE_NETWORK=1` makes live validation unavailable.
- A connector returns only fallback metadata.
- A source is reachable but irrelevant for the field.
- Rate limits or source errors hide missing coverage.

## Validation Checklist
- [ ] Required/recommended source status is recorded.
- [ ] Query and failure records exist.
- [ ] Fallback/fixture data is labeled.
- [ ] Reports do not claim source coverage is sufficient when blockers remain.

## Examples
```bash
gapforge source-health --topic "low false positive collusion detection"
gapforge live-source-diagnostic --topic "low false positive collusion detection in LLM agents" --source-profile ai_safety --write-report
gapforge real-campaign-dry-run --profile live_low_fpr_collusion
```

## Uncertainty Rules
If sources are disabled, degraded, or unavailable, mark coverage insufficient or recommend refusal. Do not infer novelty from absence of results.

## Reasoning Storage
Store only public summaries and source diagnostics. Do not store hidden chain-of-thought.
