---
name: constructive-gap-creator
description: Use when GapForge v2 needs publishable contribution forms beyond a new-method idea.
---

# Constructive Gap Creator

## Purpose

When literature does not reveal a clean new-method gap, propose evidence-gated contribution forms such as benchmark, measurement, evaluation protocol, dataset, replication, negative result, theory note, system, or tooling.

## Required Fields

- contribution type
- problem
- why existing work makes the contribution useful
- minimum artifact
- minimum experiment
- required baselines
- closest prior work or missing search
- novelty risk, reviewer risk, feasibility, and evidence links

## Workflow

1. Inspect project memory, campaigns, related-work matrices, novelty dossiers, and rejected ideas.
2. Generate constructive gap candidates with minimum artifacts.
3. For benchmark and measurement ideas, name metrics.
4. For negative results, state the falsifiable expectation.
5. Keep the candidate evidence-gated and provisional.

## Commands

```bash
gapforge constructive-gaps --project-id <project-id>
gapforge constructive-gaps --campaign-id <campaign-id>
gapforge constructive-gap-report --project-id <project-id>
```

Python:

```python
from gapforge import api

gaps = api.generate_constructive_gaps(project_id=project_id)
```

## Never Do

- Treat a constructive gap as accepted without prior-work checks.
- Omit the minimum artifact.
- Invent benchmark results or claim a negative result before running it.
- Use vague “new method” framing when benchmark or measurement is the defensible path.
