---
name: contribution-positioning
description: Use when softening v2.4 selected-benchmark contribution claims after prior-work review.
---

# Contribution Positioning

## Purpose

Translate the v2.4 prior-work dossier into publication-safe claims, claims to avoid, reviewer risks, and real paper citation requirements.

## Command Path

```bash
gapforge selected-positioning --benchmark-id <benchmark-id>
gapforge selected-positioning-report --benchmark-id <benchmark-id>
gapforge selected-related-work-matrix-v2 --benchmark-id <benchmark-id>
```

## API Path

```python
from gapforge import api

positioning = api.position_selected_contribution(benchmark_id)
matrix = api.build_selected_related_work_matrix_v2(benchmark_id)
```

## Discipline Rules

- If novelty is plausible but not strong, use careful wording.
- Avoid first, SOTA, novel, deployment-valid, and publication-ready unless gates support them.
- Include closest prior work citations and synthetic limitations.
- Cite real paper records for every required related-work claim.
- Fallback-only records do not count as citation support.
- No fake citation or hidden counterevidence is allowed.
