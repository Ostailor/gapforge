"""Job queue persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.models import JobQueue, from_dict, to_plain


def load_queue(path: Path) -> JobQueue:
    return from_dict(JobQueue, json.loads(path.read_text(encoding="utf-8")))


def save_queue(path: Path, queue: JobQueue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_plain(queue), indent=2) + "\n", encoding="utf-8")
