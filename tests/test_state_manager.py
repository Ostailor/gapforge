from __future__ import annotations

import json
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import (
    CitationEdge,
    CitationGraph,
    Claim,
    Evidence,
    EvidenceSpan,
    ExperimentPlan,
    Gap,
    NoveltyAssessment,
    Paper,
    PaperArtifact,
    PaperNote,
    PaperSection,
    ResearchRunState,
    SearchQueryRecord,
    SourceCoverageReport,
)
from gapforge.state import RUN_ARTIFACTS, ResearchStateManager


def test_create_run_writes_durable_format(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))

    state = manager.create_run("low false positive collusion detection")

    run_dir = Path(state.run_dir)
    assert run_dir.exists()
    for artifact in RUN_ARTIFACTS:
        assert (run_dir / artifact).exists(), artifact
    assert json.loads((run_dir / "config.json").read_text(encoding="utf-8"))["schema_version"] == 2


def test_save_and_load_state_round_trips(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("calibrated collusion detection")
    paper = Paper(
        id="paper-1",
        title="A paper",
        authors=["A. Author"],
        year=2025,
        venue="TestConf",
        abstract="Abstract",
        url="https://example.test/paper-1",
        source="fixture",
    )
    manager.append_papers(state, [paper])

    loaded = manager.load_run(state.run_id)

    assert isinstance(loaded, ResearchRunState)
    assert loaded.run_id == state.run_id
    assert loaded.papers[0].id == "paper-1"


def test_loads_v1_style_state_dict_with_v2_defaults(tmp_path: Path) -> None:
    raw = {
        "run_id": "old-run",
        "topic": {
            "text": "old topic",
            "slug": "old-topic",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        "run_dir": str(tmp_path / "runs" / "old-run"),
        "config": {"schema_version": 1},
        "papers": [],
        "paper_notes": [],
        "paper_ranking": None,
        "claims": [],
        "gaps": [],
        "hypotheses": [],
        "cross_domain_analogies": [],
        "cross_domain_transfers": [],
        "novelty_assessments": [],
        "experiments": [],
        "reviewer_objections": [],
        "reviewer_summaries": [],
        "run_log": [],
        "rejected_ideas": [],
        "provenance": [],
        "completed_skills": [],
    }

    state = ResearchRunState.from_dict(raw)

    assert state.config["schema_version"] == 1
    assert state.paper_artifacts == []
    assert state.paper_sections == []
    assert state.evidence_spans == []
    assert state.search_queries == []
    assert state.source_coverage is None
    assert state.citation_graph is None
    assert state.human_reviews == []


def test_save_and_load_v2_full_text_state_objects(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("full text schema")
    paper = Paper(id="paper-1", title="Full text paper", authors=[], abstract="Abstract", year=2026, source="fixture")
    state.papers.append(paper)
    state.paper_artifacts.append(
        PaperArtifact(
            id="artifact-1",
            paper_id="paper-1",
            artifact_type="pdf",
            source_url="https://example.test/paper.pdf",
            local_path="artifacts/paper.pdf",
            sha256="abc123",
            bytes_size=123,
            mime_type="application/pdf",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    state.paper_sections.append(
        PaperSection(
            id="section-1",
            paper_id="paper-1",
            title="Results",
            normalized_title="results",
            section_type="results",
            text="The method improves recall at fixed false positive rate.",
            page_start=3,
            page_end=4,
            char_start=10,
            char_end=68,
            confidence="medium",
        )
    )
    state.evidence_spans.append(
        EvidenceSpan(
            id="span-1",
            paper_id="paper-1",
            section_id="section-1",
            quote="improves recall at fixed false positive rate",
            page_start=3,
            page_end=3,
            char_start=22,
            char_end=66,
            locator="Results, p. 3",
            evidence_type="result",
            confidence="medium",
        )
    )
    state.search_queries.append(
        SearchQueryRecord(
            id="query-1",
            query="full text schema",
            source_names=["fixture"],
            purpose="initial_topic",
            max_results=5,
            executed_at="2026-01-01T00:00:00+00:00",
            result_paper_ids=["paper-1"],
        )
    )
    state.source_coverage = SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=["fixture"],
        query_records=state.search_queries,
        papers_by_source={"fixture": 1},
        papers_with_pdf=["paper-1"],
        papers_with_full_text=["paper-1"],
        papers_abstract_only=[],
        confidence="medium",
    )
    state.citation_graph = CitationGraph(
        paper_ids=["paper-1"],
        edges=[CitationEdge(source_paper_id="paper-1", target_paper_id="paper-1", edge_type="manual", source="fixture")],
    )
    manager.save_run(state)

    loaded = manager.load_run(state.run_id)

    assert loaded.paper_artifacts[0].artifact_type == "pdf"
    assert loaded.paper_sections[0].section_type == "results"
    assert loaded.evidence_spans[0].section_id == "section-1"
    assert loaded.search_queries[0].purpose == "initial_topic"
    assert loaded.source_coverage is not None
    assert loaded.source_coverage.papers_with_full_text == ["paper-1"]
    assert loaded.citation_graph is not None
    assert loaded.citation_graph.edges[0].edge_type == "manual"
    run_dir = Path(state.run_dir)
    for artifact in [
        "paper_artifacts.json",
        "paper_sections.json",
        "evidence_spans.json",
        "search_queries.json",
        "source_coverage.json",
        "source_coverage.md",
        "citation_graph.json",
        "full_text_coverage.md",
        "evidence_spans.md",
        "citation_graph.md",
        "related_work_expansion.md",
        "paper_ranking.json",
        "paper_ranking.md",
        "gap_evidence_matrix.json",
        "gap_evidence_matrix.md",
        "human_reviews.json",
        "human_reviews.md",
    ]:
        assert (run_dir / artifact).exists(), artifact


def test_validation_fails_on_unsupported_supported_claim(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("claim validation")
    state.claims.append(
        Claim(
            id="claim-1",
            text="This claim is incorrectly marked supported.",
            type="background",
            status="supported",
            source_paper_ids=["paper-1"],
        )
    )

    result = manager.validate_state(state)

    assert not result.ok
    assert any(issue.code == "supported-claim-without-evidence" for issue in result.issues)


def test_validation_checks_gap_experiment_and_note_links(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("link validation")
    state.paper_notes.append(PaperNote(paper_id="", summary="Missing ID"))
    state.gaps.append(Gap(id="gap-1", description="Gap", why_it_matters="Matter"))
    state.experiments.append(ExperimentPlan(id="experiment-1", hypothesis_id="missing", title="Experiment", design="Design"))

    result = manager.validate_state(state)
    codes = {issue.code for issue in result.issues}

    assert "paper-note-without-paper-id" in codes
    assert "gap-without-linked-papers-or-reason" in codes
    assert "experiment-without-hypothesis" in codes


def test_append_claims_and_validate_novelty_prior_work(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("novelty validation")
    claim = Claim(
        id="claim-1",
        text="The proposed method is new.",
        type="novelty",
        status="uncertain",
        supporting_evidence=[Evidence(source_id="paper-1", quote="Prior title", locator="url")],
        source_paper_ids=["paper-1"],
    )

    manager.append_claims(state, [claim])
    result = manager.validate_state(state)

    assert not result.ok
    assert any(issue.code == "novelty-claim-without-prior-work" for issue in result.issues)


def test_validation_checks_strong_novelty_requires_prior_work(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("strong novelty validation")
    state.novelty_assessments.append(
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-1",
            idea_summary="A claimed strong idea",
            novelty_strength="strong",
            verdict="pursue",
        )
    )

    result = manager.validate_state(state)

    assert not result.ok
    assert any(issue.code == "strong-novelty-without-prior-work" for issue in result.issues)


def test_validation_checks_v2_full_text_links(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("full text link validation")
    state.papers.append(Paper(id="paper-1", title="Known", authors=[], abstract="", year=2026))
    state.paper_artifacts.append(PaperArtifact(id="artifact-1", paper_id="missing", artifact_type="pdf"))
    state.paper_sections.append(PaperSection(id="section-1", paper_id="missing", title="Results"))
    state.evidence_spans.append(EvidenceSpan(id="span-1", paper_id="paper-1", section_id="missing-section", quote="Evidence"))
    state.evidence_spans.append(EvidenceSpan(id="span-2", paper_id="missing", quote="Evidence"))

    result = manager.validate_state(state)
    codes = {issue.code for issue in result.issues}

    assert "paper-artifact-unknown-paper" in codes
    assert "paper-section-unknown-paper" in codes
    assert "evidence-span-unknown-section" in codes
    assert "evidence-span-unknown-paper" in codes


def test_validation_requires_evidence_spans_for_high_confidence_full_text_claims(tmp_path: Path) -> None:
    manager = ResearchStateManager(GapForgeConfig.from_cwd(tmp_path))
    state = manager.create_run("full text claim validation")
    state.papers.append(Paper(id="paper-1", title="Known", authors=[], abstract="", year=2026))
    state.paper_sections.append(PaperSection(id="section-1", paper_id="paper-1", title="Results", text="Supported result."))
    state.claims.append(
        Claim(
            id="claim-1",
            text="The full-text paper demonstrates a result.",
            type="result",
            status="supported",
            confidence="high",
            supporting_evidence=[Evidence(source_id="paper-1", source_paper_id="paper-1", quote="Supported result.", locator="Results")],
            source_paper_ids=["paper-1"],
            needs_verification=False,
        )
    )

    result = manager.validate_state(state)

    assert not result.ok
    assert any(issue.code == "high-confidence-full-text-claim-without-evidence-span" for issue in result.issues)

    state.evidence_spans.append(
        EvidenceSpan(
            id="span-1",
            paper_id="paper-1",
            section_id="section-1",
            quote="Supported result.",
            locator="Results",
            evidence_type="result",
        )
    )
    result = manager.validate_state(state)
    assert result.ok
