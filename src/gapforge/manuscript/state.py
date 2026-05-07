"""Persistence for first-class manuscript state."""

from __future__ import annotations

import json
from pathlib import Path

from gapforge.manuscript.models import ManuscriptState
from gapforge.models import from_dict, to_plain

MANUSCRIPT_SUBDIRS = [
    "sections",
    "figures",
    "tables",
    "bibliography",
    "reviews",
    "submission",
    "artifact_evaluation",
]


class ManuscriptStateStore:
    """Read and write manuscript state in a project-scoped manuscript directory."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    @property
    def state_path(self) -> Path:
        return self.root_dir / "manuscript.json"

    def ensure_layout(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        for subdir in MANUSCRIPT_SUBDIRS:
            (self.root_dir / subdir).mkdir(parents=True, exist_ok=True)

    def load(self) -> ManuscriptState:
        if not self.state_path.exists():
            raise FileNotFoundError(f"No manuscript state found at {self.state_path}")
        return from_dict(ManuscriptState, json.loads(self.state_path.read_text(encoding="utf-8")))

    def save(self, state: ManuscriptState) -> None:
        self.ensure_layout()
        self.state_path.write_text(json.dumps(to_plain(state), indent=2) + "\n", encoding="utf-8")
