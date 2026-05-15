---
name: matrix-recovery
description: Use when recovering, repairing, loading, or inspecting the v2.6 selected benchmark related-work matrix.
---

# Matrix Recovery

## Purpose

Recover or repair the selected manuscript related-work matrix so v2.6 can resolve `missing:related_work_matrix` honestly.

## Command Path

```bash
gapforge selected-related-work-matrix-load --benchmark-id <benchmark-id>
gapforge selected-related-work-matrix-repair --benchmark-id <benchmark-id>
gapforge selected-related-work-matrix-status --benchmark-id <benchmark-id>
gapforge v26-release-gate --write-report --json
```

## API Path

```python
from gapforge import api

load = api.load_selected_related_work_matrix(benchmark_id)
repair = api.repair_selected_related_work_matrix(benchmark_id)
gate = api.v26_release_gate(write_report=True)
```

## Discipline Rules

- Real paper IDs must resolve before counting entries.
- Must-cite and closest-prior-work entries must be visible.
- Treat the matrix as evidence for bounded claims, not a general readiness pass.
- Fallback-only or generated citation entries do not count as real related work.
- Missing categories remain blockers until explicitly repaired or justified.
- Do not invent evidence, fake citations, or matrix coverage.
- Do not claim publication readiness while the matrix is missing, invalid, or hidden.
