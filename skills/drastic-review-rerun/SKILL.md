---
name: drastic-review-rerun
description: Use when rerunning v2.6 drastic review after matrix, artifact package, and benchmark/no-fit remediation.
---

# Drastic Review Rerun

## Purpose

Rerun harsh review after v2.6 remediation and compare old and new blockers without weakening reviewer standards.

## Command Path

```bash
gapforge drastic-review-rerun --manuscript-id <manuscript-id>
gapforge drastic-readiness-delta --manuscript-id <manuscript-id>
gapforge drastic-revision-close --manuscript-id <manuscript-id> --item-id <item-id>
gapforge v26-release-gate --write-report --json
```

## API Path

```python
from gapforge import api

rerun = api.rerun_drastic_review(manuscript_id)
gate = api.v26_release_gate(write_report=True)
```

## Discipline Rules

- Compare v2.5 and v2.6 blockers explicitly.
- Mark `missing:related_work_matrix` and `missing:artifact_package` resolved only when loadable artifacts exist.
- Treat rerun findings as evidence for bounded readiness changes, not a venue decision.
- Preserve new or remaining fatal blockers.
- Conference-candidate status is blocked while fatal blockers remain.
- Workshop-candidate status is allowed only when remaining issues are nonfatal and limitations are explicit.
- Do not invent evidence, fake reviewer outcomes, or acceptance claims.
