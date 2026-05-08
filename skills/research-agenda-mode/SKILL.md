---
name: research-agenda-mode
description: Use when GapForge v2 active search finds no defensible accepted idea candidate.
---

# Research Agenda Mode

## Purpose

Convert honest no-idea outcomes into staged future work. Agenda mode is actionable refusal, not a hidden success state.

## Enter When

- no candidate survives novelty, evidence, feasibility, tournament, and human-review gates
- source coverage is too weak
- closest prior work invalidates the strongest candidates
- constructive gaps lack minimum artifacts
- human review rejects the remaining portfolio
- more mutation would be low-value without new evidence

## Agenda Contents

- blocker summary
- concrete agenda steps
- required artifacts
- success criteria
- decision points
- stop conditions
- estimated effort
- provenance and human review

## Commands

```bash
gapforge research-agenda --project-id <project-id>
gapforge agenda-report --agenda-id <agenda-id>
gapforge agenda-to-campaigns --agenda-id <agenda-id>
```

Python:

```python
from gapforge import api

agenda = api.generate_research_agenda(project_id)
```

## Release Rule

For v2.0, an accepted candidate is preferred. Agenda-only fallback can pass the release gate only with `--allow-agenda-only` and `idea_discovery_incomplete` warning notes. Do not claim v2 found an idea when agenda mode is the final output.

## Never Do

- Label agenda steps as accepted ideas.
- Hide blockers to make refusal look successful.
- Bypass human review.
- Treat agenda mode as paper readiness.
