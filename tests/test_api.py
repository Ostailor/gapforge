from __future__ import annotations

import json
import sys
from pathlib import Path

from gapforge import api
from gapforge.config import GapForgeConfig
from gapforge.experiments.workspace import ExperimentWorkspaceManager
from gapforge.models import (
    BaselineCandidate,
    ExperimentProtocol,
    Gap,
    Paper,
    PaperNote,
    ReproducibilityChecklist,
    ResearchDirection,
    SearchRound,
    SourceCoverageReport,
)
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager


class HealthyApiSource:
    name = "Semantic Scholar"

    def search(self, query: str, *, max_results: int, sort: str, date_from: str | None, date_to: str | None):
        return [
            Paper(
                id=f"api-source-{index}",
                title=f"API source paper {index}",
                authors=["Ada"],
                abstract=f"Live-looking result for {query}.",
                year=2026,
                source=self.name,
            )
            for index in range(min(max_results, 2))
        ]


def test_api_create_project_and_run(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)

    project = api.create_project("Notebook Project", description="scripted workflow", config=config)
    state = api.create_run("low false positive collusion detection", project_id=project.project.id, config=config)

    loaded_project = api.get_project(project.project.id, config=config)
    assert state.run_id in loaded_project.run_ids
    assert api.get_state(state.run_id, config=config).topic.text == "low false positive collusion detection"


