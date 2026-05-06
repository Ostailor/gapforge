from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gapforge.campaigns import CampaignManager
from gapforge.campaigns.acceptance import campaign_task_attestation_status, create_campaign_actual_run_attestation
from gapforge.campaigns.context_builder import build_task_context
from gapforge.campaigns.controller import CampaignController
from gapforge.campaigns.import_workflow import validate_import_all
from gapforge.campaigns.importer import CampaignOutputImporter
from gapforge.campaigns.novelty_loop import CampaignNoveltyLoop
from gapforge.campaigns.outputs import import_campaign_outputs, validate_campaign_outputs
from gapforge.campaigns.review import CampaignReviewManager
from gapforge.campaigns.reviewer_loop import CampaignReviewerLoop
from gapforge.campaigns.rollback import rollback_import
from gapforge.campaigns.search_agent import CampaignSearchAgent, validate_search_request
from gapforge.campaigns.task_packs import create_campaign_task_pack
from gapforge.config import GapForgeConfig
from gapforge.directions.maturation import DirectionMaturationManager
from gapforge.experiment_code import ExperimentCodeTaskGenerator, ExperimentRepoScaffolder
from gapforge.models import (
    AgentSearchRequest,
    BaselineCandidate,
    CampaignImportRecord,
    Claim,
    EvidenceSpan,
    ExperimentProtocol,
    Gap,
    GapEvidenceMatrix,
    GapEvidenceRow,
    HumanReviewRecord,
    NoveltyDossier,
    Paper,
    PaperNote,
    PaperSection,
    RejectedIdea,
    RelatedWorkMatrix,
    ResearchDirection,
    ReviewQueue,
    ReviewQueueItem,
    SourceCoverageReport,
)
from gapforge.project_memory import PROJECT_ARTIFACTS, ProjectMemoryManager
from gapforge.retrieval import build_project_index
from gapforge.state import ResearchStateManager


def test_create_project_writes_project_memory_files(tmp_path: Path) -> None:
    manager = ProjectMemoryManager(GapForgeConfig.from_cwd(tmp_path))

    program = manager.create_project("Low FPR Collusion Program")

    project_dir = Path(program.project.root_dir)
    assert project_dir.exists()
    assert project_dir.parent == tmp_path / "projects"
    assert (project_dir / "runs").exists()
    assert (project_dir / "reports").exists()
    for artifact in PROJECT_ARTIFACTS:
        assert (project_dir / artifact).exists(), artifact

    loaded = manager.load_project(program.project.id)
    assert loaded.project.name == "Low FPR Collusion Program"
    assert loaded.corpus_papers == []


