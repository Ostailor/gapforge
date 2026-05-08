from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.ideas import IdeaSeedGenerator, IdeaStore, TopicPortfolioGenerator, is_generic_idea_title
from gapforge.models import HumanReviewRecord, ProjectMemoryRecord, Provenance, RelatedWorkMatrix, ResearchDirection
from gapforge.project_memory import ProjectMemoryManager
from gapforge.state import ResearchStateManager, utc_now_iso

LOW_FPR_TOPIC = "low false-positive collusion detection in LLM multi-agent systems"


def test_idea_bank_generated_from_topic_portfolio(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    portfolio = TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)

    result = IdeaSeedGenerator(config).generate(portfolio_id=portfolio.id)
    state = IdeaStore(config).load_state(project_id)

    assert result.bank.project_id == project_id
    assert len(result.candidates) >= len(portfolio.topic_variants)
    assert state.idea_bank is not None
    assert len(state.idea_bank.candidate_ids) == len(state.candidates)
    assert all(candidate.maturity == "seed" for candidate in state.candidates)
    assert all(candidate.novelty_status != "strong" for candidate in state.candidates)
    assert all(candidate.contribution_type for candidate in state.candidates)
    assert all(candidate.likely_failure_mode for candidate in state.candidates)


def test_generated_seed_pool_is_diverse(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    program_manager = ProjectMemoryManager(config)
    program = program_manager.load_project(project_id)
    program.memory_records.append(
        ProjectMemoryRecord(
            id="memory-gap-low-fpr",
            project_id=project_id,
            record_type="gap",
            text="Existing monitor papers rarely report specificity under benign multi-agent communication.",
            linked_paper_ids=["paper-known-gap"],
            status="active",
        )
    )
    program.related_work_matrices.append(
        RelatedWorkMatrix(
            direction_id="direction-low-fpr",
            missing_categories=["benchmark with benign negatives", "evaluation protocol"],
            must_read_paper_ids=["paper-must-read"],
            baseline_paper_ids=["paper-baseline"],
        )
    )
    program.research_directions.append(
        ResearchDirection(
            id="agenda-low-fpr",
            project_id=project_id,
            title="Specificity-first monitor evaluation agenda",
            summary="Prefer ideas that make benign communication false alarms visible.",
            maturity="agenda_item",
            readiness_score=0.6,
            supporting_paper_ids=["paper-agenda-support"],
        )
    )
    run_state_manager = ResearchStateManager(config)
    run = run_state_manager.create_run(LOW_FPR_TOPIC)
    run.human_reviews.append(
        HumanReviewRecord(
            id="review-prefer-specificity",
            object_type="direction",
            object_id="agenda-low-fpr",
            action="approve",
            note="Prefer specificity-first ideas over broad monitor claims.",
        )
    )
    run_state_manager.save_run(run)
    program.run_ids.append(run.run_id)
    program_manager.save_project(program)
    portfolio = TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)

    result = IdeaSeedGenerator(config).generate(portfolio_id=portfolio.id)
    contribution_types = {candidate.contribution_type for candidate in result.candidates}
    source_types = {candidate.provenance.created_by_skill.split(":", 1)[-1] for candidate in result.candidates}

    assert {"benchmark", "measurement", "evaluation_protocol", "negative_result", "theory"}.issubset(contribution_types)
    assert {
        "topic_variant",
        "repeated_literature_gap",
        "missing_benchmark",
        "missing_evaluation_protocol",
        "negative_result_opportunity",
        "measurement_study_opportunity",
        "theory_guarantee_opportunity",
    }.issubset(source_types)
    benchmark_seed = next(
        candidate for candidate in result.candidates if candidate.provenance.created_by_skill.endswith("missing_benchmark")
    )
    assert "paper-must-read" in benchmark_seed.closest_prior_work_ids
    assert "paper-baseline" in benchmark_seed.closest_prior_work_ids
    assert any("agenda-low-fpr" in candidate.provenance.source_ids for candidate in result.candidates)
    assert any("review-prefer-specificity" in candidate.provenance.source_ids for candidate in result.candidates)


def test_rejected_ideas_influence_new_seeds(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    idea_store = IdeaStore(config)
    idea_store.create_bank(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    rejected = idea_store.add_candidate(
        project_id=project_id,
        source_topic_id="topic-rejected",
        title="Generic monitor idea",
        summary="Rejected broad monitor framing.",
        contribution_type="measurement",
    )
    idea_store.reject_candidate(rejected.id, "too generic and missing benign negatives")
    portfolio = TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)

    result = IdeaSeedGenerator(config).generate(portfolio_id=portfolio.id)
    mutation_seeds = [
        candidate for candidate in result.candidates if candidate.provenance.created_by_skill.endswith("rejected_idea_mutation")
    ]

    assert mutation_seeds
    assert any("too generic and missing benign negatives" in candidate.likely_failure_mode for candidate in mutation_seeds)
    assert all(candidate.maturity == "seed" for candidate in mutation_seeds)


def test_generic_idea_filter_catches_empty_and_generic_titles() -> None:
    assert is_generic_idea_title("")
    assert is_generic_idea_title("idea")
    assert is_generic_idea_title("research idea")
    assert is_generic_idea_title("AI idea")
    assert is_generic_idea_title("topic")
    assert not is_generic_idea_title("Low false-positive benchmark for benign multi-agent communication")


def test_idea_generation_report_renders(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    portfolio = TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    result = IdeaSeedGenerator(config).generate(portfolio_id=portfolio.id, max_candidates=5)

    report = IdeaStore(config).write_bank_report(project_id)
    candidate_report = IdeaStore(config).write_idea_report(result.candidates[0].id)

    assert "# Idea Bank" in report
    assert "Active candidates: 5" in report
    assert "Idea maturity is separate from paper readiness" in report
    assert "Likely failure mode" in candidate_report
    assert "Novelty status: `unchecked`" in candidate_report


def test_idea_generate_cli_from_project_and_portfolio(tmp_path: Path) -> None:
    config, project_id = _project(tmp_path)
    portfolio = TopicPortfolioGenerator(config).generate(project_id=project_id, root_topic=LOW_FPR_TOPIC)
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}

    by_project = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-generate", "--project-id", project_id, "--max-candidates", "4"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert by_project.returncode == 0, by_project.stderr
    payload = json.loads(by_project.stdout)
    assert payload["bank"]["project_id"] == project_id
    assert len(payload["candidates"]) == 4
    assert all(candidate["maturity"] == "seed" for candidate in payload["candidates"])

    by_portfolio = subprocess.run(
        [sys.executable, "-m", "gapforge.cli", "idea-generate", "--portfolio-id", portfolio.id, "--max-candidates", "3"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert by_portfolio.returncode == 0, by_portfolio.stderr
    assert json.loads(by_portfolio.stdout)["bank"]["project_id"] == project_id


def _project(tmp_path: Path) -> tuple[GapForgeConfig, str]:
    config = GapForgeConfig.from_cwd(tmp_path)
    manager = ProjectMemoryManager(config)
    program = manager.create_project("Idea Generator Project")
    program.provenance.append(
        Provenance(
            created_by_skill="test",
            timestamp=utc_now_iso(),
            reasoning_summary="Test fixture project for idea seed generation.",
        )
    )
    manager.save_project(program)
    return config, program.project.id
