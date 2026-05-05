from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import Gap, NoveltyAssessment, NoveltyDossier, Paper, PaperSection, SearchQueryRecord, SourceCoverageReport
from gapforge.orchestrator import Orchestrator
from gapforge.reporting import build_final_report, write_final_report
from gapforge.sources.coverage import refresh_source_coverage
from gapforge.sources.policies import get_source_policy_profile
from gapforge.sources.stopping import refresh_stopping_assessment


def test_query_record_is_created_for_search(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path), sources=[FixtureSource()])

    state = orchestrator.search("low false positive collusion detection", max_results=5)

    assert state.search_queries
    record = state.search_queries[0]
    assert record.purpose == "initial_topic"
    assert record.query == "low false positive collusion detection"
    assert record.source_names == ["Fixture"]
    assert record.result_paper_ids == ["paper-1"]
    assert state.source_coverage is not None
    assert state.source_coverage.searched_sources == ["Fixture"]


def test_source_failures_are_recorded_in_query_and_coverage(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path), sources=[FailingSource(), FixtureSource()])

    state = orchestrator.search("collusion detection", max_results=5)

    assert state.search_queries[0].failure_messages
    assert state.source_coverage is not None
    assert "Failing" in state.source_coverage.failed_sources
    assert any("Failing search failed" in warning for warning in state.source_coverage.coverage_warnings)


