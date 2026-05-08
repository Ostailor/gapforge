---
name: idea-synthesis
description: Use when Codex/GPT-5.4 is asked to synthesize GapForge v2 ideas, mutations, critiques, or agenda patches.
---

# Idea Synthesis

## Purpose

Use Codex/GPT-5.4 to propose structured patches from the topic portfolio, idea bank, evidence, prior work, and human preferences. Outputs are untrusted until validated and imported.

## Task Types

- `idea_seed_expansion`
- `idea_mutation`
- `constructive_gap_synthesis`
- `cross_domain_idea_transfer`
- `idea_critique`
- `idea_tournament_judge`
- `research_agenda_builder`

## Required Prompt Context

- topic portfolio
- existing idea bank and rejected ideas
- prior-work blockers and source coverage summary
- evidence links and allowed paper IDs
- human preferences and feedback
- exact output schemas
- no fake citations/results rule
- public reasoning summary only

## Outputs

- `idea_candidates_patch.json`
- `idea_mutations_patch.json`
- `constructive_gaps_patch.json`
- `transfer_candidates_patch.json`
- `idea_reviews_patch.json`
- `agenda_patch.json`

## Commands

```bash
gapforge idea-codex-task --project-id <project-id> --type idea_seed_expansion
gapforge idea-codex-handoff --task-id <task-id>
gapforge idea-codex-import --task-id <task-id>
```

## Validation Rules

- candidate contribution type is required
- claimed evidence links must resolve
- fake citations and fake results are rejected
- strong novelty is blocked unless prior-work gates exist
- generic ideas are rejected or downgraded
- Codex output cannot bypass human review or release gates
