---
name: drastic-reviewer
description: Use when running the v2.5 drastic OpenReview-style reviewer panel against a manuscript or selected benchmark.
---

# Drastic Reviewer

## Purpose

Run a harsher-than-normal reviewer panel calibrated by review taxonomy issues so the paper receives serious top-conference-style critique.

## Command Path

```bash
gapforge drastic-review --manuscript-id <manuscript-id>
gapforge drastic-review --benchmark-id <benchmark-id>
gapforge drastic-review-report --manuscript-id <manuscript-id>
```

## API Path

```python
from gapforge import api

panel = api.run_drastic_review(manuscript_id=manuscript_id)
```

## Discipline Rules

- Every criticism must map to manuscript text, artifacts, recorded evidence, or missing evidence.
- Do not invent citations, missing results, benchmark failures, or reviewer consensus.
- If the paper is likely reject or only a workshop candidate, say so.
- Fatal flaws and unresolved objections must remain visible.
- Evidence discipline applies: no fake citation, fake result, fake review, or unsupported claim is allowed.
- Drastic review is simulated critique, not a venue decision.
