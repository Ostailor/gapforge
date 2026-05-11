---
name: selected-related-work-search
description: Use when planning or running v2.4 selected-benchmark related-work search campaigns.
---

# Selected Related-Work Search

## Purpose

Run the v2.4 category-specific search campaign that remediates the v2.3 publication blocker. v2.3 synthetic main benchmark completed, but it was not publication-ready because required related-work categories had no real paper records.

## Command Path

```bash
gapforge selected-related-work-search-plan --benchmark-id <benchmark-id>
gapforge selected-related-work-search-run --benchmark-id <benchmark-id>
gapforge selected-related-work-search-status --benchmark-id <benchmark-id>
gapforge selected-related-work-search-report --benchmark-id <benchmark-id>
```

## API Path

```python
from gapforge import api

campaign = api.plan_selected_related_work_search(benchmark_id)
campaign = api.run_selected_related_work_search(benchmark_id)
```

## Discipline Rules

- Every required category needs concrete search evidence.
- Fallback-only records do not complete a category.
- A source failure must create a blocker and next command.
- No fake citation, fake novelty claim, or synthetic deployment-validity claim can be introduced.
- Do not call the manuscript publication-ready from search evidence alone.
