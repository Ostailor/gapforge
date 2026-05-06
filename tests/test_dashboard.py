from __future__ import annotations

# ruff: noqa: I001

import os
import subprocess
import sys
from pathlib import Path

import gapforge.models as gf_models
from gapforge.baselines import BaselineRegistry
from gapforge.campaigns import CampaignManager
from gapforge.config import GapForgeConfig
from gapforge.dashboard import StaticDashboardBuilder
from gapforge.datasets import DatasetRegistry
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.export.paper_package import PaperPackageExporter
from gapforge.metrics import MetricRegistry
from gapforge.project_memory import ProjectMemoryManager
from gapforge.real_literature.review import RealLiteratureReviewManager
from gapforge.results import ResultParser
from gapforge.reporting import write_final_report
from gapforge.reviewers import EmpiricalReviewBuilder
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
        "live_sources.html",
        "search_strategy.html",
        "search_rounds.html",
        "prior_work_recall.html",
        "real_literature_quality.html",
        "v5_release_gate.html",
        "experiment_workspaces.html",
        "experiment_runs.html",
        "datasets.html",
        "baselines.html",
        "metrics.html",
        "results.html",
        "reproducibility.html",
        "empirical_reviews.html",
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


def test_dashboard_renders_real_literature_quality_sections(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_id, campaign_id, _run_id = _real_literature_quality_project(config)

    result = StaticDashboardBuilder(config).build_project(project_id)

    live_sources = (result.root / "live_sources.html").read_text(encoding="utf-8")
    search_strategy = (result.root / "search_strategy.html").read_text(encoding="utf-8")
    search_rounds = (result.root / "search_rounds.html").read_text(encoding="utf-8")
    prior_work = (result.root / "prior_work_recall.html").read_text(encoding="utf-8")
    quality = (result.root / "real_literature_quality.html").read_text(encoding="utf-8")
    v5_gate = (result.root / "v5_release_gate.html").read_text(encoding="utf-8")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in result.pages)

    assert "arxiv" in live_sources
    assert "low false positive collusion" in search_strategy
    assert "novelty" in search_rounds
    assert "missing_required_round" in prior_work
    assert "prior work blocker" in prior_work
    assert "rejected/not accepted" in quality
    assert "Workflow acceptance is separate from research-quality acceptance" in quality
    assert campaign_id in v5_gate
    assert "sk-test-transcript-secret" not in combined


def test_real_literature_campaign_and_run_reports_render(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_id, campaign_id, run_id = _real_literature_quality_project(config)
    campaign_manager = CampaignManager(config)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)

    campaign_report = campaign_manager.campaign_report(campaign_id)
    project_report = project_manager.write_project_report(project_manager.load_project(project_id))
    final_report = write_final_report(state_manager.load_run(run_id))

    campaign_text = campaign_report.read_text(encoding="utf-8")
    real_campaign_text = (config.project_root / project_id / "campaigns" / campaign_id / "real_literature_campaign_report.md").read_text(
        encoding="utf-8"
    )
    project_text = project_report.read_text(encoding="utf-8")
    final_text = final_report.read_text(encoding="utf-8")
    assert "Real-literature quality" in campaign_text
    assert "Workflow acceptance vs research-quality acceptance" in real_campaign_text
    assert "Missing prior-work search rounds" in real_campaign_text
    assert "Real Literature Quality" in project_text
    assert "Real-Literature Quality" in final_text
    assert "Recommendation refused because" in final_text


def test_dashboard_renders_experiment_pages_failed_runs_and_warnings(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project_id, workspace_id, failed_execution_id = _experiment_dashboard_project(config)

    result = StaticDashboardBuilder(config).build_project(project_id)

    expected_pages = {
        "experiment_workspaces.html",
        "experiment_runs.html",
        "datasets.html",
        "baselines.html",
        "metrics.html",
        "results.html",
        "reproducibility.html",
        "empirical_reviews.html",
    }
    assert expected_pages.issubset({path.name for path in result.pages})
    runs = (result.root / "experiment_runs.html").read_text(encoding="utf-8")
    datasets = (result.root / "datasets.html").read_text(encoding="utf-8")
    results = (result.root / "results.html").read_text(encoding="utf-8")
    reproducibility = (result.root / "reproducibility.html").read_text(encoding="utf-8")
    reviews = (result.root / "empirical_reviews.html").read_text(encoding="utf-8")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in result.pages)

    assert workspace_id in (result.root / "experiment_workspaces.html").read_text(encoding="utf-8")
    assert failed_execution_id in runs
    assert "Command exited with return code 2." in runs
    assert "&lt;script&gt;dataset&lt;/script&gt;" in datasets
    assert "fixture/synthetic/generated data" in results.lower()
    assert "metric-result-dashboard" in results
    assert "claim-dashboard" in results
    assert "dataset_cards" in reproducibility
    assert "deterministic fatal empirical review blockers" in reviews
    assert "sk-test-dashboard-secret" not in combined


