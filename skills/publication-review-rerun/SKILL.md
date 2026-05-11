---
name: publication-review-rerun
description: Use when rerunning the v2.4 selected-benchmark publication review after related-work remediation.
---

# Publication Review Rerun

## Purpose

Rerun the selected benchmark publication-readiness review after v2.4 related-work search, real paper curation, reading, dossier refresh, contribution positioning, and manuscript revision.

## Command Path

```bash
gapforge selected-publication-review --benchmark-id <benchmark-id> --after-related-work
gapforge selected-publication-fix-list --benchmark-id <benchmark-id>
gapforge selected-manuscript-related-work-revise --benchmark-id <benchmark-id>
gapforge selected-paper-package-v24 --benchmark-id <benchmark-id>
gapforge v24-release-gate --write-report --json
```

## API Path

```python
from gapforge import api

review = api.rerun_selected_publication_review(benchmark_id)
revision = api.revise_selected_manuscript_related_work(benchmark_id)
gate = api.v24_release_gate(write_report=True)
```

## Discipline Rules

- Missing categories cannot yield publication-ready.
- Fallback-only related work cannot yield publication-ready.
- Synthetic evidence is not deployment validity.
- No fake citation or fake novelty claim can pass.
- A duplicate closest prior work result must become no-go, not a softened publication-ready claim.
