---
name: idea-tournament
description: Use when GapForge v2 has multiple idea candidates that need transparent comparison or selection.
---

# Idea Tournament

## Purpose

Rank surviving ideas under shared criteria and select one strongest candidate or create a research agenda. Tournament selection is not final acceptance.

## Scoring Dimensions

- evidence support
- novelty
- experimentability
- tractability
- impact
- reviewer risk
- time-to-demo
- benchmark availability
- baseline availability
- cross-domain leverage
- human preference

## Workflow

1. Load candidate pool and human preferences.
2. Disqualify generic ideas, fake citations/results, fatal novelty blockers, and human-rejected candidates.
3. Score viable candidates transparently.
4. Select the top viable idea or create an agenda if no idea survives.
5. Require human review before final acceptance.

## Commands

```bash
gapforge idea-tournament --project-id <project-id>
gapforge idea-tournament --project-id <project-id> --top-k 5
gapforge selected-idea --project-id <project-id>
gapforge idea-score-report --project-id <project-id>
```

Python:

```python
from gapforge import api

tournament = api.run_idea_tournament(project_id, top_k=5)
```

## Never Do

- Let bad ideas win because they are numerous.
- Treat tournament score as novelty proof.
- Override human rejection.
- Accept a selected idea without human review and evidence gates.
