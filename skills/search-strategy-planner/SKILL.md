---
name: search-strategy-planner
description: Use when planning or reviewing GapForge v0.5 multi-round source-policy-aware literature search strategies.
---

# Search Strategy Planner

## Purpose
Plan intentional search rounds before reading, gap synthesis, novelty claims, or Codex research synthesis.

## Inputs
- Topic and source policy profile.
- Source policy requirements, source health diagnostics, existing query records, project memory, known gaps/directions.

## Outputs
- `SearchStrategy`
- `SearchRound`s for initial, survey, benchmark, novelty, adjacent-field, and counterevidence searches.
- `search_strategy.md` and `search_rounds.md`.

## Required Artifacts
- `data/search_strategies/<strategy-id>.json`
- `data/search_strategies/<strategy-id>.md`
- run `search_rounds.json`
- run `source_coverage.md`

## Procedure
1. Select the field profile explicitly, for example `ai_safety`, `medicine`, or `generic`.
2. Plan primary/newest queries and canonical/survey queries.
3. Add benchmark/dataset/method queries.
4. Add closest-prior-work queries before novelty.
5. Add adjacent-field queries only when an analogy or transfer claim is being explored.
6. Add exclusion/counterevidence queries.
7. Execute rounds and record failures before synthesis.

## Evidence/Citation Rules
- Search plans are not evidence. Only returned papers and recorded evidence spans support claims.
- Unknown citations become search requests.
- Do not invent papers, search results, venues, benchmarks, or datasets.

## Source Coverage Rules
- Strategy must reflect source policy requirements.
- Missing rounds cap novelty and readiness.
- Query failures must remain visible.

## Failure Modes
- One broad query dominates the campaign.
- No survey/canonical search, so old seminal work is missed.
- No closest-prior-work round, so novelty is overclaimed.
- Adjacent-field search is used as proof instead of hypothesis generation.

## Validation Checklist
- [ ] Multiple query families are present.
- [ ] Required sources are included.
- [ ] Closest-prior-work search exists.
- [ ] Missing or skipped rounds are explicit.
- [ ] Codex synthesis waits until minimum search rounds complete or fail visibly.

## Examples
```bash
gapforge plan-search-strategy "low false positive collusion detection in LLM agents" --source-profile ai_safety
gapforge execute-search-strategy --run-id <run-id> --strategy-id <strategy-id>
gapforge search-rounds --run-id <run-id>
```

## Uncertainty Rules
If required rounds are missing or skipped, novelty remains unknown/weak. Do not treat no results as evidence of novelty.

## Reasoning Storage
Store concise public planning summaries only. Do not store hidden chain-of-thought.
