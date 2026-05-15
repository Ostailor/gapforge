---
name: artifact-package-repair
description: Use when loading, repairing, regenerating, or inspecting the v2.6 selected manuscript artifact evaluation package.
---

# Artifact Package Repair

## Purpose

Recover or create a reviewer-loadable artifact package so v2.6 can resolve `missing:artifact_package` without inventing files.

## Command Path

```bash
gapforge selected-artifact-package-load --benchmark-id <benchmark-id>
gapforge selected-artifact-package-repair --benchmark-id <benchmark-id>
gapforge selected-artifact-package-status --benchmark-id <benchmark-id>
gapforge v26-release-gate --write-report --json
```

## API Path

```python
from gapforge import api

load = api.load_selected_artifact_package(benchmark_id)
repair = api.repair_selected_artifact_package(benchmark_id)
gate = api.v26_release_gate(write_report=True)
```

## Discipline Rules

- Require README/install/run instructions, expected outputs, hashes, hardware/time notes, and replication links.
- Exclude restricted/private data by default.
- Preserve smoke, pilot, main, failed, and skipped labels.
- If source artifacts are missing, report exact blockers and commands.
- Treat package contents as evidence for bounded claims, not a general readiness pass.
- Do not invent package files, outputs, hashes, commands, or badge claims.
