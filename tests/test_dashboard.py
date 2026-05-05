from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import gapforge.models as gf_models
from gapforge.config import GapForgeConfig
from gapforge.dashboard import StaticDashboardBuilder
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


def test_static_run_dashboard_files_generated_and_escaped(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = _dashboard_run(config)

    result = StaticDashboardBuilder(config).build_run(state.run_id)

    expected = {
        "index.html",
        "papers.html",
        "gaps.html",
        "directions.html",
        "novelty.html",
        "evidence.html",
        "coverage.html",
        "reviews.html",
    }
    assert {path.name for path in result.pages} == expected
    for filename in expected:
        assert (Path(state.run_dir) / "dashboard" / filename).exists()
    papers = (Path(state.run_dir) / "dashboard" / "papers.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in papers
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in papers


def test_dashboard_includes_warnings_rejected_ideas_and_evidence(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = _dashboard_run(config)

    StaticDashboardBuilder(config).build_run(state.run_id)
    dashboard_dir = Path(state.run_dir) / "dashboard"

    assert "offline smoke warning" in (dashboard_dir / "coverage.html").read_text(encoding="utf-8")
    assert "Rejected duplicate idea" in (dashboard_dir / "reviews.html").read_text(encoding="utf-8")
    assert "paper-1:Results:p3" in (dashboard_dir / "evidence.html").read_text(encoding="utf-8")


def test_static_project_dashboard_shows_directions_and_human_reviews(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = _dashboard_run(config)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Dashboard Project")
    project_manager.attach_run(program.project.id, state.run_id)
    program = project_manager.load_project(program.project.id)
    program.research_directions = [
        gf_models.ResearchDirection(
            id="direction-1",
            project_id=program.project.id,
            title="Dashboard Direction",
            linked_gap_ids=["gap-1"],
            maturity="candidate",
            readiness_score=0.42,
            blocking_issues=["coverage is weak"],
            next_actions=["search more prior work"],
            supporting_paper_ids=["paper-1"],
        )
    ]
    project_manager.save_project(program)

    result = StaticDashboardBuilder(config).build_project(program.project.id)

    directions = (result.root / "directions.html").read_text(encoding="utf-8")
    reviews = (result.root / "reviews.html").read_text(encoding="utf-8")
    assert "Dashboard Direction" in directions
    assert "coverage is weak" in directions
    assert "researcher note" in reviews


def test_dashboard_cli_generates_run_dashboard(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = _dashboard_run(config)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "dashboard", "--run-id", state.run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "index.html" in result.stdout
    assert (Path(state.run_dir) / "dashboard" / "index.html").exists()


def _dashboard_run(config: GapForgeConfig):
    manager = ResearchStateManager(config)
    state = manager.create_run("dashboard topic")
    state.papers = [
        gf_models.Paper(
            id="paper-1",
            title="<script>alert(1)</script> Low-FPR Paper",
            authors=["Ada"],
            abstract="Abstract",
            year=2026,
            source="fixture",
            url="https://example.test/paper",
        )
    ]
    state.gaps = [
        gf_models.Gap(
            id="gap-1",
            title="Dashboard gap",
            description="Inspect evidence and uncertainty.",
            supporting_paper_ids=["paper-1"],
            confidence="medium",
            novelty_status="unknown",
            risk_that_gap_is_fake="Coverage is weak.",
        )
    ]
    state.evidence_spans = [
        gf_models.EvidenceSpan(
            id="span-1",
            paper_id="paper-1",
            section_id="section-1",
            quote="Evidence locator should remain visible.",
            locator="paper-1:Results:p3",
            evidence_type="result",
        )
    ]
    state.source_coverage = gf_models.SourceCoverageReport(
        run_id=state.run_id,
        topic=state.topic.text,
        searched_sources=["fixture-source"],
        query_records=[
            gf_models.SearchQueryRecord(
                id="query-1",
                query="dashboard topic",
                source_names=["fixture-source"],
                purpose="initial_topic",
                result_paper_ids=["paper-1"],
            )
        ],
        papers_by_source={"fixture": 1},
        papers_with_full_text=["paper-1"],
        coverage_warnings=["offline smoke warning"],
        confidence="low",
    )
    state.rejected_ideas = [gf_models.RejectedIdea(id="rej-1", idea="Rejected duplicate idea", reason="Already covered.")]
    state.human_reviews = [
        gf_models.HumanReviewRecord(
            id="review-1",
            object_type="gap",
            object_id="gap-1",
            action="annotate",
            note="researcher note",
            reviewer="tester",
        )
    ]
    manager.save_run(state)
    return state
