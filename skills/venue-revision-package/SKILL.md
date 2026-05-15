---
name: venue-revision-package
description: Use when creating or inspecting the v2.6 venue revision package after artifact integration and drastic review rerun.
---

# Venue Revision Package

## Purpose

Create a post-review revision package that bundles manuscript, bibliography, related-work matrix, artifact package, benchmark/no-fit report, drastic review, revision delta, limitations, and checklist.

## Command Path

```bash
gapforge selected-venue-artifact-integrate --benchmark-id <benchmark-id>
gapforge selected-venue-revision-package --benchmark-id <benchmark-id>
gapforge selected-venue-revision-status --benchmark-id <benchmark-id>
gapforge v26-release-gate --write-report --json
```

## API Path

```python
from gapforge import api

integration = api.integrate_venue_artifacts(benchmark_id)
package = api.create_venue_revision_package(benchmark_id)
gate = api.v26_release_gate(write_report=True)
```

## Discipline Rules

- Label package status as `conference_candidate`, `workshop_candidate`, `revise_for_reviews`, or `no_go` according to evidence.
- Conference-candidate status requires no fatal blockers.
- Include real benchmark or no-fit status and limitations.
- Do not copy venue-style prose.
- Do not label the package as accepted or camera-ready.
- Do not invent evidence or include fake citations, fake results, or synthetic deployment-validity claims.