def test_dashboard_cli_generates_workspace_dashboard(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    _project_id, workspace_id, _failed_execution_id = _experiment_dashboard_project(config)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "dashboard", "--workspace-id", workspace_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "index.html" in result.stdout
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    assert (Path(workspace.root_dir) / "dashboard" / "experiment_runs.html").exists()


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


def _real_literature_quality_project(config: GapForgeConfig) -> tuple[str, str, str]:
    project_manager = ProjectMemoryManager(config)
    state_manager = ResearchStateManager(config)
    campaign_manager = CampaignManager(config)
    program = project_manager.create_project("Real Literature Dashboard Project")
    state = _dashboard_run(config)
    state.source_coverage.fallback_paper_count = 1
    state.search_strategies.append(
        gf_models.SearchStrategy(
            id="strategy-real-lit",
            topic=state.topic.text,
            source_profile="ai_safety",
            primary_queries=["low false positive collusion"],
            survey_queries=["survey low false positive AI safety monitors"],
            benchmark_queries=["benchmark false positive monitor collusion"],
            closest_prior_work_queries=["closest prior work low false positive collusion"],
            expected_sources=["arxiv"],
        )
    )
    state.search_rounds.append(
        gf_models.SearchRound(
            id="round-novelty",
            strategy_id="strategy-real-lit",
            round_type="novelty",
            sources=["arxiv"],
            status="complete",
            result_paper_ids=["paper-1"],
        )
    )
    state.prior_work_recall_assessments.append(
        gf_models.PriorWorkRecallAssessment(
            id="recall-gap-1",
            target_id="gap-1",
            required_query_rounds=["novelty", "survey", "benchmark", "missing_required_round"],
            completed_query_rounds=["novelty"],
            candidate_prior_work_ids=["paper-1"],
            top_prior_work_ids=["paper-1"],
            missing_required_searches=["missing_required_round"],
            recall_confidence="low",
            novelty_allowed=False,
            blocking_issues=["prior work blocker"],
        )
    )
    state.gap_evidence_matrices.append(
        gf_models.GapEvidenceMatrix(
            gap_id="gap-1",
            papers_supporting=["paper-1"],
            papers_countering=["paper-1"],
            confidence="low",
        )
    )
    state_manager.save_run(state)
    project_manager.attach_run(program.project.id, state.run_id)
    campaign = campaign_manager.create_campaign(
        "real literature quality topic",
        project_id=program.project.id,
        mode="codex_task_pack",
        agent_name="codex",
        model="gpt-5.4",
        source_profile="ai_safety",
    )
    campaign = campaign_manager.attach_run(campaign.campaign.id, state.run_id)
    campaign.stop_conditions.append(
        gf_models.CampaignStopCondition(
            id="stop-poor-coverage",
            campaign_id=campaign.campaign.id,
            reason="not_ready_poor_coverage: recommendation refused because prior work recall is incomplete",
            triggered=True,
        )
    )
    campaign_manager.save_campaign_state(campaign)
    campaign_dir = config.project_root / program.project.id / "campaigns" / campaign.campaign.id
    (campaign_dir / "live_source_diagnostic.json").write_text(
        """{
  "id": "diagnostic-real-lit",
  "topic": "real literature quality topic",
  "source_profile": "ai_safety",
  "source_health_checks": [
    {"source_name": "arxiv", "status": "healthy", "test_query": "low false positive collusion", "result_count": 3}
  ],
  "minimum_coverage_met": true
}
""",
        encoding="utf-8",
    )
    RealLiteratureReviewManager(config).review(
        campaign.campaign.id,
        accept_workflow=True,
        accept_quality=False,
        reviewer="quality tester",
        reason="Workflow ran, but prior-work recall is incomplete.",
        missed_obvious_prior_work=True,
    )
    transcript_dir = campaign_dir / "agent_tasks" / "task-real-lit"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    (transcript_dir / "llm_transcript.md").write_text("sk-test-transcript-secret", encoding="utf-8")
    return program.project.id, campaign.campaign.id, state.run_id


def _experiment_dashboard_project(config: GapForgeConfig) -> tuple[str, str, str]:
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Experiment Dashboard Project")
    direction_id = "direction-dashboard-experiment"
    program.experiment_protocols.append(
        gf_models.ExperimentProtocol(
            id="protocol-dashboard-experiment",
            direction_id=direction_id,
            linked_experiment_plan_id="experiment-dashboard",
            objective="Render experiment execution state in the dashboard.",
            hypothesis="Dashboard pages show executions, artifacts, claims, and failures without leaking logs.",
            datasets=["fixture"],
            metrics=["false positive rate"],
            statistical_tests=["confidence intervals"],
            expected_artifacts=["metrics.json"],
        )
    )
    program.research_directions = [
        gf_models.ResearchDirection(
            id=direction_id,
            project_id=program.project.id,
            title="Experiment Dashboard Direction",
            maturity="experiment_ready",
        )
    ]
    project_manager.save_project(program)
    workspace = ExperimentWorkspaceManager(config).create_workspace(project_id=program.project.id, direction_id=direction_id)
    dataset_path = Path(workspace.root_dir) / "data" / "dashboard_fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,1\n", encoding="utf-8")
    DatasetRegistry(config).register_dataset(
        workspace_id=workspace.id,
        name="<script>dataset</script>",
        path=dataset_path,
        dataset_type="fixture",
        license="MIT",
        intended_use="Dashboard fixture only.",
    )
    BaselineRegistry(config).register_baseline(
        workspace_id=workspace.id,
        name="dashboard baseline",
        baseline_type="heuristic",
        code_available=True,
        implementation_path="code/src/baselines.py",
    )
    MetricRegistry(config).register_metric(workspace_id=workspace.id, name="false positive rate")
    manager = ExperimentWorkspaceManager(config)
    success_output = Path(workspace.root_dir) / "results" / "dashboard_metrics.json"
    success_output.write_text(
        json_dumps(
            {
                "metric_results": [
                    {
                        "metric_id": "false positive rate",
                        "value": 0.01,
                        "sample_size": 1000,
                        "confidence_interval": [0.0, 0.02],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    success_manifest = manager.create_manifest(
        workspace_id=workspace.id,
        run_type="smoke",
        run_name="dashboard-success",
        command="python code/src/run_experiment.py --config configs/smoke.json",
        expected_outputs=["results/dashboard_metrics.json"],
        random_seed=123,
    )
    success_execution = manager.record_execution(
        workspace_id=workspace.id,
        manifest_id=success_manifest.id,
        status="complete",
        returncode=0,
        stdout_text="sk-test-dashboard-secret",
        result_paths=[success_output],
    )
    failed_output = Path(workspace.root_dir) / "results" / "dashboard_failed_metrics.json"
    failed_output.write_text(
        '{"metric_results": [{"metric_id": "false positive rate", "value": 0.2, "sample_size": 10}]}', encoding="utf-8"
    )
    failed_manifest = manager.create_manifest(
        workspace_id=workspace.id,
        run_type="negative_control",
        run_name="dashboard-failed",
        command="python code/src/run_experiment.py --config configs/negative.json",
        expected_outputs=["results/dashboard_failed_metrics.json"],
        random_seed=123,
    )
    failed_execution = manager.record_execution(
        workspace_id=workspace.id,
        manifest_id=failed_manifest.id,
        status="failed",
        returncode=2,
        stdout_text="sk-test-dashboard-secret",
        stderr_text="failed without leaking secret",
        result_paths=[failed_output],
        failure_reason="Command exited with return code 2.",
    )
    ResultParser(config).parse_execution(success_execution.id)
    reports = Path(workspace.root_dir) / "reports"
    summary_path = reports / f"result_summary_{success_execution.id}.json"
    summary = gf_models.to_plain(ResultParser(config).load_or_parse_summary(success_execution.id))
    summary["metric_results"][0]["id"] = "metric-result-dashboard"
    summary["empirical_claims"][0]["id"] = "claim-dashboard"
    summary_path.write_text(json_dumps(summary), encoding="utf-8")
    ResultParser(config)._write_empirical_claim_ledger(  # noqa: SLF001
        workspace,
        [gf_models.from_dict(gf_models.EmpiricalClaim, summary["empirical_claims"][0])],
    )
    EmpiricalReviewBuilder(config).review_execution(success_execution.id)
    PaperPackageExporter(config).export_workspace_v2(workspace.id)
    return program.project.id, workspace.id, failed_execution.id


def json_dumps(payload) -> str:
    import json

    return json.dumps(payload, indent=2) + "\n"