def test_api_add_pdf_and_parse_fulltext(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    state = api.create_run("pdf api workflow", config=config)
    pdf = tmp_path / "api-paper.pdf"
    pdf.write_bytes(_tiny_pdf("Abstract API paper. Results mention deployment false positives."))

    added = api.add_pdf(state.run_id, pdf, title="API PDF Paper", authors=["Ada"], year=2026, config=config)
    parsed = api.parse_fulltext(state.run_id, paper_id=added.paper.id, config=config)

    assert added.artifact.status == "available"
    assert parsed.sections
    assert parsed.sections[0].paper_id == added.paper.id


def test_api_mine_gaps_and_build_index(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    state = api.create_run("deployment limitation mining", config=config)
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(_tiny_pdf("Abstract A."))
    pdf_b.write_bytes(_tiny_pdf("Abstract B."))
    paper_a = api.add_pdf(state.run_id, pdf_a, title="Deployment A", config=config).paper
    paper_b = api.add_pdf(state.run_id, pdf_b, title="Deployment B", config=config).paper

    state = api.get_state(state.run_id, config=config)
    state.paper_notes.extend(
        [
            PaperNote(
                paper_id=paper_a.id,
                one_sentence_summary="A",
                stated_limitations=["Deployment false-positive behavior remains unresolved."],
            ),
            PaperNote(
                paper_id=paper_b.id,
                one_sentence_summary="B",
                stated_limitations=["Real-world deployment validation is missing."],
            ),
        ]
    )
    ResearchStateManager(config).save_run(state)

    mined = api.mine_gaps(state.run_id, config=config)
    manifest = api.build_index(run_id=state.run_id, config=config)

    assert mined.gaps
    assert any(gap.type == "deployment gap" for gap in mined.gaps)
    assert manifest.document_count > 0


def test_api_export_report_without_cli(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = api.create_run("report api workflow", config=config)

    result = api.export_report(state.run_id, config=config)

    assert result.path == Path(state.run_dir) / "final_report.md"
    assert result.path.exists()
    assert "GapForge Final Research Report" in result.path.read_text(encoding="utf-8")


def test_api_create_and_run_fake_campaign(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GAPFORGE_DISABLE_NETWORK", "1")
    config = GapForgeConfig.from_cwd(tmp_path)
    project = api.create_project("API Campaign Project", config=config)

    campaign = api.create_campaign(
        project.project.id,
        "low false positive campaign workflow",
        mode="fake_agent",
        agent_name="fake",
        model="fake",
        config=config,
    )
    action = api.campaign_next(campaign.campaign.id, config=config)
    result = api.run_campaign(campaign.campaign.id, mode="fake_agent", max_iterations=1, config=config)

    assert campaign.campaign.project_id == project.project.id
    assert action.decision_type
    assert result.decisions


def test_api_campaign_task_validate_and_import(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project = api.create_project("API Task Project", config=config)
    campaign = api.create_campaign(project.project.id, "campaign task import workflow", config=config)

    task = api.create_campaign_task(campaign.campaign.id, "campaign_stop_decision", config=config)
    outputs = task.path / "outputs"
    stop_patch = outputs / "stop_condition_patch.json"
    final_patch = outputs / "final_recommendation_patch.json"
    stop_patch.write_text(
        """{
  "stop_condition_patch": [
    {
      "reason": "not_ready_poor_coverage",
      "triggered": true,
      "evidence": ["api fixture"]
    }
  ],
  "public_reasoning_summary": "Stop because coverage is insufficient."
}
""",
        encoding="utf-8",
    )
    final_patch.write_text(
        """{
  "final_recommendation_patch": [
    {
      "recommendation": "no_direction_ready",
      "confidence": "low"
    }
  ],
  "public_reasoning_summary": "No recommendation is ready."
}
""",
        encoding="utf-8",
    )

    validation = api.validate_campaign_output(campaign.campaign.id, task.task_id, [stop_patch, final_patch], config=config)
    imported = api.import_campaign_output(campaign.campaign.id, task.task_id, [stop_patch, final_patch], config=config)
    attestation = api.attest_agent_run(
        task.task_id,
        agent_name="codex",
        model="gpt-5.4",
        execution_method="task_pack",
        attester="tester",
        config=config,
    )

    assert validation.status == "valid"
    assert imported.status == "applied"
    assert attestation.accepted_as_actual_run is True
    assert api.campaign_acceptance(campaign.campaign.id, config=config).accepted is False


def test_api_acceptance_fails_without_real_attestation(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project = api.create_project("API Acceptance Project", config=config)
    campaign = api.create_campaign(
        project.project.id,
        "acceptance without attestation",
        mode="codex_task_pack",
        agent_name="codex",
        model="gpt-5.4",
        config=config,
    )

    reviewed = api.review_campaign(campaign.campaign.id, accept=True, reviewer="tester", config=config)

    assert reviewed.review.accepted is True
    assert reviewed.summary.accepted is False
    assert "Missing human attestation" in " ".join(reviewed.summary.blocking_failures)


def test_api_v4_release_gate(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)

    result = api.v4_release_gate(config=config)

    assert result.passed is False
    assert result.blockers


def test_api_create_draft_and_traceability_manuscript(tmp_path: Path) -> None:
    config, manuscript_id, execution_id, artifact_ids = _api_manuscript_fixture(tmp_path)

    drafted = api.draft_manuscript(
        manuscript_id,
        sections=["abstract", "introduction", "related_work", "method", "experiments", "results", "limitations", "conclusion"],
        section_links={
            "related_work": {"source_paper_ids": ["paper-api"]},
            "results": {"source_result_ids": [execution_id], "source_artifact_ids": artifact_ids},
        },
        claim_uses=[
            {
                "section_type": "related_work",
                "claim_id": "claim-api-background",
                "claim_text": "Prior work motivates scriptable manuscript workflows.",
                "use_type": "background",
                "support_status": "supported",
                "evidence_locators": ["paper-api:introduction:p1"],
            },
            {
                "section_type": "results",
                "claim_id": "claim-api-result",
                "claim_text": "The API fixture records an artifact-backed result.",
                "use_type": "result",
                "support_status": "supported",
            },
        ],
        status="approved",
        config=config,
    )
    bibliography = api.build_bibliography(manuscript_id, config=config)
    rendered = api.render_manuscript(manuscript_id, config=config)
    traceability = api.run_traceability_check(manuscript_id, config=config)

    assert drafted.manuscript.id == manuscript_id
    assert len(drafted.sections) == 8
    assert bibliography.entries[0].paper_id == "paper-api"
    assert "API Manuscript" in rendered
    assert traceability.blocking_issues == []
    assert traceability.supported_claim_count == 2


def test_api_submission_package_and_v8_release_gate(tmp_path: Path) -> None:
    config, manuscript_id, execution_id, artifact_ids = _api_manuscript_fixture(tmp_path)
    _write_v8_api_prerequisites(config)
    api.draft_manuscript(
        manuscript_id,
        sections=["abstract", "introduction", "related_work", "method", "experiments", "results", "limitations", "conclusion"],
        section_links={
            "related_work": {"source_paper_ids": ["paper-api"]},
            "results": {"source_result_ids": [execution_id], "source_artifact_ids": artifact_ids},
        },
        claim_uses=[
            {
                "section_type": "related_work",
                "claim_id": "claim-api-background",
                "claim_text": "Prior work motivates scriptable manuscript workflows.",
                "use_type": "background",
                "support_status": "supported",
                "evidence_locators": ["paper-api:introduction:p1"],
            },
            {
                "section_type": "results",
                "claim_id": "claim-api-result",
                "claim_text": "The API fixture records an artifact-backed result.",
                "use_type": "result",
                "support_status": "supported",
            },
        ],
        status="approved",
        config=config,
    )
    api.build_bibliography(manuscript_id, config=config)
    api.set_venue(manuscript_id, "generic_conference", config=config)
    assets = api.generate_manuscript_assets(manuscript_id, table_types=["result_table"], figure_types=["metric_plot"], config=config)
    anonymization = api.anonymize_manuscript(manuscript_id, config=config)
    artifact_package = api.create_artifact_eval_package(manuscript_id, config=config)
    checklist = api.submission_checklist(manuscript_id, config=config)
    review = api.manuscript_review(manuscript_id, config=config)
    revision = api.rebuttal_plan(manuscript_id, config=config)
    package = api.submission_package(manuscript_id, "review", config=config)
    gate = api.v8_release_gate(write_report=True, config=config)

    assert assets.tables and assets.figures
    assert anonymization.status == "pass"
    assert artifact_package.status == "review_ready"
    assert checklist.blocking_issues == []
    assert review.manuscript_id == manuscript_id
    assert revision.manuscript_id == manuscript_id
    assert package.files
    assert gate.requirements["manuscript_project_created"] is True
    assert gate.requirements["submission_package_exported"] is True


def test_api_source_health_with_mocked_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GAPFORGE_DISABLE_NETWORK", raising=False)
    config = GapForgeConfig.from_cwd(tmp_path)

    result = api.source_health("low false positive collusion", profile="generic", sources=[HealthyApiSource()], config=config)

    assert not isinstance(result, list)
    assert "Semantic Scholar" in result.usable_sources
    assert result.source_health_checks[0].result_count == 2


def test_api_search_strategy(tmp_path: Path) -> None:
    strategy = api.plan_search_strategy("low false positive collusion detection", "ai_safety", config=GapForgeConfig.from_cwd(tmp_path))

    assert strategy.primary_queries
    assert strategy.closest_prior_work_queries
    assert "openreview" in strategy.expected_sources


def test_api_prior_work_recall(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = api.create_run("low false positive collusion detection", config=config)
    state.papers = [
        Paper(id="support", title="Support paper", authors=["Ada"], abstract="A support paper.", year=2026),
        Paper(
            id="candidate",
            title="Different prior monitoring work",
            authors=["Grace"],
            abstract="Studies monitoring, not collusion.",
            year=2025,
        ),
    ]
    state.gaps = [
        Gap(
            id="gap-api",
            title="Low-FPR collusion detection gap",
            description="Need low false-positive collusion detection.",
            supporting_paper_ids=["support"],
        )
    ]
    state.search_rounds = [
        SearchRound(id="round-initial", strategy_id="strategy-api", round_type="initial", status="complete"),
        SearchRound(id="round-novelty", strategy_id="strategy-api", round_type="novelty", status="complete"),
        SearchRound(id="round-benchmark", strategy_id="strategy-api", round_type="benchmark", status="complete"),
        SearchRound(id="round-survey", strategy_id="strategy-api", round_type="survey", status="complete"),
    ]
    state.source_coverage = SourceCoverageReport(run_id=state.run_id, topic=state.topic.text, confidence="medium")
    ResearchStateManager(config).save_run(state)

    assessment = api.prior_work_recall(run_id=state.run_id, gap_id="gap-api", config=config)
    reloaded = api.get_state(state.run_id, config=config)

    assert not isinstance(assessment, list)
    assert assessment.target_id == "gap-api"
    assert reloaded.prior_work_recall_assessments


def test_api_canonicalize_papers(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = api.create_run("canonical API", config=config)
    state.papers = [
        Paper(id="paper-a", title="Same Paper", authors=["Ada"], year=2026, doi="10.1000/test", abstract="Short abstract."),
        Paper(
            id="paper-b",
            title="Same Paper",
            authors=["Ada"],
            year=2026,
            doi="https://doi.org/10.1000/test",
            abstract="Longer richer abstract.",
        ),
    ]
    ResearchStateManager(config).save_run(state)

    identities, decisions = api.canonicalize_papers(run_id=state.run_id, config=config)

    assert identities
    assert decisions
    assert len(api.get_state(state.run_id, config=config).papers) == 1


def test_api_v5_release_gate(tmp_path: Path) -> None:
    result = api.v5_release_gate(config=GapForgeConfig.from_cwd(tmp_path))

    assert result.passed is False
    assert result.blockers


def test_api_generate_code_tasks(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project = api.create_project("API Code Task Project", config=config)
    campaign = api.create_campaign(project.project.id, "code task campaign", config=config)
    program = ProjectMemoryManager(config).load_project(project.project.id)
    program.research_directions.append(
        ResearchDirection(
            id="direction-api-ready",
            project_id=project.project.id,
            title="API ready direction",
            maturity="experiment_ready",
        )
    )
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-api-ready",
            direction_id="direction-api-ready",
            linked_experiment_plan_id="experiment-api",
            objective="Measure low false positive performance.",
            hypothesis="A calibrated detector lowers false positives.",
            datasets=["synthetic placeholder dataset"],
            baselines=[BaselineCandidate(paper_id="paper-api", baseline_name="prior baseline", why_required="Required comparator.")],
            metrics=["false positive rate"],
            statistical_tests=["binomial confidence interval"],
            power_or_sample_size_notes="Use enough negative examples for tight FPR intervals.",
            ablations=["without calibration"],
            implementation_modules=["detector", "metrics"],
            expected_artifacts=["metrics report"],
            evaluation_script_outline=["load data", "run baseline", "compute FPR"],
            failure_modes=["baseline outperforms detector"],
            reproducibility_checklist=ReproducibilityChecklist(
                dataset_versioning="pin fixture version",
                environment_spec="pyproject",
                logging_plan="write JSONL metrics",
                metric_definitions=["FPR"],
                negative_controls=["random labels"],
                error_analysis_plan="inspect false positives",
            ),
            compute_budget="local smoke",
            timeline=["one day scaffold"],
        )
    )
    ProjectMemoryManager(config).save_project(program)

    tasks = api.generate_code_tasks(campaign.campaign.id, "direction-api-ready", config=config)

    assert tasks
    assert {task.task_type for task in tasks}


def test_api_create_experiment_workspace(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project = _api_experiment_project(config)

    workspace = api.create_experiment_workspace(project.project.id, "direction-api-experiment", config=config)

    assert workspace.project_id == project.project.id
    assert workspace.direction_id == "direction-api-experiment"
    assert Path(workspace.root_dir).exists()


def test_api_run_fixture_experiment_and_parse_results(tmp_path: Path) -> None:
    config, workspace_id, dataset_id, baseline_id, metric_id = _api_experiment_workspace(tmp_path)

    run_result = _run_api_fixture_experiment(config, workspace_id, dataset_id, baseline_id, metric_id)
    summary = api.parse_results(run_result.execution.id, config=config)
    analysis = api.analyze_results(execution_id=run_result.execution.id, config=config)
    reproducibility = api.reproducibility_check(execution_id=run_result.execution.id, config=config)
    review = api.empirical_review(execution_id=run_result.execution.id, config=config)

    assert run_result.execution.status == "complete"
    assert summary.metric_results
    assert summary.empirical_claims
    assert analysis.metric_analyses
    assert reproducibility.status in {"pass", "warning", "fail"}
    assert review.reviewer_reviews


def test_api_export_paper_package_v2(tmp_path: Path) -> None:
    config, workspace_id, dataset_id, baseline_id, metric_id = _api_experiment_workspace(tmp_path)
    run_result = _run_api_fixture_experiment(config, workspace_id, dataset_id, baseline_id, metric_id)
    api.parse_results(run_result.execution.id, config=config)
    api.analyze_results(execution_id=run_result.execution.id, config=config)
    api.reproducibility_check(execution_id=run_result.execution.id, config=config)
    api.empirical_review(execution_id=run_result.execution.id, config=config)

    package = api.export_paper_package_v2(workspace_id=workspace_id, config=config)
    gate = api.v6_release_gate(config=config)

    assert package.id == f"paper-package-v2-{workspace_id}"
    assert "result_summary.md" in package.files
    assert gate.passed is False
    assert gate.blockers


def test_api_register_benchmark_suite_and_download_dataset(tmp_path: Path) -> None:
    config, workspace_id, dataset_id, baseline_id, metric_id = _api_experiment_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)

    benchmark = api.register_benchmark(
        workspace_id,
        "API fixture benchmark",
        description="Fixture benchmark through the API.",
        domain="fixture",
        task_type="detection",
        dataset_ids=[dataset_id],
        baseline_ids=[baseline_id],
        metric_ids=[metric_id],
        expected_splits=["test"],
        evaluation_protocol="Report false positive rate.",
        config=config,
    )
    suite = api.create_benchmark_suite(
        workspace.project_id,
        "API benchmark suite",
        benchmark_ids=[benchmark.id],
        required_tasks=["detection"],
        config=config,
    )
    download = api.download_dataset(dataset_id, config=config)
    comparison = api.benchmark_compare(workspace_id, benchmark.id, config=config)

    assert benchmark.dataset_ids == [dataset_id]
    assert suite.benchmark_ids == [benchmark.id]
    assert download.status in {"manual_required", "skipped", "downloaded", "failed"}
    assert comparison.benchmark_id == benchmark.id


def test_api_submit_fixture_job_and_create_sweep(tmp_path: Path) -> None:
    config, workspace_id, dataset_id, baseline_id, metric_id = _api_experiment_workspace(tmp_path)
    manifest = api.create_experiment_manifest(
        workspace_id,
        run_type="smoke",
        run_name="api-job",
        dataset_ids=[dataset_id],
        baseline_ids=[baseline_id],
        metric_ids=[metric_id],
        command=f"{sys.executable} -c 'print(1)'",
        expected_outputs=[],
        random_seed=123,
        config=config,
    )

    job = api.submit_job(workspace_id, manifest.id, config=config)
    sweep = api.create_sweep(
        workspace_id,
        manifest.id,
        {"metric.threshold": ["0.1", "0.2"]},
        name="api sweep",
        config=config,
    )
    environments = api.compute_status(config=config)

    assert job.status == "queued"
    assert job.manifest_id == manifest.id
    assert len(sweep.generated_manifest_ids) == 2
    assert any(environment.environment_type == "local" for environment in environments)


def test_api_aggregate_results_and_error_analysis(tmp_path: Path) -> None:
    config, workspace_id, dataset_id, baseline_id, metric_id = _api_experiment_workspace(tmp_path)
    run_result = _run_api_fixture_experiment(config, workspace_id, dataset_id, baseline_id, metric_id)
    api.parse_results(run_result.execution.id, config=config)

    aggregates = api.aggregate_results(workspace_id, include_smoke=True, config=config)
    error_report = api.run_error_analysis(run_result.execution.id, config=config)

    assert aggregates
    assert aggregates[0].workspace_id == workspace_id
    assert error_report.execution_id == run_result.execution.id
    assert "No predictions artifact" in " ".join(error_report.limitations)


def test_api_export_verify_replication_and_reproduce(tmp_path: Path) -> None:
    config, workspace_id, dataset_id, baseline_id, metric_id = _api_experiment_workspace(tmp_path)
    run_result = _run_api_fixture_experiment(config, workspace_id, dataset_id, baseline_id, metric_id)
    api.parse_results(run_result.execution.id, config=config)

    package = api.export_replication_package(workspace_id, config=config)
    package_dir = Path(package.manifest_path).parent
    verification = api.verify_replication_package(package_dir, config=config)
    reproduction = api.reproduce_package(package_dir, dry_run=True, config=config)

    assert package.workspace_id == workspace_id
    assert verification.package_id == package.id
    assert verification.status in {"pass", "warning", "fail"}
    assert reproduction.package_id == package.id
    assert reproduction.status == "planned"


def test_api_v7_release_gate(tmp_path: Path) -> None:
    result = api.v7_release_gate(config=GapForgeConfig.from_cwd(tmp_path))

    assert result.passed is False
    assert result.blockers


def _api_experiment_project(config: GapForgeConfig):
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("API Experiment Project")
    program.research_directions.append(
        ResearchDirection(
            id="direction-api-experiment",
            project_id=program.project.id,
            title="API experiment direction",
            summary="Fixture direction for scriptable v0.6 workflow tests.",
            maturity="experiment_ready",
        )
    )
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-api-experiment",
            direction_id="direction-api-experiment",
            linked_experiment_plan_id="experiment-api",
            objective="Exercise the v0.6 API experiment execution workflow.",
            hypothesis="A fixture command emits artifact-backed metric results.",
            datasets=["api fixture dataset"],
            metrics=["false positive rate"],
            statistical_tests=["binomial confidence interval"],
            expected_artifacts=["metrics.json"],
        )
    )
    project_manager.save_project(program)
    return program


def _api_experiment_workspace(tmp_path: Path) -> tuple[GapForgeConfig, str, str, str, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    project = _api_experiment_project(config)
    workspace = api.create_experiment_workspace(project.project.id, "direction-api-experiment", config=config)
    dataset_path = Path(workspace.root_dir) / "data" / "api_fixture.csv"
    dataset_path.write_text("id,split,label\n1,test,0\n2,test,1\n", encoding="utf-8")
    dataset = api.register_dataset(
        workspace.id,
        "api fixture examples",
        dataset_path,
        dataset_type="fixture",
        license="MIT",
        intended_use="API fixture only.",
        config=config,
    )
    baseline = api.register_baseline(
        workspace.id,
        "api heuristic baseline",
        baseline_type="heuristic",
        code_available=True,
        implementation_path="code/src/baselines.py",
        config=config,
    )
    metric = api.register_metric(workspace.id, "false positive rate", config=config)
    api.scaffold_experiment_code(workspace.id, config=config)
    return config, workspace.id, dataset.id, baseline.id, metric.id


def _run_api_fixture_experiment(
    config: GapForgeConfig,
    workspace_id: str,
    dataset_id: str,
    baseline_id: str,
    metric_id: str,
):
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    output = Path(workspace.root_dir) / "results" / "api_metrics.json"
    script = Path(workspace.root_dir) / "code" / "write_api_metrics.py"
    payload = {
        "metric_results": [
            {
                "metric_id": metric_id,
                "dataset_id": dataset_id,
                "baseline_id": baseline_id,
                "value": 0.01,
                "sample_size": 1000,
                "confidence_interval": [0.0, 0.02],
            }
        ]
    }
    script.write_text(
        f"from pathlib import Path\nPath({str(output)!r}).write_text({json.dumps(json.dumps(payload))} + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest = api.create_experiment_manifest(
        workspace_id,
        run_type="smoke",
        run_name="api-smoke",
        dataset_ids=[dataset_id],
        baseline_ids=[baseline_id],
        metric_ids=[metric_id],
        command=f"{sys.executable} {script}",
        expected_outputs=["results/api_metrics.json"],
        random_seed=123,
        config=config,
    )
    return api.run_experiment(workspace_id, manifest_id=manifest.id, config=config)


def _api_manuscript_fixture(tmp_path: Path) -> tuple[GapForgeConfig, str, str, list[str]]:
    config, workspace_id, dataset_id, baseline_id, metric_id = _api_experiment_workspace(tmp_path)
    workspace = ExperimentWorkspaceManager(config).load_workspace(workspace_id)
    run = api.create_run("api manuscript evidence", project_id=workspace.project_id, config=config)
    run.papers = [
        Paper(
            id="paper-api",
            title="Scriptable Manuscript Workflows",
            authors=["Ada Lovelace"],
            abstract="Known paper evidence for API manuscript tests.",
            year=2026,
            venue="APIConf",
            doi="10.1000/api-manuscript",
        )
    ]
    ResearchStateManager(config).save_run(run)
    result = _run_api_fixture_experiment(config, workspace_id, dataset_id, baseline_id, metric_id)
    api.parse_results(result.execution.id, config=config)
    api.export_replication_package(workspace_id, config=config)
    manuscript = api.create_manuscript(
        workspace.project_id,
        workspace.direction_id,
        workspace.id,
        "API Manuscript",
        config=config,
    )
    return config, manuscript.manuscript.id, result.execution.id, result.execution.result_artifact_ids


def _write_v8_api_prerequisites(config: GapForgeConfig) -> None:
    release_dir = config.data_dir / "release_gate"
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / "deterministic_ci.json").write_text('{"passed": true}\n', encoding="utf-8")
    (release_dir / "v0.7_latest.json").write_text('{"passed": true, "status": "pass"}\n', encoding="utf-8")


def _tiny_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n",
        b"4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n",
        b"5 0 obj<< /Length " + str(len(stream)).encode() + b" >>stream\n" + stream + b"\nendstream\nendobj\n",
    ]
    body = b"%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body += obj
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        body += f"{offset:010d} 00000 n \n".encode()
    body += f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return body