def test_coverage_warns_when_all_papers_are_fallback(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("fallback fixture")
    state.papers = [
        Paper(
            id="fallback-1",
            title="Fallback Paper",
            authors=[],
            abstract="fallback",
            year=2024,
            source="arXiv",
            raw_metadata={"fallback": True},
        )
    ]

    refresh_source_coverage(state)

    assert state.source_coverage is not None
    assert state.source_coverage.fallback_paper_count == 1
    assert any("smoke test" in warning for warning in state.source_coverage.coverage_warnings)


def test_coverage_warns_without_full_text_and_improves_with_sections(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("coverage fixture")
    state.papers = [Paper(id="p1", title="Paper", authors=[], abstract="abstract", year=2024, source="manual")]

    refresh_source_coverage(state)
    assert state.source_coverage is not None
    assert state.source_coverage.papers_with_full_text == []
    assert any("No parsed full text" in warning for warning in state.source_coverage.coverage_warnings)

    state.paper_sections = [
        PaperSection(id="s1", paper_id="p1", title="Results", section_type="results", text="Results show useful evidence.")
    ]
    refresh_source_coverage(state)

    assert state.source_coverage.papers_with_full_text == ["p1"]
    assert not any("No parsed full text" in warning for warning in state.source_coverage.coverage_warnings)


def test_coverage_cli_and_final_report_include_source_coverage(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path), sources=[FixtureSource()])
    state = orchestrator.search("collusion detection", max_results=5)
    orchestrator.state_store.save_run(state)

    write_final_report(state)
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "coverage", "--run-id", state.run_id],
        cwd=tmp_path,
        env={**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = (Path(state.run_dir) / "final_report.md").read_text(encoding="utf-8")

    assert "Search and Source Coverage" in report
    assert "Queries run: 1" in report
    assert (Path(state.run_dir) / "source_coverage.md").exists()


def test_ai_safety_profile_requires_ai_safety_sources(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("ai safety low false positive monitor evasion")
    state.papers = [
        Paper(
            id=f"p{i}",
            title=("Survey of AI safety evaluations" if i == 0 else f"AI safety benchmark paper {i}"),
            authors=[],
            abstract="evaluation benchmark threat model survey" if i == 0 else "evaluation benchmark threat model",
            year=2025,
            source=["arXiv", "OpenReview", "Semantic Scholar"][i % 3],
        )
        for i in range(20)
    ]
    state.paper_sections = [
        PaperSection(id=f"s{i}", paper_id=f"p{i}", title="Evaluation", section_type="experiments", text="full text") for i in range(6)
    ]
    state.search_queries = [
        SearchQueryRecord(
            id="q1",
            query="ai safety survey benchmark evaluation threat model",
            source_names=["arXiv", "OpenReview", "Semantic Scholar"],
            purpose="initial_topic",
            max_results=20,
            result_paper_ids=[paper.id for paper in state.papers],
        ),
        SearchQueryRecord(id="q2", query="ai safety closest prior work", source_names=["Semantic Scholar"], purpose="novelty"),
        SearchQueryRecord(id="q3", query="ai safety related work", source_names=["Semantic Scholar"], purpose="citation_expansion"),
        SearchQueryRecord(id="q4", query="ai safety cybersecurity control theory", source_names=["arXiv"], purpose="analogy"),
    ]
    state.source_coverage = SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=["arXiv", "OpenReview", "Semantic Scholar"],
        query_records=state.search_queries,
        papers_by_source={"arXiv": 7, "OpenReview": 7, "Semantic Scholar": 6},
        papers_with_full_text=[f"p{i}" for i in range(6)],
        confidence="high",
    )

    assessment = refresh_stopping_assessment(state, profile="ai_safety")

    assert assessment.enough_for_mapping
    assert assessment.enough_for_gap_mining
    assert assessment.enough_for_novelty
    assert assessment.profile_id == "ai_safety"


def test_medicine_profile_warns_about_pubmed_placeholder(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("medical screening false positives")
    state.papers = [
        Paper(id="p1", title="Clinical screening review", authors=[], abstract="systematic review", year=2025, source="CrossRef")
    ]
    refresh_source_coverage(state)

    assessment = refresh_stopping_assessment(state, profile=get_source_policy_profile("medicine"))

    assert any("PubMed-like source" in item for item in assessment.missing_requirements)
    assert any("PubMed" in query for query in assessment.recommended_queries)


def test_poor_policy_coverage_recommends_searches(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("low false positive collusion detection")
    state.papers = [Paper(id="p1", title="Fallback", authors=[], abstract="fallback", year=2025, source="fixture")]
    refresh_source_coverage(state)

    assessment = refresh_stopping_assessment(state, profile="ai_safety")

    assert not assessment.enough_for_mapping
    assert not assessment.enough_for_novelty
    assert assessment.recommended_queries
    assert any("required source" in item for item in assessment.missing_requirements)


def test_source_policy_cli_lists_profiles(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "source-policy", "--list"],
        cwd=tmp_path,
        env={**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ai_safety" in result.stdout
    assert "medicine" in result.stdout


def test_strict_report_uses_policy_stopping_assessment(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("ai safety novelty policy gate")
    state.papers = [Paper(id="p1", title="Related Work", authors=[], abstract="related", year=2025, source="arXiv")]
    state.paper_sections = [PaperSection(id="s1", paper_id="p1", title="Results", section_type="results", text="evidence")]
    state.gaps = [
        Gap(
            id="gap-1",
            title="Policy-gated gap",
            description="Evaluate monitor evasion under strict false-positive budgets.",
            supporting_paper_ids=["p1"],
            risk_that_gap_is_fake="Source coverage may be too narrow.",
            confidence="medium",
        )
    ]
    state.novelty_assessments = [
        NoveltyAssessment(
            target_gap_or_hypothesis_id="gap-1",
            idea_summary="Policy-gated gap",
            closest_prior_work=["p1: Related Work"],
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
        )
    ]
    state.novelty_dossiers = [
        NoveltyDossier(
            target_id="gap-1",
            idea_summary="Policy-gated gap",
            top_prior_work=["p1: Related Work"],
            verdict="pursue",
            novelty_strength="medium",
            confidence="medium",
        )
    ]
    refresh_source_coverage(state)
    refresh_stopping_assessment(state, profile="ai_safety")

    report = build_final_report(state, strict=True)
    direction = report["sections"]["recommended_top_research_direction"]

    assert direction["readiness"] == "not_ready"
    assert any("source policy" in reason.lower() for reason in direction["blocking_reasons"])


def test_offline_smoke_does_not_pass_novelty_coverage(tmp_path: Path) -> None:
    orchestrator = Orchestrator(GapForgeConfig.from_cwd(tmp_path))
    state = orchestrator.init_topic("offline smoke")
    refresh_source_coverage(state, ["Network disabled; offline smoke test."])

    assessment = refresh_stopping_assessment(state, profile="generic")

    assert not assessment.enough_for_novelty
    assert assessment.confidence == "low"


class FixtureSource:
    name = "Fixture"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [Paper(id="paper-1", title=f"Paper for {query}", authors=[], abstract="abstract", year=2025, source=self.name)]


class FailingSource:
    name = "Failing"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        raise RuntimeError("source unavailable")
