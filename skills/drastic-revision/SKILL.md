---
name: drastic-revision
description: Use when converting v2.5 drastic review output into concrete revision, rebuttal, experiment, and claim-softening tasks.
---

# Drastic Revision

## Purpose

Turn harsh reviewer objections into concrete manuscript, experiment, related-work, artifact, and rebuttal tasks.

## Command Path

```bash
gapforge drastic-revision-plan --manuscript-id <manuscript-id>
gapforge apply-drastic-revision --manuscript-id <manuscript-id> --dry-run
gapforge drastic-revision-status --manuscript-id <manuscript-id>
gapforge v25-release-gate --write-report --json
```

## API Path

```python
from gapforge import api

plan = api.create_drastic_revision_plan(manuscript_id)
gate = api.v25_release_gate(write_report=True)
```

## Discipline Rules

- Rebuttal cannot excuse real blockers or invent evidence.
- Missing experiments become experiment requests; missing prior work becomes related-work requests.
- Overstrong claims must be softened or removed.
- If fatal blockers remain, publication-candidate status must be downgraded.
- Evidence discipline applies: no fake citation, fake result, fake review resolution, or hidden objection is allowed.
