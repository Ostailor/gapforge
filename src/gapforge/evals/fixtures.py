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
    PriorWorkRecallAssessment,
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
V4_FIXTURE_NAMES = [
    "fake_agent_campaign",
    "novelty_research_loop",
    "undercovered_refusal",
    "invalid_agent_output",
    "experiment_ready_direction",
    "reviewer_fatal_flaw",
]
V5_FIXTURE_NAMES = [
    "live_like_low_fpr_collusion",
    "live_like_monitor_evasion",
    "live_like_prior_work_duplicate",
    "live_like_undercovered_refusal",
    "live_like_cross_domain_specificity",
]
V6_FIXTURE_NAMES = [
    "smoke_success",
    "failed_run",
    "missing_baseline",
    "low_fpr_underpowered",
    "fake_result_rejected",
    "reproducible_result",
    "paper_package_result_labels",
]
V7_FIXTURE_NAMES = [
    "fixture_benchmark_success",
    "fixture_benchmark_failure",
    "low_fpr_underpowered_benchmark",
    "replication_package_canary",
    "fake_result_rejected",
]
V8_FIXTURE_NAMES = [
    "complete_submission_package",
    "unsupported_claim_blocked",
    "fake_citation_blocked",
    "smoke_result_overclaim",
    "missing_artifact_package",
    "anonymous_submission_leak",
    "reviewer_rebuttal_required",
    "camera_ready_blocked",
]
V9_FIXTURE_NAMES = [
    "accepted_direction",
    "accepted_refusal",
    "product_failure_fake_citation",
    "product_failure_workflow_break",
    "incomplete_missing_review",
    "v1_ready_project",
    "v1_blocked_migration",
]
V21_FIXTURE_NAMES = [
    "complete_smoke_benchmark",
    "missing_honest_null_distribution",
    "underpowered_low_fpr_overclaim",
    "missing_baseline",
    "fake_result_blocked",
    "manuscript_smoke_labeled",
    "reviewer_blocks_publishability",
]
V2_IDEA_FIXTURE_NAMES = [
    "accepted_benchmark_idea",
    "accepted_measurement_idea",
    "accepted_negative_result_idea",
    "generic_idea_rejected",
    "duplicate_idea_rejected",
    "agenda_after_no_survivors",
    "fake_citation_blocked",
    "human_preference_changes_winner",
    "mutation_rescues_rejected_idea",
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
    is_v4: bool = False
    is_v5: bool = False
    is_v6: bool = False
    is_v7: bool = False
    is_v8: bool = False
    is_v9: bool = False
    is_v21: bool = False
    is_v2_ideas: bool = False
    campaign_fixture: dict[str, Any] = field(default_factory=dict)
    real_literature_fixture: dict[str, Any] = field(default_factory=dict)
    experiment_fixture: dict[str, Any] = field(default_factory=dict)
    benchmark_fixture: dict[str, Any] = field(default_factory=dict)
    manuscript_fixture: dict[str, Any] = field(default_factory=dict)
    pilot_fixture: dict[str, Any] = field(default_factory=dict)
    selected_benchmark_fixture: dict[str, Any] = field(default_factory=dict)
    idea_fixture: dict[str, Any] = field(default_factory=dict)

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


def default_v4_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "campaign_v4"


def default_v5_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "real_literature_v5"


def default_v6_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "experiments_v6"


def default_v7_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "benchmarks_v7"


def default_v8_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "manuscript_v8"


def default_v9_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "pilots_v9"


def default_v21_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "selected_benchmark_v21"


def default_v2_idea_fixture_root() -> Path:
    return Path.cwd() / "tests" / "fixtures" / "ideas_v2"


def list_fixtures(root: Path | None = None) -> list[str]:
    fixture_root = root or default_fixture_root()
    if not fixture_root.exists():
        return []
    return sorted(path.name for path in fixture_root.iterdir() if path.is_dir())


def load_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_fixture_root()
    path = fixture_root / name
    if not path.exists():
        v4_path = default_v4_fixture_root() / name
        if v4_path.exists():
            return load_v4_fixture(name, default_v4_fixture_root())
        v5_path = default_v5_fixture_root() / name
        if v5_path.exists():
            return load_v5_fixture(name, default_v5_fixture_root())
        v6_path = default_v6_fixture_root() / name
        if v6_path.exists():
            return load_v6_fixture(name, default_v6_fixture_root())
        v7_path = default_v7_fixture_root() / name
        if v7_path.exists():
            return load_v7_fixture(name, default_v7_fixture_root())
        v8_path = default_v8_fixture_root() / name
        if v8_path.exists():
            return load_v8_fixture(name, default_v8_fixture_root())
        v9_path = default_v9_fixture_root() / name
        if v9_path.exists():
            return load_v9_fixture(name, default_v9_fixture_root())
        v21_path = default_v21_fixture_root() / name
        if v21_path.exists():
            return load_v21_fixture(name, default_v21_fixture_root())
        v2_idea_path = default_v2_idea_fixture_root() / name
        if v2_idea_path.exists():
            return load_v2_idea_fixture(name, default_v2_idea_fixture_root())
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


def load_v4_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_v4_fixture_root()
    path = fixture_root / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown v4 eval fixture: {name}")
    raw = _read_json(path / "fixture.json")
    topic = str(raw.get("topic", name.replace("_", " ")))
    papers = [from_dict(Paper, item) for item in raw.get("papers", [])]
    if not papers:
        papers = [
            Paper(
                id=f"paper-{name}",
                title=f"Synthetic fixture paper for {topic}",
                authors=["GapForge fixture"],
                abstract="Synthetic offline fixture metadata for campaign behavior evaluation.",
                year=2026,
                source="fixture",
            )
        ]
    gaps = [from_dict(Gap, item) for item in raw.get("known_good_gaps", [])]
    if not gaps:
        gaps = [
            Gap(
                id=f"gap-{name}",
                title=f"Synthetic campaign gap for {topic}",
                description="Offline fixture gap with explicit evidence linkage for campaign evaluation.",
                supporting_paper_ids=[papers[0].id],
                why_existing_work_does_not_solve_it="Fixture encodes the expected campaign behavior rather than a real finding.",
                minimum_experiment_needed="Synthetic protocol check only.",
                risk_that_gap_is_fake="This is synthetic fixture data and must not be treated as a literature conclusion.",
                confidence="medium",
            )
        ]
    return EvalFixture(
        name=name,
        topic=topic,
        path=path,
        papers=papers,
        paper_notes=[from_dict(PaperNote, item) for item in raw.get("paper_notes", [])],
        known_good_gaps=gaps,
        known_bad_gaps=[from_dict(Gap, item) for item in raw.get("known_bad_gaps", [])],
        duplicate_ideas=list(raw.get("duplicate_ideas", [])),
        expected_reviewer_objections=list(raw.get("expected_reviewer_objections", [])),
        paper_sections=[from_dict(PaperSection, item) for item in raw.get("paper_sections", [])],
        evidence_spans=[from_dict(EvidenceSpan, item) for item in raw.get("evidence_spans", [])],
        expected_novelty_dossiers=[from_dict(NoveltyDossier, item) for item in raw.get("expected_novelty_dossiers", [])],
        expected_gap_evidence_matrix=[from_dict(GapEvidenceMatrix, item) for item in raw.get("expected_gap_evidence_matrix", [])],
        expected_source_coverage=(
            from_dict(SourceCoverageReport, raw["expected_source_coverage"]) if raw.get("expected_source_coverage") else None
        ),
        is_v4=True,
        campaign_fixture=raw,
    )


def load_v5_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_v5_fixture_root()
    path = fixture_root / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown v5 eval fixture: {name}")
    papers = [from_dict(Paper, item) for item in _read_json(path / "papers.json")]
    sections_path = path / "paper_sections.json"
    if not sections_path.exists():
        sections_path = path / "excerpts.json"
    source_health = _read_json(path / "source_health.json")
    prior_work = from_dict(PriorWorkRecallAssessment, _read_json(path / "prior_work_recall_assessment.json"))
    novelty_dossiers = [from_dict(NoveltyDossier, item) for item in _read_json(path / "novelty_dossiers.json")]
    related_work = [from_dict(RelatedWorkMatrix, item) for item in _read_json(path / "related_work_matrix.json")]
    human_review = _read_json(path / "human_quality_review.json")
    expected_gate = _read_json(path / "expected_release_gate_result.json")
    canonical_papers = _read_json(path / "canonical_papers.json")
    fixture_payload = {
        "source_health": source_health,
        "papers": _read_json(path / "papers.json"),
        "search_strategy": _read_json(path / "search_strategy.json"),
        "search_rounds": _read_json(path / "search_rounds.json"),
        "canonical_papers": canonical_papers,
        "prior_work_recall_assessment": _read_json(path / "prior_work_recall_assessment.json"),
        "novelty_dossiers": _read_json(path / "novelty_dossiers.json"),
        "related_work_matrix": _read_json(path / "related_work_matrix.json"),
        "human_quality_review": human_review,
        "expected_release_gate_result": expected_gate,
    }
    topic = str(expected_gate.get("topic", name.replace("_", " ")))
    return EvalFixture(
        name=name,
        topic=topic,
        path=path,
        papers=papers,
        paper_notes=[],
        known_good_gaps=[
            Gap(
                id=f"gap-{name}",
                title=topic,
                description="Offline v0.5 real-literature behavior fixture.",
                supporting_paper_ids=[papers[0].id] if papers else [],
                why_existing_work_does_not_solve_it="Encoded by fixture prior-work and novelty gate artifacts.",
                minimum_experiment_needed="Use fixture gate expectations.",
                risk_that_gap_is_fake="This fixture tests behavior only and is not a real literature claim.",
                confidence="medium",
            )
        ],
        known_bad_gaps=[],
        duplicate_ideas=[],
        expected_reviewer_objections=[],
        paper_sections=[from_dict(PaperSection, item) for item in _read_json_optional(sections_path, [])],
        evidence_spans=[from_dict(EvidenceSpan, item) for item in _read_json(path / "evidence_spans.json")],
        expected_novelty_dossiers=novelty_dossiers,
        expected_source_coverage=None,
        human_gold_prior_work=[{"paper_id": paper_id} for paper_id in prior_work.top_prior_work_ids or prior_work.candidate_prior_work_ids],
        human_gold_related_work_matrix=related_work,
        is_v5=True,
        real_literature_fixture=fixture_payload,
    )


def load_v6_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_v6_fixture_root()
    path = fixture_root / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown v6 eval fixture: {name}")
    raw = _read_json(path / "fixture.json")
    topic = str(raw.get("topic", name.replace("_", " ")))
    papers = [
        Paper(
            id=f"paper-{name}",
            title=f"Experiment fixture paper for {topic}",
            authors=["GapForge fixture"],
            abstract="Synthetic offline fixture metadata for v0.6 experiment execution evaluation.",
            year=2026,
            source="fixture",
        )
    ]
    return EvalFixture(
        name=name,
        topic=topic,
        path=path,
        papers=papers,
        paper_notes=[],
        known_good_gaps=[
            Gap(
                id=f"gap-{name}",
                title=topic,
                description="Offline v0.6 experiment behavior fixture.",
                supporting_paper_ids=[papers[0].id],
                why_existing_work_does_not_solve_it="Fixture encodes execution and empirical validation behavior only.",
                minimum_experiment_needed="Use fixture execution records and result artifacts.",
                risk_that_gap_is_fake="This is synthetic fixture data and is not a real empirical result.",
                confidence="medium",
            )
        ],
        known_bad_gaps=[],
        duplicate_ideas=[],
        expected_reviewer_objections=[],
        is_v6=True,
        experiment_fixture=raw,
    )


def load_v7_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_v7_fixture_root()
    path = fixture_root / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown v7 eval fixture: {name}")
    raw = _read_json(path / "fixture.json")
    topic = str(raw.get("topic", name.replace("_", " ")))
    papers = [
        Paper(
            id=f"paper-{name}",
            title=f"Benchmark fixture paper for {topic}",
            authors=["GapForge fixture"],
            abstract="Synthetic offline fixture metadata for v0.7 benchmark and replication evaluation.",
            year=2026,
            source="fixture",
        )
    ]
    return EvalFixture(
        name=name,
        topic=topic,
        path=path,
        papers=papers,
        paper_notes=[],
        known_good_gaps=[
            Gap(
                id=f"gap-{name}",
                title=topic,
                description="Offline v0.7 benchmark behavior fixture.",
                supporting_paper_ids=[papers[0].id],
                why_existing_work_does_not_solve_it="Fixture encodes benchmark, aggregation, and replication behavior only.",
                minimum_experiment_needed="Use fixture benchmark execution records and replication artifacts.",
                risk_that_gap_is_fake="This is synthetic fixture data and is not a real benchmark result.",
                confidence="medium",
            )
        ],
        known_bad_gaps=[],
        duplicate_ideas=[],
        expected_reviewer_objections=[],
        is_v7=True,
        benchmark_fixture=raw,
    )


def load_v8_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_v8_fixture_root()
    path = fixture_root / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown v8 eval fixture: {name}")
    raw = _read_json(path / "fixture.json")
    topic = str(raw.get("topic", name.replace("_", " ")))
    papers = [
        Paper(
            id=f"paper-{name}",
            title=f"Manuscript fixture paper for {topic}",
            authors=["GapForge fixture"],
            abstract="Synthetic offline fixture metadata for v0.8 manuscript submission evaluation.",
            year=2026,
            source="fixture",
        )
    ]
    return EvalFixture(
        name=name,
        topic=topic,
        path=path,
        papers=papers,
        paper_notes=[],
        known_good_gaps=[
            Gap(
                id=f"gap-{name}",
                title=topic,
                description="Offline v0.8 manuscript behavior fixture.",
                supporting_paper_ids=[papers[0].id],
                why_existing_work_does_not_solve_it="Fixture encodes manuscript traceability, review, and submission gates only.",
                minimum_experiment_needed="Use fixture manuscript package and release-gate artifacts.",
                risk_that_gap_is_fake="This is synthetic fixture data and is not a real manuscript claim.",
                confidence="medium",
            )
        ],
        known_bad_gaps=[],
        duplicate_ideas=[],
        expected_reviewer_objections=[],
        is_v8=True,
        manuscript_fixture=raw,
    )


def load_v9_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_v9_fixture_root()
    path = fixture_root / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown v9 eval fixture: {name}")
    raw = _read_json(path / "fixture.json")
    topic = str(raw.get("topic", name.replace("_", " ")))
    papers = [
        Paper(
            id=f"paper-{name}",
            title=f"Pilot fixture paper for {topic}",
            authors=["GapForge fixture"],
            abstract="Synthetic offline fixture metadata for v0.9 external pilot and v1 readiness evaluation.",
            year=2026,
            source="fixture",
        )
    ]
    return EvalFixture(
        name=name,
        topic=topic,
        path=path,
        papers=papers,
        paper_notes=[],
        known_good_gaps=[
            Gap(
                id=f"gap-{name}",
                title=topic,
                description="Offline v0.9 pilot behavior fixture.",
                supporting_paper_ids=[papers[0].id],
                why_existing_work_does_not_solve_it="Fixture encodes pilot outcome, review, audit, and release-gate behavior only.",
                minimum_experiment_needed="Use fixture pilot and v1 readiness artifacts.",
                risk_that_gap_is_fake="This is synthetic fixture data and is not a real pilot outcome.",
                confidence="medium",
            )
        ],
        known_bad_gaps=[],
        duplicate_ideas=[],
        expected_reviewer_objections=[],
        is_v9=True,
        pilot_fixture=raw,
    )


def load_v21_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_v21_fixture_root()
    path = fixture_root / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown v2.1 selected benchmark eval fixture: {name}")
    raw = _read_json(path / "fixture.json")
    topic = str(raw.get("topic", name.replace("_", " ")))
    papers = [
        Paper(
            id=f"paper-{name}",
            title=f"Selected benchmark fixture paper for {topic}",
            authors=["GapForge fixture"],
            abstract="Synthetic offline fixture metadata for v2.1 selected benchmark execution evaluation.",
            year=2026,
            source="fixture",
        )
    ]
    return EvalFixture(
        name=name,
        topic=topic,
        path=path,
        papers=papers,
        paper_notes=[],
        known_good_gaps=[
            Gap(
                id=f"gap-{name}",
                title=topic,
                description="Offline v2.1 selected benchmark execution behavior fixture.",
                supporting_paper_ids=[papers[0].id],
                why_existing_work_does_not_solve_it=(
                    "Fixture encodes selected benchmark specification, smoke execution, review, and release gate behavior only."
                ),
                minimum_experiment_needed="Use fixture selected benchmark records and release-gate expectations.",
                risk_that_gap_is_fake="This is synthetic fixture data and is not a real benchmark result.",
                confidence="medium",
            )
        ],
        known_bad_gaps=[],
        duplicate_ideas=[],
        expected_reviewer_objections=[],
        is_v21=True,
        selected_benchmark_fixture=raw,
    )


def load_v2_idea_fixture(name: str, root: Path | None = None) -> EvalFixture:
    fixture_root = root or default_v2_idea_fixture_root()
    path = fixture_root / name
    if not path.exists():
        raise FileNotFoundError(f"Unknown v2 idea eval fixture: {name}")
    raw = _read_json(path / "fixture.json")
    topic = str(raw.get("topic", name.replace("_", " ")))
    papers = [
        Paper(
            id=paper_id,
            title=f"Idea fixture paper {paper_id}",
            authors=["GapForge fixture"],
            abstract="Synthetic offline fixture metadata for v2 idea discovery evaluation.",
            year=2026,
            source="fixture",
        )
        for paper_id in raw.get("known_paper_ids", ["paper-fixture"])
    ]
    return EvalFixture(
        name=name,
        topic=topic,
        path=path,
        papers=papers,
        paper_notes=[],
        known_good_gaps=[
            Gap(
                id=f"gap-{name}",
                title=topic,
                description="Offline v2 idea discovery behavior fixture.",
                supporting_paper_ids=[papers[0].id] if papers else [],
                why_existing_work_does_not_solve_it="Fixture encodes idea discovery behavior only.",
                minimum_experiment_needed="Use fixture idea-candidate, mutation, novelty, tournament, and feedback records.",
                risk_that_gap_is_fake="This is synthetic fixture data and is not a real literature claim.",
                confidence="medium",
            )
        ],
        known_bad_gaps=[],
        duplicate_ideas=[],
        expected_reviewer_objections=[],
        is_v2_ideas=True,
        idea_fixture=raw,
    )


def load_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or FIXTURE_NAMES
    return [load_fixture(name, root) for name in selected]


def load_v3_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or V3_FIXTURE_NAMES
    return [load_v3_fixture(name, root) for name in selected]


def load_v4_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or V4_FIXTURE_NAMES
    return [load_v4_fixture(name, root) for name in selected]


def load_v5_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or V5_FIXTURE_NAMES
    return [load_v5_fixture(name, root) for name in selected]


def load_v6_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or V6_FIXTURE_NAMES
    return [load_v6_fixture(name, root) for name in selected]


def load_v7_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or V7_FIXTURE_NAMES
    return [load_v7_fixture(name, root) for name in selected]


def load_v8_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or V8_FIXTURE_NAMES
    return [load_v8_fixture(name, root) for name in selected]


def load_v9_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or V9_FIXTURE_NAMES
    return [load_v9_fixture(name, root) for name in selected]


def load_v21_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or V21_FIXTURE_NAMES
    return [load_v21_fixture(name, root) for name in selected]


def load_v2_idea_fixtures(names: list[str] | None = None, root: Path | None = None) -> list[EvalFixture]:
    selected = names or V2_IDEA_FIXTURE_NAMES
    return [load_v2_idea_fixture(name, root) for name in selected]


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
