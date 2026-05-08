"""Backup helpers for migration snapshots."""

from __future__ import annotations

import shutil
from pathlib import Path

from gapforge.state import utc_now_compact


def create_backup_snapshot(source: Path, backup_root: Path, object_type: str, object_id: str) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"Cannot back up missing migration source: {source}")
    backup_root.mkdir(parents=True, exist_ok=True)
    destination = backup_root / f"{object_type}-{object_id}-{utc_now_compact()}"
    suffix = 2
    candidate = destination
    while candidate.exists():
        candidate = destination.with_name(f"{destination.name}-{suffix}")
        suffix += 1
    if source.is_dir():
        shutil.copytree(source, candidate)
    else:
        candidate.mkdir(parents=True, exist_ok=False)
        shutil.copy2(source, candidate / source.name)
    return candidate
