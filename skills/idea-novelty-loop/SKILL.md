---
name: idea-novelty-loop
description: Use when a GapForge v2 idea needs closest-prior-work search, counterevidence, or novelty assessment.
---

# Idea Novelty Loop

## Purpose

Attack promising idea candidates before promoting them. v2 searches harder for ideas, but every serious idea still faces the v1-style evidence and novelty discipline.

## Workflow

1. Generate prior-work queries from title, claim, experiment, baselines, metrics, and contribution type.
2. Search the current corpus.
3. Search live sources only when enabled and record missing searches otherwise.
4. Retrieve closest prior work.
5. Find counterevidence.
6. Update novelty status.
7. Reject, revise, recommend mutation, or pursue.

## Verdicts

- `reject`: closest prior work or counterevidence blocks the core idea.
- `revise`: plausible with material changes.
- `pursue`: enough support for further evaluation, not paper readiness.
- `unknown`: missing searches or evidence block judgment.

## Commands

```bash
gapforge idea-novelty --idea-id <idea-id>
gapforge idea-novelty --project-id <project-id> --top-k 10
gapforge idea-counterevidence --idea-id <idea-id>
```

Python:

```python
from gapforge import api

assessment = api.run_idea_novelty(idea_id=idea_id)
```

## Never Do

- Mark strong novelty without completed prior-work search.
- Ignore counterevidence.
- Treat missing searches as proof of novelty.
- Delete duplicate ideas instead of preserving rejection evidence.
