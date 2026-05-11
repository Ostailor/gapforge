---
name: prior-work-dossier-refresh
description: Use when refreshing the v2.4 selected-benchmark closest-prior-work dossier from curated papers.
---

# Prior-Work Dossier Refresh

## Purpose

Refresh the v2.4 closest-prior-work dossier after real paper curation and reading. The dossier must decide whether prior work makes the selected benchmark duplicate, weak, plausible, strong, or unknown.

## Command Path

```bash
gapforge read-selected-related-work --benchmark-id <benchmark-id>
gapforge selected-prior-work-refresh --benchmark-id <benchmark-id>
gapforge selected-prior-work-dossier --benchmark-id <benchmark-id>
```

## API Path

```python
from gapforge import api

readings = api.read_selected_related_work(benchmark_id)
dossier = api.refresh_selected_prior_work(benchmark_id)
```

## Discipline Rules

- Use full text when available and mark abstract-only evidence.
- Fallback-only records do not establish novelty.
- Directly solving prior work must trigger revise/no-go, not be hidden.
- No fake citation, fake novelty claim, or publication-ready label is allowed while the dossier is unknown.
- Preserve the v2.3 synthetic limitation: synthetic evidence is not deployment validity.
