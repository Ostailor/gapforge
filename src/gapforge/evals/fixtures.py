"""Offline evaluation fixture loading."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gapforge.models import (
    EvidenceSpan,
    Gap,
    GapEvidenceMatrix,
    NoveltyDossier,
    Paper,
    PaperNote,
    PaperSection,
    RelatedWorkMatrix,
    SourceCoverageReport,
    from_dict,
)

SAMPLE_TOPIC = "low false positive collusion detection"
FIXTURE_NAMES = [
    "low_fpr_collusion",
    "lexical_substitution_monitoring",
    "quantum_portfolio_optimization",
    "wildfire_prediction_ml",
]
V2_FIXTURE_NAMES = [
    "low_fpr_collusion_v2",
    "lexical_substitution_monitoring_v2",
    "ai_agent_covert_channels_v2",
    "medical_screening_false_positives_v2",
    "cartel_detection_economics_v2",
]
V3_FIXTURE_NAMES = [
    "low_fpr_collusion",
    "llm_monitor_evasion",
    "medical_screening_specificity",
    "cartel_detection_economics",
    "physics_phase_transition_analogy",
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
    paper_sections: list[PaperSection] = field(default_factory=list)
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)
    expected_novelty_dossiers: list[NoveltyDossier] = field(default_factory=list)
    expected_gap_evidence_matrix: list[GapEvidenceMatrix] = field(default_factory=list)
    expected_source_coverage: SourceCoverageReport | None = None
    human_gold_prior_work: list[dict[str, Any]] = field(default_factory=list)
    human_gold_related_work_matrix: list[RelatedWorkMatrix] = field(default_factory=list)
    human_gold_reviewer_objections: list[dict[str, Any]] = field(default_factory=list)
    expected_not_ready_reasons: list[str] = field(default_factory=list)
    is_v3: bool = False

    @property
    def is_v2(self) -> bool:
        return bool(
            self.paper_sections
            or self.evidence_spans
            or self.expected_novelty_dossiers
            or self.expected_gap_evidence_matrix
            or self.expected_source_coverage
        )


def default_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "research_topics"


def default_v3_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "curated_v3" / "topics"


def list_fixtures(root: Path | None = None) -> list[str]:
    fixture_root = root or default_fixture_root()
    if not fixture_root.exists():
        return []
    return sorted(path.name for path in fixture_root.iterdir() if path.is_dir())


def load_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_fixture_root()
    path = fixture_root / name
    if not path.exists():
        v3_path = default_v3_fixture_root() / name
        if v3_path.exists():
            return load_v3_fixture(name, default_v3_fixture_root())
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
        paper_sections=[from_dict(PaperSection, item) for item in _read_json_optional(path / "paper_sections.json", [])],
        evidence_spans=[from_dict(EvidenceSpan, item) for item in _read_json_optional(path / "evidence_spans.json", [])],
        expected_novelty_dossiers=[
            from_dict(NoveltyDossier, item) for item in _read_json_optional(path / "expected_novelty_dossiers.json", [])
        ],
        expected_gap_evidence_matrix=[
            from_dict(GapEvidenceMatrix, item) for item in _read_json_optional(path / "expected_gap_evidence_matrix.json", [])
        ],
        expected_source_coverage=(
            from_dict(SourceCoverageReport, _read_json(path / "expected_source_coverage.json"))
            if (path / "expected_source_coverage.json").exists()
            else None
        ),
    )


def load_v3_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_v3_fixture_root()
    path = fixture_root / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown v3 eval fixture: {name}")
    topic = _topic(path / "topic.md")
    sections_path = path / "paper_sections.json"
    if not sections_path.exists():
        sections_path = path / "excerpt_sections.json"
    return EvalFixture(
        name=name,
        topic=topic,
        path=path,
        papers=[from_dict(Paper, item) for item in _read_json(path / "curated_papers.json")],
        paper_notes=[from_dict(PaperNote, item) for item in _read_json_optional(path / "paper_notes.json", [])],
        known_good_gaps=[from_dict(Gap, item) for item in _read_json(path / "human_gold_gaps.json")],
        known_bad_gaps=[],
        duplicate_ideas=[],
        expected_reviewer_objections=_read_json_optional(path / "human_gold_reviewer_objections.json", []),
        paper_sections=[from_dict(PaperSection, item) for item in _read_json_optional(sections_path, [])],
        evidence_spans=[from_dict(EvidenceSpan, item) for item in _read_json(path / "evidence_spans.json")],
        expected_novelty_dossiers=[],
        expected_gap_evidence_matrix=[],
        expected_source_coverage=(
            from_dict(SourceCoverageReport, _read_json(path / "expected_source_coverage.json"))
            if (path / "expected_source_coverage.json").exists()
            else None
        ),
        human_gold_prior_work=_read_json(path / "human_gold_prior_work.json"),
        human_gold_related_work_matrix=[
            from_dict(RelatedWorkMatrix, item) for item in _read_json(path / "human_gold_related_work_matrix.json")
        ],
        human_gold_reviewer_objections=_read_json(path / "human_gold_reviewer_objections.json"),
        expected_not_ready_reasons=_read_json(path / "expected_not_ready_reasons.json"),
        is_v3=True,
    )


def load_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or FIXTURE_NAMES
    return [load_fixture(name, root) for name in selected]


def load_v3_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or V3_FIXTURE_NAMES
    return [load_v3_fixture(name, root) for name in selected]


def _topic(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if clean:
            return clean.removeprefix("#").strip()
    return ""


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_optional(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return _read_json(path)
