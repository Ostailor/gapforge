---
name: idea-bank
description: Use when a GapForge v2 task needs auditable idea candidates, rejected ideas, reviews, or evidence links.
---

# Idea Bank

## Purpose

Maintain first-class idea discovery state. Seeds, candidates, rejected ideas, evidence links, and reviews must survive across runs so v2 can search harder without forgetting failures.

## Object Distinctions

- `seed`: provisional idea. It may be speculative and must not be treated as accepted.
- `candidate`: structured idea ready for evidence, novelty, feasibility, and tournament checks.
- `rejected`: preserved failed idea with a reason.
- `agenda_item`: future work after no candidate passes.
- `experiment_ready` and `manuscript_ready`: later maturity states, separate from initial idea acceptance.

## Workflow

1. Create or load the project idea bank.
2. Add candidates with contribution type, core claim, proposed experiment, baselines, metrics, risks, and provenance.
3. Link evidence only to known paper IDs, evidence spans, or claims.
4. Preserve rejected candidates and human feedback records.
5. Write idea reports so humans can inspect why candidates survived or failed.

## Commands

```bash
gapforge idea-bank-create --project-id <project-id> --root-topic "<topic>"
gapforge idea-list --project-id <project-id>
gapforge idea-report --idea-id <idea-id>
gapforge idea-review --idea-id <idea-id>
```

Python:

```python
from gapforge import api

bank = api.create_idea_bank(project_id, root_topic)
ideas = api.generate_ideas(project_id=project_id)
```

## Never Do

- Delete rejected ideas to improve yield.
- Mark seeds as accepted.
- Invent citations, evidence spans, baselines, metrics, or results.
- Let human preference override novelty or evidence blockers.
