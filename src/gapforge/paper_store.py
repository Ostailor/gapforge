"""Persistence helper for paper search results."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.models import Paper, to_plain


class PaperStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, papers: list[Paper]) -> None:
        self.path.write_text(json.dumps(to_plain(papers), indent=2) + "\n", encoding="utf-8")

    def load(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))
