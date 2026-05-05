from __future__ import annotations

from pathlib import Path

from gapforge.config import GapForgeConfig
from gapforge.models import (
    ActiveLoopState,
    CitationGraph,
    Claim,
    CoverageStoppingAssessment,
    ExperimentPlan,
    Gap,
    NoveltyAssessment,
    NoveltyDossier,
    PaperNote,
    ResearchBudget,
    ReviewQueue,
    ReviewQueueItem,
)
from gapforge.orchestration.decisions import ActiveLoopDecider
from gapforge.project_memory import ProjectMemoryManager
from gapforge.review.queue import ReviewQueueManager
from gapforge.state import ResearchStateManager


def test_unsupported_high_confidence_claim_creates_queue_item(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state_manager = ResearchStateManager(config)
    state = state_manager.create_run("review queue")
    state.claims.append(
        Claim(
            id="claim-1",
            text="This high-impact deployment claim has no evidence.",
            type="result",
            status="unsupported",
            confidence="high",
            created_by_skill="deep-reading-llm",
        )
    )
    state_manager.save_run(state)

    queue = ReviewQueueManager(config).build_for_run(state.run_id)

    assert queue.summary.startswith("1 open")
    item = queue.items[0]
    assert item.object_type == "claim"
    assert item.object_id == "claim-1"
    assert item.priority == "high"
    assert (Path(state.run_dir) / "review_queue.md").exists()


def test_completed_review_queue_item_persists(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = _run_with_unsupported_claim(config)
    project = ProjectMemoryManager(config).create_project("Review Queue Project")
    ProjectMemoryManager(config).attach_run(project.project.id, state.run_id)
    manager = ReviewQueueManager(config)
    queue = manager.build_for_project(project.project.id)
    item_id = queue.items[0].id

    manager.complete_project_item(project.project.id, item_id, note="Reviewed and accepted risk.")
    rebuilt = manager.build_for_project(project.project.id)

    item = next(item for item in rebuilt.items if item.id == item_id)
    assert item.status == "completed"
    assert item.completed_at
    program = ProjectMemoryManager(config).load_project(project.project.id)
    assert any(record.record_type == "decision" and item_id in record.linked_object_ids for record in program.memory_records)


def test_dismissed_review_queue_item_is_auditable(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = _run_with_unsupported_claim(config)
    project = ProjectMemoryManager(config).create_project("Dismiss Queue Project")
    ProjectMemoryManager(config).attach_run(project.project.id, state.run_id)
    manager = ReviewQueueManager(config)
    queue = manager.build_for_project(project.project.id)
    item_id = queue.items[0].id

    manager.dismiss_project_item(project.project.id, item_id, reason="Known synthetic fixture issue.")
    program = ProjectMemoryManager(config).load_project(project.project.id)

    item = next(item for item in program.review_queue.items if item.id == item_id)
    assert item.status == "dismissed"
    assert any("Known synthetic fixture issue" in record.text for record in program.memory_records)


def test_active_loop_can_request_human_review_from_queue(tmp_path: Path) -> None:
    config = GapForgeConfig.from_cwd(tmp_path)
    state = ResearchStateManager(config).create_run("active loop queue")
    state.paper_notes.append(PaperNote(paper_id="paper-1", one_sentence_summary="fixture note"))
    state.gaps.append(Gap(id="gap-1", title="Promising gap", description="Gap", confidence="medium"))
    state.novelty_assessments.append(
        NoveltyAssessment(target_gap_or_hypothesis_id="gap-1", idea_summary="Gap", verdict="pursue", novelty_strength="medium")
    )
    state.novelty_dossiers.append(
        NoveltyDossier(
            target_id="gap-1",
            idea_summary="Gap",
            verdict="pursue",
            novelty_strength="medium",
            top_prior_work=["paper-1"],
        )
    )
    state.experiments.append(ExperimentPlan(id="experiment-1", title="Experiment", linked_gap_ids=["gap-1"], metrics=["FPR"]))
    state.citation_graph = CitationGraph(paper_ids=[])
    state.coverage_stopping_assessment = CoverageStoppingAssessment(
        run_id=state.run_id,
        enough_for_mapping=True,
        enough_for_gap_mining=True,
        enough_for_novelty=True,
        enough_for_experiment_design=False,
    )
    state.review_queue = ReviewQueue(
        items=[
            ReviewQueueItem(
                id="review-item-1",
                run_id=state.run_id,
                object_type="claim",
                object_id="claim-1",
                priority="high",
                reason="Needs review.",
            )
        ]
    )
    state.active_loop = ActiveLoopState(budget=ResearchBudget(max_queries=10, stop_when_coverage_sufficient=False))

    decision = ActiveLoopDecider().decide(state, state.active_loop)

    assert decision.decision_type == "request_human_review"
    assert "claim:claim-1" in decision.evidence[0]


def _run_with_unsupported_claim(config: GapForgeConfig):
    state_manager = ResearchStateManager(config)
    state = state_manager.create_run("project review queue")
    state.claims.append(
        Claim(
            id="claim-1",
            text="High-confidence unsupported project claim.",
            type="novelty",
            status="unsupported",
            confidence="high",
        )
    )
    state_manager.save_run(state)
    return state
