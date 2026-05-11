---
name: related-work-curation
description: Use when attaching, rejecting, or reviewing v2.4 selected-benchmark related-work paper records.
---

# Related-Work Curation

## Purpose

Curate v2.4 related-work search results into accepted real paper attachments, rejected records, waivers, and visible missing categories.

## Command Path

```bash
gapforge attach-related-paper --benchmark-id <benchmark-id> --category "low-FPR detection/evaluation" --paper-id <paper-id>
gapforge reject-related-paper --benchmark-id <benchmark-id> --paper-id <paper-id> --reason "not relevant"
gapforge related-work-auto-curate --benchmark-id <benchmark-id>
gapforge related-work-curation-report --benchmark-id <benchmark-id>
```

## API Path

```python
from gapforge import api

attachment = api.attach_related_paper(
    benchmark_id,
    category="low-FPR detection/evaluation",
    paper_id=paper_id,
    relationship="closest_prior_work",
)
```

## Discipline Rules

- Real paper records must resolve to known paper IDs.
- Fallback-only records do not complete a category.
- Missing categories must stay visible; no fake citation can be accepted.
- Counterevidence and closest prior work are preserved even when they weaken novelty.
- Synthetic benchmark evidence is not deployment validity or publication-ready evidence.
