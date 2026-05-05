from __future__ import annotations

# ruff: noqa: I001

import os
import subprocess
import sys
from pathlib import Path

import gapforge.models as gf_models
from gapforge.campaigns import CampaignManager
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
        "campaigns.html",
        "actual_runs.html",
        "canaries.html",
        "agent_tasks.html",
        "imports.html",
        "human_reviews.html",
        "release_gate.html",
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


def test_actual_run_dashboard_labels_fake_vs_real_and_blockers(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_id, real_campaign_id, fake_campaign_id = _actual_run_project(config)

    result = StaticDashboardBuilder(config).build_project(project_id)

    actual_runs = (result.root / "actual_runs.html").read_text(encoding="utf-8")
    release_gate = (result.root / "release_gate.html").read_text(encoding="utf-8")
    assert real_campaign_id in actual_runs
    assert fake_campaign_id in actual_runs
    assert "real-attested" in (result.root / "imports.html").read_text(encoding="utf-8")
    assert "fake-agent only" in release_gate.lower()
    assert "PASSED" in release_gate


def test_actual_run_dashboard_escapes_and_does_not_read_transcripts(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_id, _real_campaign_id, _fake_campaign_id = _actual_run_project(config, unsafe=True)

    result = StaticDashboardBuilder(config).build_project(project_id)

    human_reviews = (result.root / "human_reviews.html").read_text(encoding="utf-8")
    assert "<script>alert(99)</script>" not in human_reviews
    assert "&lt;script&gt;alert(99)&lt;/script&gt;" in human_reviews
    combined = "\n".join(path.read_text(encoding="utf-8") for path in result.pages)
    assert "sk-test-transcript-secret" not in combined


def test_release_gate_dashboard_cli(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_id, _real_campaign_id, _fake_campaign_id = _actual_run_project(config)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "release-gate-dashboard", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "release_gate.html" in result.stdout
    assert (config.project_root / project_id / "dashboard" / "release_gate.html").exists()


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


def _actual_run_project(config: GapForgeConfig, *, unsafe: bool = False) -> tuple[str, str, str]:
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Actual Run Dashboard Project")
    state = _dashboard_run(config)
    project_manager.attach_run(program.project.id, state.run_id)
    campaign_manager = CampaignManager(config)
    real = campaign_manager.create_campaign(
        "actual run dashboard topic",
        project_id=program.project.id,
        mode="codex_task_pack",
        agent_name="codex",
        model="gpt-5.4",
    )
    real = campaign_manager.attach_run(real.campaign.id, state.run_id)
    real.imports.append(
        gf_models.CampaignImportRecord(
            id="import-real-1",
            campaign_id=real.campaign.id,
            task_id="task-real-1",
            status="applied",
            accepted_objects=[
                {"type": "novelty_dossier", "id": "dossier-1", "source_path": "outputs/novelty_dossiers_patch.json"},
                {"type": "agent_actual_run_attestation", "id": "attestation-1", "accepted": True},
            ],
        )
    )
    real.human_reviews.append(
        gf_models.CampaignHumanReview(
            id="campaign-review-1",
            campaign_id=real.campaign.id,
            reviewer="tester",
            accepted=True,
            notes="<script>alert(99)</script>" if unsafe else "accepted real Codex output",
        )
    )
    real.acceptance_summary = gf_models.CampaignAcceptanceSummary(
        campaign_id=real.campaign.id,
        accepted=True,
        actual_run_attestation_present=True,
        accepted_real_agent_outputs=["import-real-1"],
        release_gate_eligible=True,
    )
    campaign_manager.save_campaign_state(real)
    fake = campaign_manager.create_campaign("fake dashboard topic", project_id=program.project.id, mode="fake_agent")
    fake.imports.append(
        gf_models.CampaignImportRecord(
            id="import-fake-1",
            campaign_id=fake.campaign.id,
            task_id="task-fake-1",
            status="applied",
            accepted_objects=[{"type": "fake_output", "id": "fake"}],
        )
    )
    campaign_manager.save_campaign_state(fake)
    transcript_dir = config.project_root / program.project.id / "campaigns" / real.campaign.id / "agent_tasks" / "task-real-1"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    (transcript_dir / "llm_transcript.md").write_text("sk-test-transcript-secret", encoding="utf-8")
    return program.project.id, real.campaign.id, fake.campaign.id
