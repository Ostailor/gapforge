"""Offline evaluation fixture loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gapforge.models import Gap, Paper, PaperNote, from_dict

SAMPLE_TOPIC = "low false positive collusion detection"
FIXTURE_NAMES = [
    "low_fpr_collusion",
    "lexical_substitution_monitoring",
    "quantum_portfolio_optimization",
    "wildfire_prediction_ml",
]


@dataclass(slots=True)
class EvalFixture:
    name: str
    topic: str
    path: Path
    papers: list[Paper]
    paper_notes: list[PaperNote]
    known_good_gaps: list[Gap]
    known_bad_gaps: list[Gap]
    duplicate_ideas: list[dict[str, Any]]
    expected_reviewer_objections: list[dict[str, Any]]


def default_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "research_topics"


def list_fixtures(root: Path | None = None) -> list[str]:
    fixture_root = root or default_fixture_root()
    if not fixture_root.exists():
        return []
    return sorted(path.name for path in fixture_root.iterdir() if path.is_dir())


def load_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_fixture_root()
    path = fixture_root / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown eval fixture: {name}")
    topic = _topic(path / "topic.md")
    return EvalFixture(
        name=name,
        topic=topic,
        path=path,
        papers=[from_dict(Paper, item) for item in _read_json(path / "papers.json")],
        paper_notes=[from_dict(PaperNote, item) for item in _read_json(path / "paper_notes.json")],
        known_good_gaps=[from_dict(Gap, item) for item in _read_json(path / "known_good_gaps.json")],
        known_bad_gaps=[from_dict(Gap, item) for item in _read_json(path / "known_bad_gaps.json")],
        duplicate_ideas=_read_json(path / "duplicate_ideas.json"),
        expected_reviewer_objections=_read_json(path / "expected_reviewer_objections.json"),
    )


def load_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or list_fixtures(root)
    return [load_fixture(name, root) for name in selected]


def _topic(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    return text.removeprefix("#").strip()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