def test_gapforge_project_root_env_override(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    custom_root = tmp_path / "custom-projects"
    monkeypatch.setenv("GAPFORGE_PROJECT_ROOT", str(custom_root))

    config = GapForgeConfig.from_cwd(tmp_path)
    ProjectMemoryManager(config).create_project("Custom Root Project")

    assert config.project_root == custom_root
    assert any(custom_root.iterdir())


def test_attach_run_and_sync_deduplicates_corpus_papers(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    run_a = state_manager.create_run("collusion detection")
    run_b = state_manager.create_run("agent collusion")
    run_a.papers.append(
        Paper(
            id="paper-a",
            title="Shared Collusion Detection Benchmark",
            authors=["A"],
            abstract="A benchmark.",
            year=2024,
            doi="10.1234/shared",
            source="fixture",
        )
    )
    run_b.papers.append(
        Paper(
            id="paper-b",
            title="Shared Collusion Detection Benchmark",
            authors=["B"],
            abstract="Same DOI.",
            year=2025,
            doi="10.1234/SHARED",
            source="fixture",
        )
    )
    state_manager.save_run(run_a)
    state_manager.save_run(run_b)
    program = project_manager.create_project("Collusion Memory")

    project_manager.attach_run(program.project.id, run_a.run_id)
    project_manager.attach_run(program.project.id, run_b.run_id)
    synced = project_manager.sync_project_memory(program.project.id)

    assert synced.run_ids == [run_a.run_id, run_b.run_id]
    assert len(synced.corpus_papers) == 1
    corpus = synced.corpus_papers[0]
    assert corpus.canonical_doi == "10.1234/shared"
    assert set(corpus.seen_run_ids) == {run_a.run_id, run_b.run_id}
    assert set(corpus.source_paper_ids) == {"paper-a", "paper-b"}
    assert (Path(synced.project.root_dir) / "runs" / f"{run_a.run_id}.json").exists()


def test_sync_claims_gaps_rejected_ideas_and_human_decisions(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    state = state_manager.create_run("claim memory")
    state.papers.append(Paper(id="paper-1", title="Paper One", authors=[], abstract="Abstract", year=2026, source="fixture"))
    state.claims.append(
        Claim(
            id="claim-1",
            text="False positive rate remains a deployment blocker.",
            type="gap",
            status="supported",
            confidence="medium",
            source_paper_ids=["paper-1"],
        )
    )
    state.gaps.append(
        Gap(
            id="gap-1",
            title="Deployment false-positive gap",
            description="Systems are rarely evaluated for operator workload at low false-positive rates.",
            supporting_paper_ids=["paper-1"],
            confidence="medium",
            novelty_status="unchecked",
        )
    )
    state.rejected_ideas.append(RejectedIdea(id="rej-1", idea="Duplicate benchmark idea", reason="Already covered by prior work."))
    state.human_reviews.append(
        HumanReviewRecord(
            id="review-1",
            object_type="gap",
            object_id="gap-1",
            action="reject",
            note="Not actionable enough.",
            reviewer="researcher",
        )
    )
    state.human_reviews.append(
        HumanReviewRecord(
            id="review-2",
            object_type="gap",
            object_id="gap-1",
            action="lock",
            note="Preserve human rejection.",
            reviewer="researcher",
        )
    )
    state_manager.save_run(state)
    program = project_manager.create_project("Claim Memory")
    project_manager.attach_run(program.project.id, state.run_id)

    synced = project_manager.sync_project_memory(program.project.id)
    records = synced.memory_records

    assert any(record.record_type == "claim" and "False positive" in record.text for record in records)
    assert any(record.record_type == "gap" and "Deployment" in record.text for record in records)
    assert any(record.record_type == "rejected_idea" and record.status == "rejected" for record in records)
    assert any(record.record_type == "decision" and record.status == "rejected" for record in records)
    assert any(record.record_type == "decision" and "lock gap:gap-1" in record.text for record in records)
    direction = synced.research_directions[0]
    assert direction.maturity == "rejected"
    assert direction.readiness_score == 0.0

    reloaded = project_manager.load_project(program.project.id)
    assert any(record.record_type == "decision" for record in reloaded.memory_records)


def test_project_report_renders_summary(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    state = state_manager.create_run("report memory")
    state.papers.append(Paper(id="paper-1", title="Report Paper", authors=[], abstract="", year=2026, source="fixture"))
    state.rejected_ideas.append(RejectedIdea(id="rej-1", idea="Weak idea", reason="Insufficient novelty."))
    state_manager.save_run(state)
    program = project_manager.create_project("Report Project")
    project_manager.attach_run(program.project.id, state.run_id)
    synced = project_manager.sync_project_memory(program.project.id)

    report_path = project_manager.write_project_report(synced)

    text = report_path.read_text(encoding="utf-8")
    assert "GapForge Project Report" in text
    assert "Corpus papers: 1" in text
    assert "Weak idea" in text
    assert (Path(synced.project.root_dir) / "reports" / "project_report.md").exists()


def test_create_and_load_campaign(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Campaign Project")
    manager = CampaignManager(config)

    campaign_state = manager.create_campaign(
        "low false positive collusion detection",
        project_id=program.project.id,
        mode="codex_task_pack",
        agent_name="codex",
        model="gpt-5.4",
        source_profile="ai_safety",
    )
    loaded = manager.load_campaign_state(campaign_state.campaign.id)
    project = ProjectMemoryManager(config).load_project(program.project.id)

    assert loaded.campaign.topic == "low false positive collusion detection"
    assert loaded.campaign.mode == "codex_task_pack"
    assert loaded.budget is not None
    assert (Path(program.project.root_dir) / "campaigns" / loaded.campaign.id / "campaign.json").exists()
    assert project.campaigns[0].id == loaded.campaign.id


def test_campaign_attach_decide_milestone_stop_resume(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Campaign Lifecycle Project")
    manager = CampaignManager(config)
    campaign_state = manager.create_campaign("monitor evasion", project_id=program.project.id)

    campaign_state = manager.attach_run(campaign_state.campaign.id, "run-1")
    campaign_state = manager.attach_task(campaign_state.campaign.id, "task-1", run_id="run-1")
    campaign_state = manager.add_decision(
        campaign_state.campaign.id,
        decision_type="ask_codex",
        reason="Need closest-prior-work comparison.",
        evidence=["source coverage incomplete"],
    )
    campaign_state = manager.add_milestone(
        campaign_state.campaign.id,
        milestone_type="coverage_ready",
        linked_artifacts=["source_coverage.md"],
        notes="Enough for mapping only.",
    )
    stopped = manager.stop_campaign(campaign_state.campaign.id, reason="Waiting for human review.")
    resumed = manager.resume_campaign(campaign_state.campaign.id)

    assert "run-1" in resumed.campaign.run_ids
    assert "task-1" in resumed.campaign.task_ids
    assert stopped.stop_conditions[0].triggered is True
    assert resumed.campaign.status == "running"
    assert len(resumed.decisions) >= 2
    assert any(milestone.milestone_type == "coverage_ready" for milestone in resumed.milestones)


def test_project_report_includes_campaigns(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Campaign Report Project")
    campaign_state = CampaignManager(config).create_campaign("agent collusion", project_id=program.project.id)

    report_path = ProjectMemoryManager(config).write_project_report(ProjectMemoryManager(config).load_project(program.project.id))
    report = report_path.read_text(encoding="utf-8")

    assert "## Campaigns" in report
    assert campaign_state.campaign.id in report


def test_campaign_task_pack_generation_and_rules(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Campaign Task Pack Project")
    campaign_state = CampaignManager(config).create_campaign("novelty review topic", project_id=program.project.id)

    pack_dir = create_campaign_task_pack(config, campaign_state.campaign.id, "novelty_reviewer")
    loaded = CampaignManager(config).load_campaign_state(campaign_state.campaign.id)

    assert (pack_dir / "CAMPAIGN_TASK.md").exists()
    assert (pack_dir / "campaign_context.json").exists()
    assert (pack_dir / "expected_outputs.json").exists()
    assert (pack_dir / "validation_rules.md").exists()
    assert (pack_dir / "evidence_rules.md").exists()
    assert (pack_dir / "novelty_rules.md").exists()
    assert (pack_dir / "stop_rules.md").exists()
    assert "never invent citations" in (pack_dir / "CAMPAIGN_TASK.md").read_text(encoding="utf-8").lower()
    assert loaded.campaign.task_ids
    assert loaded.steps[-1].task_spec_id == loaded.campaign.task_ids[-1]
    assert (pack_dir / "task_context.json").exists()
    manifest = json.loads((pack_dir / "input_manifest.json").read_text(encoding="utf-8"))
    assert "task_context.json" in manifest["artifact_links"]


def test_task_context_includes_evidence_spans(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_context_fixture(tmp_path)

    context = build_task_context(config, campaign_id, "novelty_reviewer", budget="medium")

    assert context["relevant_evidence_spans"]
    assert context["relevant_evidence_spans"][0]["id"] == "evidence-relevant"
    assert "evidence-relevant" in context["allowed_object_ids"]["evidence_span_ids"]
    assert "paper-relevant:Results:p4" in context["relevant_evidence_spans"][0]["locator"]


def test_task_context_excludes_irrelevant_papers(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_context_fixture(tmp_path)

    context = build_task_context(config, campaign_id, "novelty_reviewer", budget="small")
    selected_ids = {paper["id"] for paper in context["top_relevant_papers"]}

    assert "paper-relevant" in selected_ids
    assert "paper-irrelevant" not in selected_ids


def test_task_context_budget_respected(tmp_path: Path) -> None:
    config, campaign_id, run_id = _campaign_context_fixture(tmp_path, long_text=True)
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(run_id)
    for index in range(12):
        state.paper_sections.append(
            PaperSection(
                id=f"extra-section-{index}",
                paper_id="paper-relevant",
                title=f"Extra {index}",
                section_type="discussion",
                text=("low false positive collusion detection evidence " * 80),
            )
        )
    state_manager.save_run(state)

    context = build_task_context(config, campaign_id, "gap_synthesis", budget="small")

    assert context["context_budget"]["actual_chars"] <= context["context_budget"]["max_chars"] * 1.2
    assert len(context["relevant_sections"]) <= context["context_budget"]["max_sections"]


def test_task_context_limited_flag_appears(tmp_path: Path) -> None:
    config, campaign_id, run_id = _campaign_context_fixture(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.load_run(run_id)
    for index in range(10):
        state.evidence_spans.append(
            EvidenceSpan(
                id=f"extra-evidence-{index}",
                paper_id="paper-relevant",
                section_id="section-relevant-results",
                quote=f"low false positive collusion detection evidence {index}",
                locator=f"paper-relevant:Results:p{index + 5}",
                evidence_type="result",
                confidence="medium",
            )
        )
    state_manager.save_run(state)

    context = build_task_context(config, campaign_id, "novelty_reviewer", budget="small")

    assert context["context_limited"] is True
    assert len(context["relevant_evidence_spans"]) == context["context_budget"]["max_evidence_spans"]


def test_novelty_task_context_includes_closest_prior_candidates(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_context_fixture(tmp_path)

    context = build_task_context(config, campaign_id, "novelty_reviewer", budget="small")
    prior_ids = {candidate["id"] for candidate in context["closest_prior_candidates"] if candidate.get("id")}

    assert "paper-relevant" in prior_ids


def test_task_context_cli_builds_and_inspects(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_context_fixture(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    built = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "build-task-context",
            "--campaign-id",
            campaign_id,
            "--task-type",
            "novelty_reviewer",
            "--budget",
            "small",
        ],
        cwd=config.root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert built.returncode == 0, built.stderr
    assert Path(built.stdout.strip()).exists()

    pack = create_campaign_task_pack(config, campaign_id, "novelty_reviewer")
    inspected = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "inspect-task-context", "--task-id", pack.name],
        cwd=config.root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert inspected.returncode == 0, inspected.stderr
    assert json.loads(inspected.stdout)["task_type"] == "novelty_reviewer"


def test_campaign_agent_search_requests_execute_with_fake_source(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Agent Search Project")
    campaign = CampaignManager(config).create_campaign(
        "low false positive collusion detection",
        project_id=program.project.id,
        source_profile="generic",
    )
    search_agent = CampaignSearchAgent(config, sources=[_FixtureSearchSource("Semantic Scholar")])

    proposed = search_agent.propose_searches(campaign.campaign.id)
    executed = search_agent.execute_searches(campaign.campaign.id)
    loaded = CampaignManager(config).load_campaign_state(campaign.campaign.id)
    run = ResearchStateManager(config).load_run(loaded.campaign.run_ids[0])

    assert proposed.validation_status in {"valid", "partial"}
    assert executed.validation_status == "executed"
    assert run.search_queries
    assert run.source_coverage is not None
    assert "Semantic Scholar" in run.source_coverage.searched_sources
    assert run.paper_triage is not None
    assert (Path(run.run_dir) / "retrieval" / "manifest.json").exists()


def test_campaign_invalid_search_request_rejected(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Invalid Agent Search Project")
    campaign_state = CampaignManager(config).create_campaign("low false positive collusion detection", project_id=program.project.id)
    request = AgentSearchRequest(
        id="bad-search",
        campaign_id=campaign_state.campaign.id,
        query="asdf",
        purpose="novelty",
        source_profile="generic",
        target_sources=["Semantic Scholar"],
        reason="",
    )

    issues = validate_search_request(request, campaign_state, available_sources=["Semantic Scholar"])

    assert "query is too short" in issues
    assert any("nonsense" in issue for issue in issues)
    assert "request must explain the coverage, gap, or novelty reason" in issues


def test_campaign_search_records_update_coverage(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Coverage Search Project")
    campaign = CampaignManager(config).create_campaign("monitor evasion benchmark", project_id=program.project.id, source_profile="generic")
    search_agent = CampaignSearchAgent(config, sources=[_FixtureSearchSource("Semantic Scholar")])

    search_agent.execute_searches(campaign.campaign.id)
    status = search_agent.status(campaign.campaign.id)
    loaded = CampaignManager(config).load_campaign_state(campaign.campaign.id)
    run = ResearchStateManager(config).load_run(loaded.campaign.run_ids[0])

    assert status["executed_count"] >= 1
    assert run.source_coverage is not None
    assert run.source_coverage.query_records[0].result_paper_ids
    assert run.coverage_stopping_assessment is not None
    assert run.coverage_stopping_assessment.recommended_queries


def test_campaign_novelty_stays_unknown_when_required_searches_pending(tmp_path: Path) -> None:
    config, campaign_id, run_id = _campaign_context_fixture(tmp_path)
    state_manager = ResearchStateManager(config)
    run = state_manager.load_run(run_id)
    run.novelty_dossiers[0].verdict = "pursue"
    run.novelty_dossiers[0].novelty_strength = "strong"
    run.novelty_dossiers[0].confidence = "high"
    state_manager.save_run(run)
    campaign_state = CampaignManager(config).load_campaign_state(campaign_id)
    campaign_state.search_requests.append(
        AgentSearchRequest(
            id="pending-novelty-search",
            campaign_id=campaign_id,
            query="low false positive collusion detection closest prior work",
            purpose="novelty",
            source_profile="ai_safety",
            target_sources=["arXiv"],
            reason="Required closest-prior-work search is still pending.",
            status="proposed",
        )
    )
    CampaignManager(config).save_campaign_state(campaign_state)

    CampaignSearchAgent(config, sources=[_FixtureSearchSource("arXiv")]).propose_searches(campaign_id)
    reloaded = state_manager.load_run(run_id)

    assert reloaded.novelty_dossiers[0].verdict == "unknown"
    assert reloaded.novelty_dossiers[0].novelty_strength == "unknown"
    assert reloaded.novelty_dossiers[0].missing_searches


def test_campaign_source_policy_recommends_next_searches(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Policy Search Project")
    campaign = CampaignManager(config).create_campaign(
        "low false positive collusion detection",
        project_id=program.project.id,
        source_profile="ai_safety",
    )

    batch = CampaignSearchAgent(config, sources=[_FixtureSearchSource("arXiv"), _FixtureSearchSource("OpenReview")]).propose_searches(
        campaign.campaign.id
    )

    queries = [request.query.lower() for request in batch.requests]
    assert any("survey" in query or "benchmark" in query for query in queries)
    assert all(request.campaign_id == campaign.campaign.id for request in batch.requests)


def test_campaign_novelty_loop_unknown_triggers_research(tmp_path: Path) -> None:
    config, campaign_id, run_id = _campaign_context_fixture(tmp_path)

    payload = CampaignNoveltyLoop(config, sources=[_FixtureSearchSource("arXiv"), _FixtureSearchSource("Semantic Scholar")]).run(
        campaign_id
    )
    run = ResearchStateManager(config).load_run(run_id)

    assert payload["created_search_request_count"] > 0
    assert run.search_queries
    assert any(record.purpose in {"novelty", "related_work", "citation_expansion"} for record in run.search_queries)
    assert (Path(run.run_dir) / "retrieval" / "manifest.json").exists()


def test_campaign_novelty_loop_duplicate_prior_work_rejects_direction(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_context_fixture(tmp_path)
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    direction = DirectionMaturationManager(config).create_direction(campaign.project_id, "gap-relevant")

    payload = CampaignNoveltyLoop(config, sources=[_DuplicatePriorWorkSource("Semantic Scholar")]).run(campaign_id, gap_id="gap-relevant")
    program = ProjectMemoryManager(config).load_project(campaign.project_id)
    reloaded = next(item for item in program.research_directions if item.id == direction.id)

    assert payload["stop_reason"] == "closest_prior_work_rejects_idea"
    assert reloaded.maturity == "rejected"


def test_campaign_novelty_loop_budget_exhaustion_stops(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_context_fixture(tmp_path)
    state = CampaignManager(config).load_campaign_state(campaign_id)
    assert state.budget is not None
    state.budget.max_iterations = 0
    CampaignManager(config).save_campaign_state(state)

    payload = CampaignNoveltyLoop(config, sources=[_FixtureSearchSource("arXiv")]).run(campaign_id)

    assert payload["stop_reason"] == "budget_exhausted"
    assert payload["created_search_request_count"] == 0


def test_campaign_novelty_loop_refresh_updates_direction_maturity(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_context_fixture(tmp_path)
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    direction = DirectionMaturationManager(config).create_direction(campaign.project_id, "gap-relevant")

    payload = CampaignNoveltyLoop(config, sources=[_FixtureSearchSource("arXiv")]).run(campaign_id, gap_id="gap-relevant")
    program = ProjectMemoryManager(config).load_project(campaign.project_id)
    reloaded = next(item for item in program.research_directions if item.id == direction.id)

    assert payload["matured_directions"]
    assert "gap-relevant" in reloaded.linked_novelty_dossier_ids
    assert reloaded.maturity in {"candidate", "validated_gap", "experiment_ready", "rejected"}


def test_campaign_novelty_loop_source_policy_blocks_strong_novelty(tmp_path: Path) -> None:
    config, campaign_id, run_id = _campaign_context_fixture(tmp_path)
    state_manager = ResearchStateManager(config)
    run = state_manager.load_run(run_id)
    run.novelty_dossiers[0].verdict = "pursue"
    run.novelty_dossiers[0].novelty_strength = "strong"
    run.novelty_dossiers[0].confidence = "high"
    run.coverage_stopping_assessment = None
    state_manager.save_run(run)

    CampaignNoveltyLoop(config, sources=[_FixtureSearchSource("arXiv")]).run(campaign_id, gap_id="gap-relevant")
    reloaded = state_manager.load_run(run_id)

    assert all(dossier.novelty_strength != "strong" for dossier in reloaded.novelty_dossiers)
    assert any(dossier.missing_searches for dossier in reloaded.novelty_dossiers)


def test_campaign_output_rejects_fake_citation(tmp_path: Path) -> None:
    config, campaign_id, task_id, pack_dir = _campaign_task_fixture(tmp_path)
    output = pack_dir / "outputs" / "novelty_dossiers_patch.json"
    output.write_text(
        json.dumps(
            {
                "novelty_dossiers_patch": [
                    {
                        "target_id": "gap-1",
                        "idea_summary": "Fake prior work should fail.",
                        "top_prior_work": ["Imaginary Paper 2099"],
                        "verdict": "pursue",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    validation = validate_campaign_outputs(config, campaign_id, task_id, [output])

    assert validation["status"] == "rejected"
    assert any("citation does not resolve" in issue for issue in validation["issues"])


def test_campaign_output_imports_valid_patch_after_validation(tmp_path: Path) -> None:
    config, campaign_id, task_id, pack_dir = _campaign_task_fixture(tmp_path)
    output = pack_dir / "outputs" / "final_recommendation_patch.json"
    output.write_text(
        json.dumps(
            {
                "final_recommendation_patch": [
                    {
                        "recommendation": "Stop until more source coverage is collected.",
                        "verdict": "unknown",
                    }
                ],
                "public_reasoning_summary": "Coverage is insufficient for novelty claims.",
            }
        ),
        encoding="utf-8",
    )
    stop_output = pack_dir / "outputs" / "stop_condition_patch.json"
    stop_output.write_text(
        json.dumps(
            {
                "stop_condition_patch": [
                    {
                        "reason": "Evidence is insufficient.",
                        "triggered": True,
                        "evidence": ["source coverage missing"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    validation = import_campaign_outputs(config, campaign_id, task_id, [output, stop_output])
    loaded = CampaignManager(config).load_campaign_state(campaign_id)

    assert validation["status"] == "applied"
    assert loaded.steps[-1].status == "complete"
    assert loaded.stop_conditions[-1].reason == "Evidence is insufficient."
    assert loaded.decisions
    assert loaded.imports[-1].rollback_snapshot_path


def test_campaign_partial_import_records_rejected_fields(tmp_path: Path) -> None:
    config, campaign_id, task_id, pack_dir = _campaign_task_fixture(tmp_path)
    valid_output = pack_dir / "outputs" / "final_recommendation_patch.json"
    valid_output.write_text(
        json.dumps({"final_recommendation_patch": [{"recommendation": "Continue cautiously.", "verdict": "unknown"}]}),
        encoding="utf-8",
    )
    invalid_output = pack_dir / "outputs" / "stop_condition_patch.json"
    invalid_output.write_text(
        json.dumps({"stop_condition_patch": [{"reason": "Unsupported confidence.", "confidence": "high"}]}),
        encoding="utf-8",
    )

    record = CampaignOutputImporter(config).import_outputs(campaign_id, task_id, [valid_output, invalid_output])
    loaded = CampaignManager(config).load_campaign_state(campaign_id)

    assert record.status == "partial"
    assert record.accepted_objects
    assert record.rejected_objects
    assert loaded.imports[-1].status == "partial"


def test_campaign_rollback_restores_state(tmp_path: Path) -> None:
    config, campaign_id, task_id, pack_dir = _campaign_task_fixture(tmp_path)
    output = pack_dir / "outputs" / "final_recommendation_patch.json"
    output.write_text(
        json.dumps({"final_recommendation_patch": [{"recommendation": "Stop.", "verdict": "unknown"}]}),
        encoding="utf-8",
    )

    record = CampaignOutputImporter(config).import_outputs(campaign_id, task_id, [output])
    after_import = CampaignManager(config).load_campaign_state(campaign_id)
    rollback_record = rollback_import(config, record.id)
    after_rollback = CampaignManager(config).load_campaign_state(campaign_id)

    assert after_import.decisions
    assert rollback_record.status == "rolled_back"
    assert len(after_rollback.decisions) == 0
    assert after_rollback.imports[-1].status == "rolled_back"


def test_campaign_strong_novelty_blocked_under_poor_coverage(tmp_path: Path) -> None:
    config, campaign_id, task_id, pack_dir = _campaign_task_fixture(tmp_path)
    output = pack_dir / "outputs" / "novelty_dossiers_patch.json"
    output.write_text(
        json.dumps(
            {
                "novelty_dossiers_patch": [
                    {
                        "target_id": "gap-1",
                        "idea_summary": "Too strong.",
                        "top_prior_work": [{"paper_id": "paper-1"}],
                        "verdict": "pursue",
                        "novelty_strength": "strong",
                        "source_coverage": "low",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    validation = validate_campaign_outputs(config, campaign_id, task_id, [output])

    assert validation["status"] == "rejected"
    assert any("strong novelty is blocked" in issue for issue in validation["issues"])


def test_project_cli_commands(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["GAPFORGE_DISABLE_NETWORK"] = "1"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    init = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "init-project", "CLI Project"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr
    project_dir = Path(init.stdout.strip())
    project_id = project_dir.name

    use = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "use-project", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert use.returncode == 0, use.stderr
    assert json.loads((tmp_path / "data" / "active_project.json").read_text(encoding="utf-8"))["project_id"] == project_id

    listed = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "list-projects"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr
    assert project_id in listed.stdout
    assert "*active*" in listed.stdout

    run = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "init-topic", "cli topic"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    run_id = Path(run.stdout.strip()).name

    attach = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "attach-run", "--project-id", project_id, "--run-id", run_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert attach.returncode == 0, attach.stderr

    sync = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "sync-project-memory", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert sync.returncode == 0, sync.stderr

    status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "project-status", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["run_ids"] == [run_id]

    campaign_create = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "campaign-create", "cli campaign topic", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert campaign_create.returncode == 0, campaign_create.stderr
    campaign_id = campaign_create.stdout.strip()

    campaign_status = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "campaign-status", "--campaign-id", campaign_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert campaign_status.returncode == 0, campaign_status.stderr
    assert json.loads(campaign_status.stdout)["campaign_id"] == campaign_id

    campaign_stop = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "campaign-stop", "--campaign-id", campaign_id, "--reason", "Need review."],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert campaign_stop.returncode == 0, campaign_stop.stderr
    assert json.loads(campaign_stop.stdout)["status"] == "paused"

    campaign_resume = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "campaign-resume", "--campaign-id", campaign_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert campaign_resume.returncode == 0, campaign_resume.stderr
    assert json.loads(campaign_resume.stdout)["status"] == "running"

    campaign_next = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "campaign-next", "--campaign-id", campaign_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert campaign_next.returncode == 0, campaign_next.stderr
    assert json.loads(campaign_next.stdout)["decision_type"] in {"search_more", "stop"}

    campaign_run = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "campaign-run",
            "--campaign-id",
            campaign_id,
            "--mode",
            "deterministic",
            "--max-iterations",
            "1",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert campaign_run.returncode == 0, campaign_run.stderr
    assert json.loads(campaign_run.stdout)["decision_count"] >= 1

    report = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "project-report", "--project-id", project_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert report.returncode == 0, report.stderr
    assert (project_dir / "project_report.md").exists()


def test_campaign_controller_poor_coverage_triggers_search_more(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Controller Poor Coverage")
    campaign = CampaignManager(config).create_campaign("low false positive collusion", project_id=program.project.id)

    action = CampaignController(config).next_action(campaign.campaign.id)
    result = CampaignController(config).run(campaign.campaign.id, max_iterations=1)

    assert action.decision_type == "search_more"
    assert result.decisions[-1].decision_type == "search_more"
    assert result.campaign.run_ids
    assert result.steps[-1].status == "complete"


def test_campaign_controller_missing_index_triggers_build_index(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _controller_campaign_with_run(tmp_path, full_text=True)

    action = CampaignController(config).next_action(campaign_id)
    result = CampaignController(config).run(campaign_id, max_iterations=1)

    assert action.decision_type == "build_index"
    assert result.decisions[-1].decision_type == "build_index"
    assert (config.project_root / result.campaign.project_id / "retrieval" / "manifest.json").exists()


def test_campaign_controller_missing_full_text_triggers_parse_more(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _controller_campaign_with_run(tmp_path, full_text=False)
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    program = ProjectMemoryManager(config).sync_project_memory(campaign.project_id)
    build_project_index(program)

    action = CampaignController(config).next_action(campaign_id)

    assert action.decision_type == "parse_more"


def test_campaign_controller_unknown_novelty_creates_codex_task_pack_and_pauses(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _controller_campaign_ready_for_novelty(tmp_path, mode="codex_task_pack")

    action = CampaignController(config).next_action(campaign_id)
    result = CampaignController(config).run(campaign_id, max_iterations=1)

    assert action.decision_type == "ask_codex"
    assert action.task_type == "novelty_reviewer"
    assert result.campaign.status == "paused"
    assert result.campaign.task_ids
    assert any(step.status == "blocked" and step.task_spec_id for step in result.steps)


def test_campaign_controller_fake_agent_mode_imports_and_completes_task(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _controller_campaign_ready_for_novelty(tmp_path, mode="fake_agent")

    result = CampaignController(config).run(campaign_id, max_iterations=1)

    assert result.imports
    assert result.imports[-1].status in {"applied", "partial"}
    assert any(step.status == "complete" and step.task_spec_id for step in result.steps)


def test_campaign_controller_budget_exhaustion_stops(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    program = ProjectMemoryManager(config).create_project("Controller Budget")
    state = CampaignManager(config).create_campaign("budget topic", project_id=program.project.id)
    assert state.budget is not None
    state.budget.max_iterations = 0
    CampaignManager(config).save_campaign_state(state)

    result = CampaignController(config).run(state.campaign.id)

    assert result.decisions[-1].decision_type == "stop"
    assert result.stop_conditions[-1].triggered is True


def test_campaign_controller_rejected_direction_does_not_export(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _controller_campaign_ready_for_novelty(tmp_path, mode="deterministic", novelty_verdict="pursue")
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    project_manager = ProjectMemoryManager(config)
    program = project_manager.load_project(campaign.project_id)
    program.research_directions.append(
        ResearchDirection(
            id="direction-rejected",
            project_id=program.project.id,
            title="Rejected direction",
            summary="Should not export.",
            maturity="rejected",
            readiness_score=1.0,
        )
    )
    project_manager.save_project(program)

    action = CampaignController(config).next_action(campaign_id)

    assert action.decision_type != "export_package"


def test_campaign_controller_open_review_queue_requests_human_review(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _controller_campaign_with_run(tmp_path, full_text=True)
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    project_manager = ProjectMemoryManager(config)
    program = project_manager.load_project(campaign.project_id)
    program.review_queue = ReviewQueue(
        project_id=program.project.id,
        items=[
            ReviewQueueItem(
                id="review-item-1",
                project_id=program.project.id,
                object_type="claim",
                object_id="claim-1",
                priority="high",
                reason="Manual review required.",
                status="open",
            )
        ],
    )
    project_manager.save_project(program)
    build_project_index(project_manager.sync_project_memory(program.project.id))

    action = CampaignController(config).next_action(campaign_id)

    assert action.decision_type == "request_human_review"


def test_campaign_report_renders_with_explicit_stop_reason(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _controller_campaign_with_run(tmp_path, full_text=True)
    CampaignManager(config).stop_campaign(campaign_id, reason="No useful direction is ready under current evidence.")

    path = CampaignManager(config).campaign_report(campaign_id)
    text = path.read_text(encoding="utf-8")

    assert "## 17. Stop reason" in text
    assert "no_new_information" in text
    assert "## 19. Next recommended action" in text


def test_campaign_report_poor_coverage_does_not_recommend_direction(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    project = ProjectMemoryManager(config).create_project("Poor Coverage Report")
    state = CampaignManager(config).create_campaign("undercovered report topic", project_id=project.project.id)
    CampaignManager(config).stop_campaign(state.campaign.id, reason="Source coverage is too weak for a research recommendation.")

    path = CampaignManager(config).campaign_report(state.campaign.id)
    payload_path = path.with_suffix(".json")
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    assert payload["stop_reason"]["reason"] == "not_ready_poor_coverage"
    assert payload["recommendation"]["ready"] is False
    assert "No direction is ready" in path.read_text(encoding="utf-8")


def test_campaign_report_ready_direction_links_required_artifacts(tmp_path: Path) -> None:
    config, campaign_id, run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)
    state_manager = ResearchStateManager(config)
    run_state = state_manager.load_run(run_id)
    run_state.evidence_spans.append(
        EvidenceSpan(
            id="evidence-1",
            paper_id="paper-1",
            section_id="section-1",
            quote="Controller fixture full text.",
            locator="paper-1:Abstract:p1",
        )
    )
    run_state.gap_evidence_matrices[0].evidence_rows.append(
        GapEvidenceRow(
            paper_id="paper-1",
            evidence_span_id="evidence-1",
            text="Controller fixture full text.",
            section_type="abstract",
            locator="paper-1:Abstract:p1",
        )
    )
    state_manager.save_run(run_state)

    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    project_manager = ProjectMemoryManager(config)
    program = project_manager.load_project(campaign.project_id)
    program.research_directions[0].linked_gap_ids = ["gap-1"]
    program.related_work_matrices.append(RelatedWorkMatrix(direction_id="direction-ready", coverage_summary="Fixture matrix."))
    program.experiment_protocols.append(
        ExperimentProtocol(
            id="protocol-1",
            direction_id="direction-ready",
            linked_experiment_plan_id="experiment-1",
            objective="Test the fixture direction.",
            hypothesis="The fixture intervention improves low-FPR detection.",
            metrics=["false positive rate"],
        )
    )
    project_manager.save_project(program)
    CampaignManager(config).stop_campaign(campaign_id, reason="Campaign reached experiment-ready review gate.")

    path = CampaignManager(config).campaign_report(campaign_id)
    text = path.read_text(encoding="utf-8")
    payload = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))

    assert payload["recommendation"]["ready"] is True
    assert payload["recommendation"]["direction_id"] == "direction-ready"
    assert payload["recommendation"]["novelty_dossier_id"] == "gap-1"
    assert payload["recommendation"]["related_work_matrix_id"] == "direction-ready"
    assert payload["recommendation"]["experiment_protocol_id"] == "protocol-1"
    assert "paper-1:Abstract:p1" in text


def test_experiment_code_tasks_generated_from_protocol(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)
    _add_experiment_code_protocol(config, campaign_id)

    tasks = ExperimentCodeTaskGenerator(config).generate_tasks(
        campaign_id=campaign_id,
        direction_id="direction-ready",
    )

    task_types = {task.task_type for task in tasks}
    assert {"scaffold_repo", "implement_metric", "write_tests", "run_smoke"} <= task_types
    assert all(task.experiment_protocol_id == "protocol-code" for task in tasks)
    assert all(task.validation_commands for task in tasks)
    metric_task = next(task for task in tasks if task.task_type == "implement_metric")
    assert "false positive rate" in metric_task.instructions

    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    program = ProjectMemoryManager(config).load_project(campaign.project_id)
    assert len(program.experiment_code_tasks) == len(tasks)
    assert (Path(program.project.root_dir) / "experiment_code_tasks.md").exists()


def test_experiment_repo_scaffold_created(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)
    _add_experiment_code_protocol(config, campaign_id, include_dataset=False)

    scaffold = ExperimentRepoScaffolder(config).scaffold(
        campaign_id=campaign_id,
        direction_id="direction-ready",
    )

    root = Path(scaffold.path)
    assert (root / "README.md").exists()
    assert (root / "pyproject.toml").exists()
    assert (root / "tests" / "test_smoke.py").exists()
    assert (root / "data" / "README.md").exists()
    assert "SYNTHETIC PLACEHOLDER DATA ONLY" in (root / "data" / "README.md").read_text(encoding="utf-8")
    assert "no experiment results" in (root / "README.md").read_text(encoding="utf-8").lower()


def test_codex_code_task_file_contains_handoff_rules(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)
    _add_experiment_code_protocol(config, campaign_id)
    tasks = ExperimentCodeTaskGenerator(config).generate_tasks(campaign_id=campaign_id, direction_id="direction-ready")

    path = ExperimentCodeTaskGenerator(config).write_codex_task(tasks[0].id)
    text = path.read_text(encoding="utf-8")

    assert "Do not invent unavailable datasets" in text
    assert "Validation Commands" in text
    assert tasks[0].id in text


def test_rejected_direction_cannot_generate_code_tasks_without_override(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)
    _add_experiment_code_protocol(config, campaign_id)
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    project_manager = ProjectMemoryManager(config)
    program = project_manager.load_project(campaign.project_id)
    next(direction for direction in program.research_directions if direction.id == "direction-ready").maturity = "rejected"
    project_manager.save_project(program)

    with pytest.raises(ValueError, match="rejected"):
        ExperimentCodeTaskGenerator(config).generate_tasks(campaign_id=campaign_id, direction_id="direction-ready")


def test_reviewer_loop_missing_baseline_creates_required_fix(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)
    _prepare_reviewer_direction(config, campaign_id, include_baseline=False)

    payload = CampaignReviewerLoop(config).run(campaign_id, "direction-ready")

    required = payload["panel"]["required_changes"]
    assert any("baseline" in item.lower() for item in required)
    assert any(task["recommended_action"] == "add_baseline" for task in payload["rebuttal_tasks"])
    assert "results show" not in json.dumps(payload).lower()


def test_reviewer_loop_unsupported_novelty_creates_fatal_objection(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)
    _prepare_reviewer_direction(config, campaign_id, include_baseline=True, novelty_verdict="unknown")

    payload = CampaignReviewerLoop(config).run(campaign_id, "direction-ready")

    novelty_reviews = [review for review in payload["panel"]["reviewer_reviews"] if review["role"] == "novelty"]
    assert novelty_reviews
    assert novelty_reviews[0]["fatal_flaws"]
    assert any(task["recommended_action"] == "search_more" for task in payload["rebuttal_tasks"])


def test_apply_reviewer_fixes_queues_items_and_downgrades_fatal_direction(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)
    _prepare_reviewer_direction(config, campaign_id, include_baseline=False, novelty_verdict="unknown")
    CampaignReviewerLoop(config).run(campaign_id, "direction-ready")

    payload = CampaignReviewerLoop(config).apply_fixes(campaign_id, "direction-ready")

    assert payload["review_queue_items"]
    assert payload["direction_maturity"] != "experiment_ready"
    assert any(decision["decision_type"] in {"add_baseline", "search_more"} for decision in payload["decisions"])
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    program = ProjectMemoryManager(config).load_project(campaign.project_id)
    assert program.review_queue is not None
    assert any(item.requested_by_skill == "reviewer-loop" for item in program.review_queue.items)


def test_rebuttal_tasks_command_payload_does_not_invent_results(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)
    _prepare_reviewer_direction(config, campaign_id, include_baseline=True)
    CampaignReviewerLoop(config).run(campaign_id, "direction-ready")

    payload = CampaignReviewerLoop(config).rebuttal_tasks(campaign_id, "direction-ready")
    text = json.dumps(payload).lower()

    assert "achieved" not in text
    assert all(task["must_not_invent_results"] is True for task in payload["rebuttal_tasks"])


def test_campaign_report_invalid_agent_output_stop_reason_visible(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _controller_campaign_with_run(tmp_path, full_text=True, mode="codex_task_pack")
    state = CampaignManager(config).load_campaign_state(campaign_id)
    state.imports.append(
        CampaignImportRecord(
            id="campaign-import-invalid",
            campaign_id=campaign_id,
            task_id="task-invalid",
            status="rejected",
            issues=["Unsupported high-confidence claim."],
        )
    )
    CampaignManager(config).save_campaign_state(state)

    path = CampaignManager(config).campaign_report(campaign_id)
    text = path.read_text(encoding="utf-8")

    assert "agent_output_invalid" in text
    assert "Unsupported high-confidence claim" in text


def test_campaign_report_manual_handoff_pending_visible(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _controller_campaign_ready_for_novelty(tmp_path, mode="codex_task_pack")

    CampaignController(config).run(campaign_id, max_iterations=1)
    path = CampaignManager(config).campaign_report(campaign_id)
    payload = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))

    assert payload["stop_reason"]["reason"] == "manual_handoff_pending"
    assert "Complete the Codex/GPT-5.4 handoff" in payload["next_recommended_action"]


def test_campaign_task_pack_size_and_handoff_commands(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GAPFORGE_TASK_PACK_WARNING_CHARS", "50000")
    _config, _campaign_id, _task_id, pack_dir = _campaign_task_fixture(tmp_path)

    budget = json.loads((pack_dir / "token_budget.json").read_text(encoding="utf-8"))
    handoff = (pack_dir / "HANDOFF.md").read_text(encoding="utf-8")
    task = (pack_dir / "CAMPAIGN_TASK.md").read_text(encoding="utf-8")

    assert budget["total_chars"] < budget["threshold_chars"]
    assert budget["warnings"] == []
    assert "schema_examples.json" in task
    assert "gapforge validate-import-all --task-id" in handoff
    assert "gapforge attest-agent-run" in handoff


def test_repair_agent_output_cli_generates_actionable_instructions(tmp_path: Path) -> None:
    _config, _campaign_id, task_id, pack_dir = _campaign_task_fixture(tmp_path)
    bad_output = pack_dir / "outputs" / "stop_condition_patch.json"
    bad_output.write_text(
        json.dumps({"stop_condition_patch": [{"reason": "Stop because fake paper solves it.", "paper_id": "fake-paper"}]}),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "repair-agent-output",
            "--task-id",
            task_id,
            "--path",
            str(bad_output),
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "unknown paper_id: fake-paper" in result.stdout
    assert "Repair Rules" in result.stdout
    assert "move them into a search request" in result.stdout


def test_validate_import_all_handles_multiple_campaign_tasks(tmp_path: Path) -> None:
    config, campaign_id, _task_id, _pack_dir = _campaign_task_fixture(tmp_path)
    create_campaign_task_pack(config, campaign_id, "campaign_planning")

    payload = validate_import_all(config, campaign_id)

    assert payload["processed_task_count"] == 2
    assert payload["rejected_count"] == 2
    assert payload["status"] == "rejected"
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    diagnostics_dir = config.project_root / campaign.project_id / "campaigns" / campaign_id / "diagnostics"
    assert any(diagnostics_dir.glob("real_run_diagnostic_*.md"))


def test_campaign_review_without_actual_agent_output_not_eligible(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=False)

    review, summary = CampaignReviewManager(config).review(
        campaign_id,
        accept=True,
        reviewer="Reviewer",
        source_coverage_score=4,
        stop_reason_quality_score=4,
    )

    assert review.accepted is True
    assert summary.accepted is False
    assert summary.release_gate_eligible is False
    assert "No actual Codex/GPT-5.4 output is imported." in summary.blocking_failures


def test_campaign_review_fake_citation_blocks_acceptance(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)

    _, summary = CampaignReviewManager(config).review(campaign_id, accept=True, reviewer="Reviewer", fake_citation_found=True)

    assert summary.accepted is False
    assert "Fake citation found." in summary.blocking_failures


def test_campaign_review_unsupported_claim_blocks_acceptance(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)

    _, summary = CampaignReviewManager(config).review(
        campaign_id,
        accept=True,
        reviewer="Reviewer",
        unsupported_high_confidence_claim_found=True,
    )

    assert summary.accepted is False
    assert "Unsupported high-confidence claim found." in summary.blocking_failures


def test_campaign_review_attested_task_pack_can_be_release_eligible(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)

    _, summary = CampaignReviewManager(config).review(campaign_id, accept=True, reviewer="Reviewer")
    gate = CampaignReviewManager(config).v4_actual_run_acceptance()

    assert summary.accepted is True
    assert summary.actual_run_attestation_present is True
    assert summary.release_gate_eligible is True
    assert gate["passed"] is True
    assert campaign_id in gate["accepted_campaigns"]


def test_campaign_review_refusal_campaign_can_be_accepted_without_release_eligibility(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _controller_campaign_with_run(tmp_path, full_text=True, mode="deterministic")
    manager = CampaignManager(config)
    state = manager.stop_campaign(campaign_id, reason="No useful direction is ready under current evidence.")

    _, summary = CampaignReviewManager(config).review(
        state.campaign.id,
        accept=True,
        reviewer="Reviewer",
        stop_reason_quality_score=5,
    )

    assert summary.accepted is True
    assert summary.release_gate_eligible is False


def test_campaign_review_cli_form_acceptance_and_gate(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=True)
    env = {**os.environ, "GAPFORGE_DISABLE_NETWORK": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    form = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "campaign-review", "--campaign-id", campaign_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert form.returncode == 0, form.stderr
    assert "Campaign Human Review" in form.stdout

    accepted = subprocess.run(
        [
            sys.executable,
            "-m",
            "gapforge.cli",
            "campaign-review",
            "--campaign-id",
            campaign_id,
            "--accept",
            "--reviewer",
            "Reviewer",
        ],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert accepted.returncode == 0, accepted.stderr
    assert json.loads(accepted.stdout)["summary"]["release_gate_eligible"] is True

    summary = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "campaign-acceptance", "--campaign-id", campaign_id],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert summary.returncode == 0, summary.stderr
    assert json.loads(summary.stdout)["accepted"] is True

    gate = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "v4-actual-run-acceptance"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert gate.returncode == 0, gate.stderr
    assert json.loads(gate.stdout)["passed"] is True


def test_campaign_acceptance_uses_stored_attestation_status(tmp_path: Path) -> None:
    config, campaign_id, _run_id = _campaign_ready_for_acceptance(tmp_path, with_actual_output=False)
    campaign_manager = CampaignManager(config)
    campaign_state = campaign_manager.load_campaign_state(campaign_id)
    task_id = "campaign-task-attested"
    campaign_state.campaign.task_ids.append(task_id)
    campaign_state.imports.append(
        CampaignImportRecord(
            id="campaign-import-attested",
            campaign_id=campaign_id,
            task_id=task_id,
            status="applied",
            accepted_objects=[{"type": "file", "id": "novelty_dossiers_patch.json", "source_path": "agent-output"}],
        )
    )
    create_campaign_actual_run_attestation(
        campaign_state,
        task_id,
        agent_name="codex",
        model="gpt-5.4",
        execution_method="task_pack",
        attester="Reviewer",
    )
    campaign_manager.save_campaign_state(campaign_state)
    pending_status = campaign_task_attestation_status(campaign_state, task_id)
    assert pending_status.accepted_as_actual_run is True
    assert "Campaign human review acceptance is missing." in pending_status.blockers

    _, summary = CampaignReviewManager(config).review(campaign_id, accept=True, reviewer="Reviewer")

    assert summary.actual_run_attestation_present is True
    assert summary.accepted_real_agent_outputs == ["campaign-import-attested"]
    assert summary.release_gate_eligible is True


def _campaign_context_fixture(tmp_path: Path, *, long_text: bool = False):
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Campaign Context Project")
    run_state = state_manager.create_run("low false positive collusion detection")
    relevant_text = (
        "Low false positive collusion detection in LLM agents evaluates covert coordination at strict alert budgets. "
        "The experiment reports specificity-sensitive monitoring evidence."
    )
    if long_text:
        relevant_text = relevant_text + " " + ("low false positive collusion detection detailed evidence " * 200)
    run_state.papers.extend(
        [
            Paper(
                id="paper-relevant",
                title="Low False Positive Collusion Detection for LLM Agents",
                authors=["A"],
                abstract="A paper about low false positive collusion detection and monitor specificity.",
                year=2026,
                source="fixture",
                roles=["frontier"],
            ),
            Paper(
                id="paper-irrelevant",
                title="Wildfire Fuel Moisture Forecasting",
                authors=["B"],
                abstract="A paper about wildfire spread prediction and satellite weather data.",
                year=2024,
                source="fixture",
            ),
        ]
    )
    run_state.paper_sections.extend(
        [
            PaperSection(
                id="section-relevant-results",
                paper_id="paper-relevant",
                title="Results",
                section_type="results",
                page_start=4,
                page_end=5,
                text=relevant_text,
                confidence="high",
            ),
            PaperSection(
                id="section-irrelevant-results",
                paper_id="paper-irrelevant",
                title="Results",
                section_type="results",
                page_start=3,
                text="Fuel moisture forecasts improve wildfire prediction.",
                confidence="high",
            ),
        ]
    )
    run_state.evidence_spans.append(
        EvidenceSpan(
            id="evidence-relevant",
            paper_id="paper-relevant",
            section_id="section-relevant-results",
            quote="Low false positive collusion detection evidence supports specificity-sensitive monitoring.",
            page_start=4,
            page_end=4,
            locator="paper-relevant:Results:p4",
            evidence_type="result",
            confidence="high",
        )
    )
    run_state.gaps.append(
        Gap(
            id="gap-relevant",
            title="Low-FPR collusion evaluation gap",
            description="Collusion monitors need evidence at low false-positive operating points.",
            supporting_paper_ids=["paper-relevant"],
            confidence="medium",
            risk_that_gap_is_fake="Closest prior work may already test the same operating point.",
        )
    )
    run_state.novelty_dossiers.append(
        NoveltyDossier(
            target_id="gap-relevant",
            idea_summary="Evaluate collusion detection at low false-positive rates.",
            top_prior_work=["paper-relevant"],
            candidates_considered=["paper-relevant"],
            verdict="unknown",
            novelty_strength="unknown",
            confidence="low",
            missing_searches=["Need broader closest-prior-work search."],
        )
    )
    run_state.source_coverage = SourceCoverageReport(
        run_id=run_state.run_id,
        topic=run_state.topic.text,
        searched_sources=["fixture"],
        papers_by_source={"fixture": 2},
        papers_with_full_text=["paper-relevant", "paper-irrelevant"],
        papers_abstract_only=[],
        confidence="medium",
    )
    state_manager.save_run(run_state)
    project_manager.attach_run(program.project.id, run_state.run_id)
    project_manager.sync_project_memory(program.project.id)
    campaign_state = CampaignManager(config).create_campaign(
        "low false positive collusion detection",
        project_id=program.project.id,
        mode="codex_task_pack",
        source_profile="ai_safety",
    )
    CampaignManager(config).attach_run(campaign_state.campaign.id, run_state.run_id)
    return config, campaign_state.campaign.id, run_state.run_id


class _FixtureSearchSource:
    def __init__(self, name: str) -> None:
        self.name = name

    def search(
        self,
        query: str,
        *,
        max_results: int,
        sort: str = "newest",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[Paper]:
        del sort, date_from, date_to
        normalized = "-".join(query.lower().split())[:40]
        return [
            Paper(
                id=f"{self.name.lower().replace(' ', '-')}-{normalized}-{index}",
                title=f"{query.title()} Fixture Result {index}",
                authors=["Fixture Author"],
                abstract=f"Fixture source result for {query} with benchmark and novelty context.",
                year=2026 - index,
                source=self.name,
                venue=self.name,
                citation_count=10 + index,
            )
            for index in range(1, max_results + 1)
        ]


class _DuplicatePriorWorkSource(_FixtureSearchSource):
    def search(
        self,
        query: str,
        *,
        max_results: int,
        sort: str = "newest",
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[Paper]:
        del query, max_results, sort, date_from, date_to
        return [
            Paper(
                id="duplicate-prior-work",
                title="Low-FPR Collusion Evaluation Gap",
                authors=["Prior Author"],
                abstract=(
                    "Collusion monitors need evidence at low false-positive operating points. "
                    "This paper evaluates collusion detection at low false positive rates with the same method metric and benchmark."
                ),
                year=2026,
                source=self.name,
                venue=self.name,
                citation_count=50,
            )
        ]


def _campaign_task_fixture(tmp_path: Path):
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project("Campaign Output Project")
    run_state = state_manager.create_run("campaign output topic")
    run_state.papers.append(
        Paper(
            id="paper-1",
            title="Known Campaign Paper",
            authors=["A"],
            abstract="Known evidence.",
            year=2026,
            source="fixture",
        )
    )
    state_manager.save_run(run_state)
    project_manager.attach_run(program.project.id, run_state.run_id)
    project_manager.sync_project_memory(program.project.id)
    campaign_state = CampaignManager(config).create_campaign("campaign output topic", project_id=program.project.id)
    pack_dir = create_campaign_task_pack(config, campaign_state.campaign.id, "campaign_stop_decision")
    return config, campaign_state.campaign.id, pack_dir.name, pack_dir


def _controller_campaign_with_run(tmp_path: Path, *, full_text: bool, mode: str = "deterministic"):
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.create_project(f"Controller Project {full_text} {mode}")
    run_state = state_manager.create_run("controller campaign topic")
    run_state.papers.append(
        Paper(
            id="paper-1",
            title="Controller Campaign Paper",
            authors=["A"],
            abstract="A controller fixture paper.",
            year=2026,
            source="fixture",
        )
    )
    if full_text:
        run_state.paper_sections.append(
            PaperSection(
                id="section-1",
                paper_id="paper-1",
                title="Abstract",
                section_type="abstract",
                text="Controller fixture full text.",
            )
        )
    run_state.source_coverage = SourceCoverageReport(
        run_id=run_state.run_id,
        topic=run_state.topic.text,
        searched_sources=["fixture"],
        papers_by_source={"fixture": 1},
        papers_with_full_text=["paper-1"] if full_text else [],
        papers_abstract_only=[] if full_text else ["paper-1"],
        confidence="medium",
    )
    state_manager.save_run(run_state)
    project_manager.attach_run(program.project.id, run_state.run_id)
    project_manager.sync_project_memory(program.project.id)
    campaign_state = CampaignManager(config).create_campaign("controller campaign topic", project_id=program.project.id, mode=mode)
    CampaignManager(config).attach_run(campaign_state.campaign.id, run_state.run_id)
    return config, campaign_state.campaign.id, run_state.run_id


def _controller_campaign_ready_for_novelty(tmp_path: Path, *, mode: str, novelty_verdict: str = "unknown"):
    config, campaign_id, run_id = _controller_campaign_with_run(tmp_path, full_text=True, mode=mode)
    state_manager = ResearchStateManager(config)
    run_state = state_manager.load_run(run_id)
    run_state.paper_notes.append(PaperNote(paper_id="paper-1", confidence="medium"))
    run_state.gaps.append(
        Gap(
            id="gap-1",
            description="A fixture evidence-backed gap.",
            supporting_paper_ids=["paper-1"],
            risk_that_gap_is_fake="Fixture risk remains.",
            confidence="medium",
        )
    )
    run_state.gap_evidence_matrices.append(
        GapEvidenceMatrix(
            gap_id="gap-1",
            papers_supporting=["paper-1"],
            repeated_limitation_count=1,
            confidence="medium",
        )
    )
    run_state.novelty_dossiers.append(
        NoveltyDossier(
            target_id="gap-1",
            idea_summary="Fixture novelty check.",
            top_prior_work=["paper-1"] if novelty_verdict != "unknown" else [],
            verdict=novelty_verdict,
            novelty_strength="medium" if novelty_verdict == "pursue" else "unknown",
            confidence="medium" if novelty_verdict == "pursue" else "low",
        )
    )
    state_manager.save_run(run_state)
    project_manager = ProjectMemoryManager(config)
    program = project_manager.sync_project_memory(CampaignManager(config).load_campaign_state(campaign_id).campaign.project_id)
    build_project_index(program)
    return config, campaign_id, run_id


def _campaign_ready_for_acceptance(tmp_path: Path, *, with_actual_output: bool):
    config, campaign_id, run_id = _controller_campaign_ready_for_novelty(tmp_path, mode="codex_task_pack", novelty_verdict="pursue")
    campaign_manager = CampaignManager(config)
    project_manager = ProjectMemoryManager(config)
    campaign_state = campaign_manager.load_campaign_state(campaign_id)
    program = project_manager.load_project(campaign_state.campaign.project_id)
    program.research_directions.append(
        ResearchDirection(
            id="direction-ready",
            project_id=program.project.id,
            title="Ready direction",
            summary="Fixture direction ready for acceptance review.",
            maturity="experiment_ready",
            readiness_score=0.9,
        )
    )
    project_manager.save_project(program)
    campaign_state = campaign_manager.stop_campaign(campaign_id, reason="Campaign reached experiment-ready review gate.")
    if with_actual_output:
        campaign_state.imports.append(
            CampaignImportRecord(
                id="campaign-import-attested",
                campaign_id=campaign_id,
                task_id="campaign-task-attested",
                status="applied",
                accepted_objects=[
                    {"type": "file", "id": "novelty_dossiers_patch.json", "source_path": "agent-output"},
                    {
                        "type": "agent_actual_run_attestation",
                        "id": "attestation-1",
                        "accepted": True,
                    },
                ],
            )
        )
        campaign_manager.save_campaign_state(campaign_state)
    return config, campaign_id, run_id


def _add_experiment_code_protocol(config: GapForgeConfig, campaign_id: str, *, include_dataset: bool = True) -> None:
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    project_manager = ProjectMemoryManager(config)
    program = project_manager.load_project(campaign.project_id)
    protocol = ExperimentProtocol(
        id="protocol-code",
        direction_id="direction-ready",
        linked_experiment_plan_id="experiment-code",
        objective="Test whether calibrated monitoring reduces low false positives.",
        hypothesis="Calibration should reduce false positives without hiding true collusion.",
        datasets=["allowed fixture benchmark"] if include_dataset else [],
        baselines=[
            BaselineCandidate(
                paper_id="paper-1",
                baseline_name="Threshold monitor baseline",
                why_required="Reviewer needs a direct low-FPR comparison.",
            )
        ],
        metrics=["false positive rate", "recall at fixed FPR"],
        statistical_tests=["binomial confidence interval"],
        ablations=["remove calibration", "seed sensitivity"],
        expected_artifacts=["artifacts/smoke_status.json"],
        evaluation_script_outline=["Load records", "Run baseline", "Compute metrics"],
    )
    program.experiment_protocols = [item for item in program.experiment_protocols if item.direction_id != "direction-ready"]
    program.experiment_protocols.append(protocol)
    project_manager.save_project(program)


def _prepare_reviewer_direction(
    config: GapForgeConfig,
    campaign_id: str,
    *,
    include_baseline: bool,
    novelty_verdict: str = "pursue",
) -> None:
    campaign = CampaignManager(config).load_campaign_state(campaign_id).campaign
    project_manager = ProjectMemoryManager(config)
    program = project_manager.load_project(campaign.project_id)
    direction = next(item for item in program.research_directions if item.id == "direction-ready")
    direction.linked_gap_ids = ["gap-1"]
    direction.linked_experiment_ids = ["experiment-code"]
    direction.maturity = "experiment_ready"
    protocol = ExperimentProtocol(
        id="protocol-reviewer",
        direction_id="direction-ready",
        linked_experiment_plan_id="experiment-code",
        objective="Test calibrated monitoring at low false-positive rates.",
        hypothesis="Calibration should reduce false positives without hiding true positives.",
        datasets=["fixture benchmark"],
        baselines=[
            BaselineCandidate(
                paper_id="paper-1",
                baseline_name="Threshold monitor baseline",
                why_required="Closest current monitoring baseline.",
            )
        ]
        if include_baseline
        else [],
        metrics=["false positive rate"],
        statistical_tests=["binomial confidence interval"],
        failure_modes=["No improvement over baseline falsifies the practical value."],
        safety_ethics_notes=["Avoid deployment claims without human review."],
    )
    protocol.reproducibility_checklist.metric_definitions = ["false positive rate"]
    program.experiment_protocols = [item for item in program.experiment_protocols if item.direction_id != "direction-ready"]
    program.experiment_protocols.append(protocol)
    project_manager.save_project(program)
    state_manager = ResearchStateManager(config)
    run_state = state_manager.load_run(campaign.run_ids[0])
    for dossier in run_state.novelty_dossiers:
        if dossier.target_id == "gap-1":
            dossier.verdict = novelty_verdict
            dossier.top_prior_work = ["paper-1"] if novelty_verdict != "unknown" else []
            dossier.confidence = "medium" if novelty_verdict != "unknown" else "low"
            dossier.missing_searches = ["Need closest prior work search."] if novelty_verdict == "unknown" else []
    state_manager.save_run(run_state)
