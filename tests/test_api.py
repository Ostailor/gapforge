from __future__ import annotations

from pathlib import Path

from gapforge import api
from gapforge.config import GapForgeConfig
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
